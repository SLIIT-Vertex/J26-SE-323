from collections.abc import Callable
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.grading.call_log import CallRecord
from app.knowledge_tracing.infrastructure.db.models import VisionCallModel


class SqlAlchemyVisionCallLog:
    """Stores every reader call. Each record gets its own session and commit, so a failure while
    grading cannot lose the record of a call that was already paid for."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def record(self, call: CallRecord) -> None:
        with self._session_factory() as session:
            session.add(
                VisionCallModel(
                    submission_id=call.submission_id,
                    paper_item_id=call.paper_item_id,
                    provider=call.provider,
                    model=call.model,
                    prompt_version=call.prompt_version,
                    role=call.role,
                    latency_ms=call.latency_ms,
                    tokens_in=call.tokens_in,
                    tokens_out=call.tokens_out,
                    http_status=call.http_status,
                    error_code=call.error_code,
                )
            )
            session.commit()


def usage_summary(session: Session, since: datetime) -> dict[str, dict]:
    """Calls, errors, tokens and mean latency per provider and model since a moment."""
    rows = session.execute(
        select(
            VisionCallModel.provider,
            VisionCallModel.model,
            func.count(),
            func.coalesce(func.sum(VisionCallModel.tokens_in), 0),
            func.coalesce(func.sum(VisionCallModel.tokens_out), 0),
            func.avg(VisionCallModel.latency_ms),
            func.coalesce(
                func.sum(case((VisionCallModel.error_code.is_not(None), 1), else_=0)), 0
            ),
        )
        .where(VisionCallModel.created_at >= since)
        .group_by(VisionCallModel.provider, VisionCallModel.model)
    ).all()
    return {
        f"{provider}/{model}": {
            "calls": int(calls),
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "mean_latency_ms": None if latency is None else round(float(latency)),
            "errors": int(errors),
        }
        for provider, model, calls, tokens_in, tokens_out, latency, errors in rows
    }
