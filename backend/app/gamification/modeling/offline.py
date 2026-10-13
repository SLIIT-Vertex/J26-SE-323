"""Deterministic offline dataset, evaluation, artifact, and model-card utilities."""

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DEFAULT_PROTOTYPE_DATASET = Path(__file__).with_name("data") / "default_prototype_dataset.json"
DEFAULT_PROTOTYPE_STATUS = "TODO_EXPERT_AUTHORIZATION_AND_REVIEW"
FAKE_EXPERT_REVIEW_DATASET = (
    Path(__file__).with_name("data") / "fake_expert_reviewed_prototype_dataset.json"
)


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetRow:
    episode_id: str
    learner_id: str
    features: Mapping[str, float | int | bool | str | None]
    action_id: str
    reward: float | None
    propensity: float | None
    valid_outcome: bool
    label: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset_id: str
    schema_version: str
    source_sha256: str
    exclusion_rules: tuple[str, ...]
    split_seed: int
    learner_splits: Mapping[str, tuple[str, ...]]
    synthetic: bool

    @classmethod
    def build(
        cls,
        rows: Sequence[DatasetRow],
        *,
        dataset_id: str,
        split_seed: int,
        synthetic: bool,
    ) -> "DatasetManifest":
        learners = sorted({row.learner_id for row in rows})
        ranked = sorted(
            learners,
            key=lambda learner: hashlib.sha256(
                f"{split_seed}:{learner}".encode()
            ).hexdigest(),
        )
        train_end = math.ceil(len(ranked) * 0.6)
        validation_end = train_end + math.floor(len(ranked) * 0.2)
        splits = {
            "train": tuple(ranked[:train_end]),
            "validation": tuple(ranked[train_end:validation_end]),
            "test": tuple(ranked[validation_end:]),
        }
        manifest = cls(
            dataset_id=dataset_id,
            schema_version="offline-dataset-v1",
            source_sha256=sha256_digest([asdict(row) for row in rows]),
            exclusion_rules=("invalid_outcome", "missing_reward"),
            split_seed=split_seed,
            learner_splits=splits,
            synthetic=synthetic,
        )
        manifest.assert_no_learner_leakage()
        return manifest

    def assert_no_learner_leakage(self) -> None:
        groups = [set(values) for values in self.learner_splits.values()]
        if any(left & right for index, left in enumerate(groups) for right in groups[index + 1 :]):
            raise ValueError("a learner cannot occur in multiple dataset splits")

    @property
    def digest(self) -> str:
        return sha256_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    sample_count: int
    ips: float
    self_normalized_ips: float
    direct_method: float | None
    doubly_robust: float | None


@dataclass(frozen=True, slots=True)
class ClassificationEvaluation:
    sample_count: int
    accuracy: float
    brier_score: float
    expected_calibration_error: float
    abstention_rate: float
    slices: Mapping[str, Mapping[str, float | int]]


def evaluate_classification(
    records: Sequence[Mapping[str, object]], *, slice_field: str = "skill_id"
) -> ClassificationEvaluation:
    """Evaluate only supplied labels/probabilities; never manufactures missing evidence."""
    if not records:
        raise ValueError("classification evaluation requires labelled records")
    buckets: dict[str, list[bool]] = {}
    brier = 0.0
    calibration = 0.0
    correct = 0
    abstained = 0
    for record in records:
        label = str(record["label"])
        probabilities = dict(record["probabilities"])  # type: ignore[arg-type]
        if not probabilities or abs(sum(float(value) for value in probabilities.values()) - 1) > 1e-9:
            raise ValueError("evaluation probabilities must sum to one")
        predicted = max(probabilities, key=lambda code: float(probabilities[code]))
        confidence = float(probabilities[predicted])
        is_abstained = bool(record.get("abstained", False))
        is_correct = predicted == label and not is_abstained
        correct += is_correct
        abstained += is_abstained
        brier += sum(
            (float(probability) - (1.0 if code == label else 0.0)) ** 2
            for code, probability in probabilities.items()
        )
        calibration += abs(confidence - float(is_correct))
        buckets.setdefault(str(record.get(slice_field, "unknown")), []).append(is_correct)
    total = len(records)
    slices = {
        key: {"sample_count": len(values), "accuracy": sum(values) / len(values)}
        for key, values in sorted(buckets.items())
    }
    return ClassificationEvaluation(
        sample_count=total,
        accuracy=correct / total,
        brier_score=brier / total,
        expected_calibration_error=calibration / total,
        abstention_rate=abstained / total,
        slices=slices,
    )


