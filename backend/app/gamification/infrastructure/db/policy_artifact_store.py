"""Persist a drafted support-policy artifact without changing the approved row."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.models import (
    ModelVersionModel,
    PolicyUpdateCursorModel,
)
from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle
from app.gamification.modeling.support_selection.offline_update import MODEL_NAME


class SqlAlchemyPolicyArtifactStore:
    def __init__(self, session: Session, model_name: str = MODEL_NAME) -> None:
        self._session = session
        self._model_name = model_name

    def active_bundle(self) -> ModelArtifactBundle | None:
        row = self._session.scalar(
            select(ModelVersionModel)
            .where(
                ModelVersionModel.model_name == self._model_name,
                ModelVersionModel.approval_status == "approved",
            )
            .order_by(ModelVersionModel.approved_at.desc())
        )
        if row is None:
            return None
        return _bundle_from_row(row)

    def register_draft(self, artifact: ModelArtifactBundle) -> None:
        artifact.verify()
        existing = self._session.scalar(
            select(ModelVersionModel).where(
                ModelVersionModel.artifact_sha256 == artifact.artifact_sha256
            )
        )
        if existing is not None:
            return
        self._session.add(
            ModelVersionModel(
                id=uuid4(),
                model_name=artifact.model_name,
                model_role="support_policy",
                semantic_version=f"{artifact.model_version}.{artifact.artifact_sha256[:12]}",
                artifact_uri=f"gamification://support-policy/{artifact.artifact_sha256}",
                artifact_sha256=artifact.artifact_sha256,
                feature_definition_version=artifact.feature_definition_version,
                training_dataset_id=artifact.dataset_manifest_digest,
                metrics_json=_payload(artifact),
                approval_status="draft",
                created_at=datetime.now(UTC),
            )
        )
        self._session.flush()


class SqlAlchemyPolicyUpdateCursor:
    def __init__(self, session: Session) -> None:
        self._session = session

    def mark(
        self,
        episode_id: object,
        *,
        artifact_sha256: str | None,
        reason: str | None,
        consumed_at: datetime,
    ) -> None:
        existing = self._session.get(PolicyUpdateCursorModel, episode_id)
        if existing is not None:
            return
        self._session.add(
            PolicyUpdateCursorModel(
                episode_id=episode_id,  # type: ignore[arg-type]
                artifact_sha256=artifact_sha256,
                reason_code=reason,
                consumed_at=consumed_at,
            )
        )
        self._session.flush()


def _payload(artifact: ModelArtifactBundle) -> dict[str, object]:
    return {
        "model_name": artifact.model_name,
        "model_version": artifact.model_version,
        "source_commit": artifact.source_commit,
        "feature_definition_version": artifact.feature_definition_version,
        "dataset_manifest_digest": artifact.dataset_manifest_digest,
        "seed": artifact.seed,
        "parameters": dict(artifact.parameters),
    }


def _bundle_from_row(row: ModelVersionModel) -> ModelArtifactBundle:
    payload = dict(row.metrics_json)
    bundle = ModelArtifactBundle(
        model_name=str(payload["model_name"]),
        model_version=str(payload["model_version"]),
        source_commit=str(payload["source_commit"]),
        feature_definition_version=str(payload["feature_definition_version"]),
        dataset_manifest_digest=str(payload["dataset_manifest_digest"]),
        seed=int(payload["seed"]),  # type: ignore[arg-type]
        parameters=dict(payload["parameters"]),  # type: ignore[arg-type]
        artifact_sha256=row.artifact_sha256,
    )
    bundle.verify()
    return bundle
