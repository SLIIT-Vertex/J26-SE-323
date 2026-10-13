import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Mapping, Protocol


class ManifestReference(Protocol):
    digest: str
    synthetic: bool


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


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
        manifest: ManifestReference,
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
    """Keep offline candidates inactive until a separate approval is supplied."""

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


def model_card(artifact: ModelArtifactBundle, manifest: ManifestReference) -> str:
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