def evaluate_logged_policy(
    rows: Iterable[DatasetRow],
    target_probabilities: Mapping[tuple[str, str], float],
) -> PolicyEvaluation:
    usable = [row for row in rows if row.valid_outcome and row.reward is not None]
    if any(row.propensity is None or row.propensity <= 0 for row in usable):
        raise ValueError("off-policy evaluation requires positive logged propensities")
    if not usable:
        raise ValueError("off-policy evaluation requires valid rewarded episodes")
    weights = [
        target_probabilities.get((row.episode_id, row.action_id), 0.0) / row.propensity
        for row in usable
    ]
    weighted_rewards = [weight * float(row.reward) for weight, row in zip(weights, usable)]
    total_weight = sum(weights)
    return PolicyEvaluation(
        sample_count=len(usable),
        ips=sum(weighted_rewards) / len(usable),
        self_normalized_ips=(sum(weighted_rewards) / total_weight if total_weight else 0.0),
        direct_method=None,
        doubly_robust=None,
    )


@dataclass(frozen=True, slots=True)
class ModelArtifactBundle:
    model_name: str
    model_version: str
    source_commit: str
    feature_definition_version: str
    dataset_manifest_digest: str
    seed: int
    parameters: Mapping[str, object]
    artifact_sha256: str

    @classmethod
    def create(
        cls,
        *,
        model_name: str,
        model_version: str,
        source_commit: str,
        feature_definition_version: str,
        manifest: DatasetManifest,
        seed: int,
        parameters: Mapping[str, object],
    ) -> "ModelArtifactBundle":
        payload = {
            "model_name": model_name,
            "model_version": model_version,
            "source_commit": source_commit,
            "feature_definition_version": feature_definition_version,
            "dataset_manifest_digest": manifest.digest,
            "seed": seed,
            "parameters": parameters,
        }
        return cls(**payload, artifact_sha256=sha256_digest(payload))

    def verify(self) -> None:
        payload = asdict(self)
        claimed = payload.pop("artifact_sha256")
        if sha256_digest(payload) != claimed:
            raise ValueError("artifact hash mismatch")


class ApprovalGatedArtifactRegistry:
    """Offline activation gate; candidates remain inactive until separately approved."""

    def __init__(self) -> None:
        self._registered: dict[str, ModelArtifactBundle] = {}
        self._active: dict[str, str] = {}
        self._approvals: dict[str, tuple[str, datetime]] = {}

    def register(self, artifact: ModelArtifactBundle) -> None:
        artifact.verify()
        self._registered[artifact.artifact_sha256] = artifact

    def activate(
        self,
        *,
        model_name: str,
        artifact_sha256: str,
        approved: bool,
        approver: str | None = None,
        approved_at: datetime | None = None,
    ) -> None:
        if not approved:
            raise PermissionError("unapproved artifacts cannot become active")
        if not approver or approved_at is None:
            raise ValueError("activation requires approver and approval timestamp")
        if approved_at.tzinfo is None or approved_at.utcoffset() is None:
            raise ValueError("approval timestamp must include a UTC offset")
        artifact = self._registered.get(artifact_sha256)
        if artifact is None or artifact.model_name != model_name:
            raise LookupError("registered artifact does not match model")
        self._active[model_name] = artifact_sha256
        self._approvals[artifact_sha256] = (approver, approved_at)

    def active(self, model_name: str) -> ModelArtifactBundle | None:
        digest = self._active.get(model_name)
        return self._registered.get(digest) if digest else None

    def rollback(
        self,
        *,
        model_name: str,
        artifact_sha256: str,
        approved: bool,
        approver: str | None = None,
        approved_at: datetime | None = None,
    ) -> None:
        self.activate(
            model_name=model_name,
            artifact_sha256=artifact_sha256,
            approved=approved,
            approver=approver,
            approved_at=approved_at,
        )


def model_card(artifact: ModelArtifactBundle, manifest: DatasetManifest) -> str:
    evidence = "synthetic engineering data only" if manifest.synthetic else "declared dataset"
    return "\n".join(
        (
            f"# Model card: {artifact.model_name} {artifact.model_version}",
            "",
            f"- Artifact SHA-256: `{artifact.artifact_sha256}`",
            f"- Dataset manifest: `{manifest.digest}`",
            f"- Feature definition: `{artifact.feature_definition_version}`",
            f"- Evidence: {evidence}",
            "- Approval: candidate only; registration does not authorize child-facing use",
            "- Limitations: calibration and subgroup validity require expert-labelled learner evidence",
        )
    )


