"""Remove a demo seed: only episodes tagged with that seed version, and what hangs off them."""

from __future__ import annotations

import base64
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, delete, select
from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.models import (
    LearnerEvidenceOutboxModel,
    LearningFlowEpisodeRunModel,
    LearningFlowProbeReservationModel,
    LearningRewardEntryModel,
)


def delete_seeded(
    session: Session, learner_id: UUID, seed_version: str, *, backup_directory: Path | None = None
) -> int:
    """Delete the learner's episodes tagged ``seed_version``. Events, help rounds and receipts
    cascade with them. Returns how many episodes were deleted."""

    runs = session.scalars(
        select(LearningFlowEpisodeRunModel).where(
            LearningFlowEpisodeRunModel.learner_id == learner_id
        )
    ).all()
    ids = [run.episode_id for run in runs if run.state_json.get("seed_source") == seed_version]
    if ids:
        # A complete database snapshot is written before any deletion, including dependent rows.
        # If the backup fails, the deletion never starts.
        metadata = MetaData()
        metadata.reflect(bind=session.connection())
        snapshot = {"created_at": datetime.now(UTC).isoformat(), "tables": {}}
        for table in metadata.sorted_tables:
            snapshot["tables"][table.name] = [
                dict(row) for row in session.execute(select(table)).mappings()
            ]
        directory = (
            backup_directory or Path(__file__).resolve().parents[4] / "private-notes/backups"
        )
        directory.mkdir(parents=True, exist_ok=True)
        output = (
            directory
            / f"before-demo-cleanup-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}.json.gz"
        )

        def encode(value):
            if isinstance(value, bytes):
                return {"base64": base64.b64encode(value).decode()}
            return str(value)

        with gzip.open(output, "xt", encoding="utf-8") as handle:
            json.dump(snapshot, handle, default=encode, ensure_ascii=False)
        output.chmod(0o600)
        seed_sessions = {
            UUID(
                str(run.state_json.get("learning_state_session_id") or run.state_json["session_id"])
            )
            for run in runs
            if run.episode_id in ids
        }
        state_table = metadata.tables.get("learner_skill_states")
        if state_table is not None:
            session.execute(
                delete(state_table).where(
                    state_table.c.learner_id == learner_id,
                    state_table.c.session_id.in_([str(s) for s in seed_sessions]),
                )
            )
        outbox = session.scalars(
            select(LearnerEvidenceOutboxModel).where(
                LearnerEvidenceOutboxModel.learner_id == learner_id
            )
        ).all()
        seed_ids = {str(value) for value in ids}
        for row in outbox:
            if str(row.payload_json.get("episode_id")) in seed_ids:
                session.delete(row)
        session.execute(
            delete(LearningFlowProbeReservationModel).where(
                LearningFlowProbeReservationModel.episode_id.in_(ids)
            )
        )
        session.execute(
            delete(LearningRewardEntryModel).where(LearningRewardEntryModel.episode_id.in_(ids))
        )
        session.execute(
            delete(LearningFlowEpisodeRunModel).where(
                LearningFlowEpisodeRunModel.episode_id.in_(ids)
            )
        )
        session.commit()
    return len(ids)
