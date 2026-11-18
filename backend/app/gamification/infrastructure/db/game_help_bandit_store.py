"""Persist the games' help-order bandits: approval, decision snapshots and the shared ledger.

Each subject's expert-initialised artifact is a ``model_versions`` row. It is registered as a draft
and approved once by the researcher; approving it retires the subject's previous artifact and
starts its learned state at ledger position 0. Learning appends to an ordered ledger under a row
lock, and the state can always be rebuilt from the artifact and the ledger.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.application.game_help_order import (
    ApprovedGameHelpBandit,
    StoredDecisionSnapshot,
)
from app.gamification.infrastructure.db.models import (
    GameHelpBanditLedgerModel,
    GameHelpBanditSnapshotModel,
    GameHelpBanditStateModel,
    LearningFlowEpisodeRunModel,
    ModelVersionModel,
)
from app.gamification.modeling.shared.expert_data import EXPERT_MODEL_DATA_VERSION
from app.gamification.modeling.support_selection.context import GAME_CONTEXT_VERSION
from app.gamification.modeling.support_selection.game_bandit import (
    GAME_POLICY_VERSION,
    GameHelpBandit,
)
from app.gamification.modeling.support_selection.game_bandit_ledger import (
    DecisionSnapshot,
    LedgerEntry,
    apply_entry,
    canonical_sha256,
    replay,
)


class GameHelpBanditStoreError(RuntimeError):
    pass


def model_name(subject: str) -> str:
    return f"game-help-order-bandit:{subject}"


@dataclass(frozen=True)
class GameHelpBanditDraft:
    model_version_id: UUID
    subject: str
    artifact_sha256: str
    approval_status: str


class SqlAlchemyGameHelpBanditStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Approval -------------------------------------------------------------------------

    def register_draft(self, bandit: GameHelpBandit, *, now: datetime) -> GameHelpBanditDraft:
        """Register the artifact as a draft. Registering the same artifact again changes nothing."""

        parameters = bandit.parameters()
        sha256 = canonical_sha256(parameters)
        row = self.session.scalar(
            select(ModelVersionModel).where(
                ModelVersionModel.model_name == model_name(bandit.subject),
                ModelVersionModel.artifact_sha256 == sha256,
            )
        )
        if row is None:
            row = ModelVersionModel(
                id=uuid4(),
                model_name=model_name(bandit.subject),
                model_role="support_policy",
                semantic_version=f"{GAME_POLICY_VERSION}.{sha256[:12]}",
                artifact_uri=f"gamification://game-help-order-bandit/{sha256}",
                artifact_sha256=sha256,
                feature_definition_version=GAME_CONTEXT_VERSION,
                training_dataset_id=EXPERT_MODEL_DATA_VERSION,
                metrics_json={"subject": bandit.subject, "parameters": parameters},
                approval_status="draft",
                created_at=now,
            )
            self.session.add(row)
            self.session.flush()
        return _draft(row)

    def approve(
        self, *, subject: str, artifact_sha256: str, approved_by: str, now: datetime
    ) -> GameHelpBanditDraft:
        """Approve one registered artifact; the subject's previously approved one is retired."""

        if not approved_by.strip():
            raise GameHelpBanditStoreError("APPROVER_REQUIRED")
        row = self.session.scalar(
            select(ModelVersionModel).where(
                ModelVersionModel.model_name == model_name(subject),
                ModelVersionModel.artifact_sha256 == artifact_sha256,
            )
        )
        if row is None:
            raise GameHelpBanditStoreError("ARTIFACT_NOT_REGISTERED")
        parameters = dict(row.metrics_json["parameters"])  # type: ignore[call-overload]
        if canonical_sha256(parameters) != artifact_sha256:
            raise GameHelpBanditStoreError("ARTIFACT_HASH_MISMATCH")
        if row.approval_status == "approved":
            return _draft(row)
        if row.approval_status != "draft":
            raise GameHelpBanditStoreError("ARTIFACT_NOT_A_DRAFT")
        for previous in self.session.scalars(
            select(ModelVersionModel).where(
                ModelVersionModel.model_name == model_name(subject),
                ModelVersionModel.approval_status == "approved",
            )
        ):
            previous.approval_status = "retired"
        row.approval_status = "approved"
        row.approved_by = approved_by
        row.approved_at = now
        self.session.add(
            GameHelpBanditStateModel(
                model_version_id=row.id,
                subject=subject,
                artifact_sha256=artifact_sha256,
                ledger_position=0,
                parameters_json=parameters,
                parameters_sha256=artifact_sha256,
                updated_at=now,
            )
        )
        self.session.flush()
        return _draft(row)

    # --- Deciding -------------------------------------------------------------------------

    def approved(self, subject: str) -> ApprovedGameHelpBandit | None:
        row = self.session.scalar(
            select(ModelVersionModel).where(
                ModelVersionModel.model_name == model_name(subject),
                ModelVersionModel.approval_status == "approved",
            )
        )
        if row is None:
            return None
        state = self._state(row.id)
        return ApprovedGameHelpBandit(
            model_version_id=row.id,
            artifact_sha256=row.artifact_sha256,
            ledger_position=state.ledger_position,
            bandit=GameHelpBandit.from_parameters(state.parameters_json),
        )

    def save_snapshot(
        self,
        *,
        episode_id: UUID,
        model_version_id: UUID,
        snapshot: DecisionSnapshot,
        now: datetime,
    ) -> UUID:
        record = snapshot.as_record()
        existing = self.session.scalar(
            select(GameHelpBanditSnapshotModel).where(
                GameHelpBanditSnapshotModel.episode_id == episode_id
            )
        )
        if existing is not None:
            if existing.snapshot_sha256 != canonical_sha256(record):
                raise GameHelpBanditStoreError("SNAPSHOT_CONFLICT")
            return existing.snapshot_id
        snapshot_id = uuid4()
        self.session.add(
            GameHelpBanditSnapshotModel(
                snapshot_id=snapshot_id,
                episode_id=episode_id,
                model_version_id=model_version_id,
                subject=snapshot.subject,
                context_version=snapshot.context_version,
                snapshot_json=record,
                snapshot_sha256=canonical_sha256(record),
                created_at=now,
            )
        )
        self.session.flush()
        return snapshot_id

    def snapshot_for(self, episode_id: UUID) -> StoredDecisionSnapshot | None:
        row = self.session.scalar(
            select(GameHelpBanditSnapshotModel).where(
                GameHelpBanditSnapshotModel.episode_id == episode_id
            )
        )
        return None if row is None else _stored_snapshot(row)

    # --- Learning -------------------------------------------------------------------------

    def apply(
        self,
        *,
        model_version_id: UUID,
        snapshot_id: UUID,
        entries: Sequence[LedgerEntry],
        now: datetime,
    ) -> int:
        """Apply one episode's observations once. Returns how many were applied (0 if already)."""

        if not entries:
            return 0
        if len({entry.episode_id for entry in entries}) != 1:
            raise GameHelpBanditStoreError("ONE_EPISODE_PER_UPDATE")
        state = self._state(model_version_id, for_update=True)
        episode_id = UUID(entries[0].episode_id)
        already = self.session.scalar(
            select(GameHelpBanditLedgerModel.position).where(
                GameHelpBanditLedgerModel.model_version_id == model_version_id,
                GameHelpBanditLedgerModel.episode_id == episode_id,
            )
        )
        if already is not None:
            return 0
        stored = _stored_snapshot(self._snapshot_row(snapshot_id))
        if stored.model_version_id != model_version_id:
            raise GameHelpBanditStoreError("SNAPSHOT_FROM_ANOTHER_ARTIFACT")
        if self._episode_of(snapshot_id) != episode_id:
            raise GameHelpBanditStoreError("SNAPSHOT_FROM_ANOTHER_EPISODE")
        bandit = GameHelpBandit.from_parameters(state.parameters_json)
        position = state.ledger_position
        for entry in entries:
            apply_entry(bandit, entry, stored.snapshot)
            position += 1
            self.session.add(
                GameHelpBanditLedgerModel(
                    model_version_id=model_version_id,
                    position=position,
                    episode_id=episode_id,
                    snapshot_id=snapshot_id,
                    help_type=entry.support,
                    role=entry.role,
                    score=entry.score,
                    weight=entry.weight,
                    credit_rule_version=entry.credit_rule_version,
                    applied_at=now,
                )
            )
        parameters = bandit.parameters()
        state.parameters_json = parameters
        state.parameters_sha256 = canonical_sha256(parameters)
        state.ledger_position = position
        state.updated_at = now
        self.session.flush()
        return len(entries)

    # --- Audit ----------------------------------------------------------------------------

    def ledger(self, model_version_id: UUID) -> tuple[tuple[int, LedgerEntry, UUID], ...]:
        rows = self.session.scalars(
            select(GameHelpBanditLedgerModel)
            .where(GameHelpBanditLedgerModel.model_version_id == model_version_id)
            .order_by(GameHelpBanditLedgerModel.position)
        ).all()
        return tuple(
            (
                row.position,
                LedgerEntry(
                    episode_id=str(row.episode_id),
                    support=row.help_type,
                    role=row.role,
                    score=row.score,
                    weight=row.weight,
                    credit_rule_version=row.credit_rule_version,
                ),
                row.snapshot_id,
            )
            for row in rows
        )

    def rebuild(self, model_version_id: UUID) -> GameHelpBandit:
        """The approved artifact with the whole ledger applied in order."""

        artifact = self.session.get(ModelVersionModel, model_version_id)
        if artifact is None:
            raise GameHelpBanditStoreError("ARTIFACT_NOT_REGISTERED")
        rows = self.ledger(model_version_id)
        if [position for position, _, _ in rows] != list(range(1, len(rows) + 1)):
            raise GameHelpBanditStoreError("LEDGER_GAP")
        snapshots: dict[UUID, DecisionSnapshot] = {}
        for _, _, snapshot_id in rows:
            if snapshot_id not in snapshots:
                snapshots[snapshot_id] = _stored_snapshot(self._snapshot_row(snapshot_id)).snapshot
        return replay(
            artifact.metrics_json["parameters"],  # type: ignore[arg-type]
            ((entry, snapshots[snapshot_id]) for _, entry, snapshot_id in rows),
        )

    def replay_matches(self, model_version_id: UUID) -> bool:
        """Whether rebuilding from artifact and ledger gives exactly the stored state."""

        state = self._state(model_version_id)
        return canonical_sha256(self.rebuild(model_version_id).parameters()) == (
            state.parameters_sha256
        )

    def snapshot_matches_its_inputs(self, snapshot_id: UUID, bandit: GameHelpBandit) -> bool:
        """Whether recomputing the vectors from the stored inputs gives the stored vectors."""

        stored = _stored_snapshot(self._snapshot_row(snapshot_id)).snapshot
        inputs = stored.inputs
        ids = [UUID(str(value)) for value in inputs["history_episode_ids"]]  # type: ignore[union-attr]
        runs = {
            row.episode_id: dict(row.state_json)
            for row in self.session.scalars(
                select(LearningFlowEpisodeRunModel).where(
                    LearningFlowEpisodeRunModel.episode_id.in_(ids)
                )
            )
        }
        if set(runs) != set(ids):
            return False
        history = [runs[episode_id] for episode_id in ids]
        for support, vector in stored.vectors.items():
            context = bandit.context(
                support,
                reason_family=str(inputs["reason_family"]),
                model1_uncertain=bool(inputs["model1_uncertain"]),
                learning_state=str(inputs["learning_state"]),
                history=history,
            )
            recomputed = {
                name: value
                for name, value in zip(context.names, context.values, strict=True)
                if value != 0.0
            }
            if recomputed != dict(vector):
                return False
        return True

    # --- Rows -----------------------------------------------------------------------------

    def _state(
        self, model_version_id: UUID, *, for_update: bool = False
    ) -> GameHelpBanditStateModel:
        statement = select(GameHelpBanditStateModel).where(
            GameHelpBanditStateModel.model_version_id == model_version_id
        )
        if for_update and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        state = self.session.scalar(statement)
        if state is None:
            raise GameHelpBanditStoreError("NO_LEARNED_STATE")
        if canonical_sha256(state.parameters_json) != state.parameters_sha256:
            raise GameHelpBanditStoreError("STATE_HASH_MISMATCH")
        return state

    def _snapshot_row(self, snapshot_id: UUID) -> GameHelpBanditSnapshotModel:
        row = self.session.get(GameHelpBanditSnapshotModel, snapshot_id)
        if row is None:
            raise GameHelpBanditStoreError("SNAPSHOT_NOT_FOUND")
        return row

    def _episode_of(self, snapshot_id: UUID) -> UUID:
        return self._snapshot_row(snapshot_id).episode_id


def _draft(row: ModelVersionModel) -> GameHelpBanditDraft:
    return GameHelpBanditDraft(
        model_version_id=row.id,
        subject=str(row.metrics_json["subject"]),
        artifact_sha256=row.artifact_sha256,
        approval_status=row.approval_status,
    )


def _stored_snapshot(row: GameHelpBanditSnapshotModel) -> StoredDecisionSnapshot:
    if canonical_sha256(row.snapshot_json) != row.snapshot_sha256:
        raise GameHelpBanditStoreError("SNAPSHOT_HASH_MISMATCH")
    return StoredDecisionSnapshot(
        snapshot_id=row.snapshot_id,
        model_version_id=row.model_version_id,
        snapshot=DecisionSnapshot.from_record(row.snapshot_json),
    )