def train_frequency_candidate(
    rows: Sequence[DatasetRow],
    *,
    manifest: DatasetManifest,
    model_name: str,
    model_version: str,
    source_commit: str,
    feature_definition_version: str,
    seed: int,
) -> ModelArtifactBundle:
    """Create a reproducible transparent baseline from the manifest's training learners."""
    manifest.assert_no_learner_leakage()
    train_learners = set(manifest.learner_splits["train"])
    labels = [row.label for row in rows if row.learner_id in train_learners and row.label]
    if not labels:
        raise ValueError("training split contains no supplied labels")
    counts = {label: labels.count(label) for label in sorted(set(labels))}
    total = len(labels)
    return ModelArtifactBundle.create(
        model_name=model_name,
        model_version=model_version,
        source_commit=source_commit,
        feature_definition_version=feature_definition_version,
        manifest=manifest,
        seed=seed,
        parameters={"class_priors": {label: count / total for label, count in counts.items()}},
    )


def _load_rows(path: Path) -> list[DatasetRow]:
    payload = json.loads(path.read_text())
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("dataset must be a list or an object containing a records list")
    return [DatasetRow(**row) for row in records]


def load_default_prototype_rows() -> list[DatasetRow]:
    """Load synthetic defaults; these rows are not authorized expert evidence."""
    return _load_rows(DEFAULT_PROTOTYPE_DATASET)


def load_fake_expert_reviews() -> dict[str, object]:
    """Load and validate the synthetic expert-review workflow fixture."""
    payload = json.loads(FAKE_EXPERT_REVIEW_DATASET.read_text())
    if not isinstance(payload, dict):
        raise ValueError("fake expert-review dataset must be an object")
    if payload.get("synthetic") is not True or payload.get("authorized_research_evidence") is not False:
        raise ValueError("fake expert-review dataset must remain synthetic and unauthorized")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fake expert-review dataset requires cases")
    required = {
        "reviewer_id",
        "expert_misconception_label",
        "alternative_plausible_label",
        "reason_for_label",
        "expert_confidence",
        "appropriate_support_actions",
        "inappropriate_support_actions",
    }
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("expert-review cases must be objects")
        reviews = case.get("independent_reviews")
        if not isinstance(reviews, list) or len(reviews) < 2:
            raise ValueError("each case requires at least two independent reviews")
        reviewers = set()
        for review in reviews:
            if not isinstance(review, dict) or not required <= set(review):
                raise ValueError("expert review is missing required fields")
            reviewers.add(review["reviewer_id"])
            if review["expert_confidence"] not in {"low", "medium", "high"}:
                raise ValueError("expert confidence must be low, medium, or high")
        if len(reviewers) != len(reviews):
            raise ValueError("independent reviews require distinct reviewer IDs")
        if not case.get("adjudicated_label"):
            raise ValueError("each fake case requires an adjudicated label")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline gamification model tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("dataset", type=Path)
    manifest_parser.add_argument("output", type=Path)
    manifest_parser.add_argument("--dataset-id", required=True)
    manifest_parser.add_argument("--seed", type=int, default=42)
    manifest_parser.add_argument("--synthetic", action="store_true")
    evaluate_parser = subparsers.add_parser("evaluate-classification")
    evaluate_parser.add_argument("predictions", type=Path)
    evaluate_parser.add_argument("output", type=Path)
    evaluate_parser.add_argument("--slice-field", default="skill_id")
    train_parser = subparsers.add_parser("train-candidate")
    train_parser.add_argument("dataset", type=Path)
    train_parser.add_argument("artifact", type=Path)
    train_parser.add_argument("model_card", type=Path)
    train_parser.add_argument("--dataset-id", required=True)
    train_parser.add_argument("--model-name", required=True)
    train_parser.add_argument("--model-version", required=True)
    train_parser.add_argument("--source-commit", required=True)
    train_parser.add_argument("--feature-version", required=True)
    train_parser.add_argument("--seed", type=int, default=42)
    train_parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "manifest":
        manifest = DatasetManifest.build(
            _load_rows(args.dataset),
            dataset_id=args.dataset_id,
            split_seed=args.seed,
            synthetic=args.synthetic,
        )
        args.output.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    elif args.command == "evaluate-classification":
        records = json.loads(args.predictions.read_text())
        report = evaluate_classification(records, slice_field=args.slice_field)
        args.output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
    elif args.command == "train-candidate":
        rows = _load_rows(args.dataset)
        manifest = DatasetManifest.build(
            rows,
            dataset_id=args.dataset_id,
            split_seed=args.seed,
            synthetic=args.synthetic,
        )
        artifact = train_frequency_candidate(
            rows,
            manifest=manifest,
            model_name=args.model_name,
            model_version=args.model_version,
            source_commit=args.source_commit,
            feature_definition_version=args.feature_version,
            seed=args.seed,
        )
        args.artifact.write_text(json.dumps(asdict(artifact), indent=2, sort_keys=True) + "\n")
        args.model_card.write_text(model_card(artifact, manifest) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
