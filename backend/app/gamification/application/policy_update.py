"""Batched, consent-aware update of the support policy. The active artifact stays put."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from app.gamification.application.consent_gate import research_consent_granted
from app.gamification.application.ports import AuditOutput, ConsentStore
from app.gamification.application.records import AuditEvent
from app.gamification.domain.types import OutcomeValidity
from app.gamification.modeling.shared.artifact_registry import (
    ApprovalGatedArtifactRegistry,
    ManifestReference,
    ModelArtifactBundle,
)
from app.gamification.modeling.support_selection.context import BanditContext
from app.gamification.modeling.support_selection.learned_policy import (
    LinUCBPolicy,
    ThompsonSamplingPolicy,
)
from app.gamification.modeling.support_selection.offline_update import (
    MODEL_NAME,
    LoggedBanditDecision,
    fit_from_logged_decisions,
)
from app.gamification.modeling.support_selection.reward import IndependenceGainReward

# One child's latest action must not move the policy. Two is a provisional floor.
PROVISIONAL_MINIMUM_POLICY_BATCH = 2


@dataclass(frozen=True, slots=True)
class PolicyTrainingExample:
    episode_id: str
    learner_id: UUID
    decided_at: datetime
    context: BanditContext
    arm: str
    propensity: float
    validity: OutcomeValidity
    raw_gain: float | None


@dataclass(frozen=True, slots=True)
class PolicyUpdateResult:
    status: str
    artifact_sha256: str | None
    consumed_episode_ids: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]


class InMemoryPolicyTrainingLog:
    def __init__(self, examples: tuple[PolicyTrainingExample, ...] = ()) -> None:
        self._examples = list(examples)
        self.consumed: list[tuple[str, str | None, str | None]] = []

    def pending(self) -> tuple[PolicyTrainingExample, ...]:
        done = {episode_id for episode_id, _, _ in self.consumed}
        return tuple(example for example in self._examples if example.episode_id not in done)

    def mark(self, episode_id: str, *, artifact_sha256: str | None, reason: str | None) -> None:
        if any(episode_id == existing for existing, _, _ in self.consumed):
            return
        self.consumed.append((episode_id, artifact_sha256, reason))

    def latest_artifact_sha256(self) -> str | None:
        hashes = [digest for _, digest, _ in self.consumed if digest]
        return hashes[-1] if hashes else None


class InMemorySupportPolicySource:
    """Registers a draft beside the approved artifact and does not activate it."""

    def __init__(
        self, registry: ApprovalGatedArtifactRegistry, model_name: str = MODEL_NAME
    ) -> None:
        self._registry = registry
        self._model_name = model_name
        self.drafts: list[ModelArtifactBundle] = []

    def active_bundle(self) -> ModelArtifactBundle | None:
        return self._registry.active(self._model_name)

    def register_draft(self, artifact: ModelArtifactBundle) -> None:
        self._registry.register(artifact)
        if all(item.artifact_sha256 != artifact.artifact_sha256 for item in self.drafts):
            self.drafts.append(artifact)


class _DigestManifest:
    def __init__(self, digest: str) -> None:
        self.digest = digest
        self.synthetic = False


class UpdateSupportPolicy:
    def __init__(
        self,
        *,
        log: InMemoryPolicyTrainingLog,
        policies: InMemorySupportPolicySource,
        consent: ConsentStore,
        audit: AuditOutput,
        minimum_batch_size: int = PROVISIONAL_MINIMUM_POLICY_BATCH,
        seed: int,
        source_commit: str,
    ) -> None:
        if minimum_batch_size < 2:
            raise ValueError("a policy update cannot run on one episode")
        if not source_commit:
            raise ValueError("source_commit is required")
        self._log = log
        self._policies = policies
        self._consent = consent
        self._audit = audit
        self._minimum_batch_size = minimum_batch_size
        self._seed = seed
        self._source_commit = source_commit
        self._reward = IndependenceGainReward()

    def execute(self, at: datetime) -> PolicyUpdateResult:
        pending = self._log.pending()
        if not pending:
            return PolicyUpdateResult("unchanged", self._log.latest_artifact_sha256(), (), ())
        eligible: list[PolicyTrainingExample] = []
        skipped: list[tuple[str, str]] = []
        for example in pending:
            reason = self._skip_reason(example, at)
            if reason is None:
                eligible.append(example)
            else:
                skipped.append((example.episode_id, reason))
        if len(eligible) < self._minimum_batch_size:
            self._audit_event(
                "policy_update_skipped",
                ("BATCH_BELOW_MINIMUM",),
                at,
                {"eligible_count": len(eligible), "minimum_batch_size": self._minimum_batch_size},
            )
            return PolicyUpdateResult("batch_below_minimum", None, (), tuple(skipped))
        active = self._policies.active_bundle()
        if active is None:
            self._audit_event("policy_update_skipped", ("NO_APPROVED_ARTIFACT",), at, {})
            return PolicyUpdateResult("no_approved_artifact", None, (), tuple(skipped))
        artifact = self._fit(active, eligible)
        self._policies.register_draft(artifact)
        for example in eligible:
            self._log.mark(
                example.episode_id, artifact_sha256=artifact.artifact_sha256, reason=None
            )
        for episode_id, reason in skipped:
            self._log.mark(episode_id, artifact_sha256=None, reason=reason)
        self._audit_event(
            "policy_updated",
            ("POLICY_ARTIFACT_DRAFTED",),
            at,
            {
                "artifact_sha256": artifact.artifact_sha256,
                "episode_ids": ",".join(example.episode_id for example in eligible),
                "skipped": ",".join(f"{episode_id}:{reason}" for episode_id, reason in skipped),
            },
        )
        return PolicyUpdateResult(
            "drafted",
            artifact.artifact_sha256,
            tuple(example.episode_id for example in eligible),
            tuple(skipped),
        )

    def _skip_reason(self, example: PolicyTrainingExample, at: datetime) -> str | None:
        if not research_consent_granted(self._consent, example.learner_id, at):
            return "CONSENT_SCOPE_MISSING"
        if example.validity is not OutcomeValidity.VALID or example.raw_gain is None:
            return "INVALID_OUTCOME"
        return None

    def _fit(
        self, active: ModelArtifactBundle, eligible: list[PolicyTrainingExample]
    ) -> ModelArtifactBundle:
        policy = _restore(dict(active.parameters))
        episode_ids = sorted(example.episode_id for example in eligible)
        manifest: ManifestReference = _DigestManifest(_dataset_digest(episode_ids))
        decisions = [
            LoggedBanditDecision(
                learner_id=str(example.learner_id),
                decided_at=example.decided_at,
                context=example.context,
                arm=example.arm,
                propensity=example.propensity,
            )
            for example in eligible
        ]
        outcomes = [_OutcomeView(example.validity, example.raw_gain) for example in eligible]
        return fit_from_logged_decisions(
            decisions,
            outcomes,
            policy,
            reward=self._reward,
            train_learner_ids=[str(example.learner_id) for example in eligible],
            manifest=manifest,
            seed=self._seed,
            source_commit=self._source_commit,
        )

    def _audit_event(
        self,
        event_type: str,
        reason_codes: tuple[str, ...],
        at: datetime,
        metadata: Mapping[str, str | int | float | bool | None],
    ) -> None:
        self._audit.write(
            AuditEvent(
                event_type=event_type,
                subject_id=MODEL_NAME,
                occurred_at=at,
                reason_codes=reason_codes,
                metadata=metadata,
            )
        )


@dataclass(frozen=True, slots=True)
class _OutcomeView:
    validity: OutcomeValidity
    raw_gain: float | None


def _restore(parameters: dict[str, object]) -> LinUCBPolicy | ThompsonSamplingPolicy:
    algorithm = parameters.get("algorithm")
    if algorithm == "linucb":
        return LinUCBPolicy.from_parameters(parameters)
    if algorithm == "thompson_sampling":
        return ThompsonSamplingPolicy.from_parameters(parameters)
    raise ValueError("active artifact is not a supported bandit")


def _dataset_digest(episode_ids: list[str]) -> str:
    payload = ",".join(episode_ids).encode()
    return hashlib.sha256(payload).hexdigest()
