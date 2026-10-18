"""Small local timing probe; it makes no production capacity claim."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
)
from app.gamification.infrastructure.db.learning_flow_gateways import (
    SqlAlchemyLearningFlowEvidencePublisher,
    SqlAlchemyProbeGateway,
)
from app.gamification.infrastructure.db.learning_flow_store import (
    SqlAlchemyLearningFlowStore,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=25)
    args = parser.parse_args()
    if args.episodes < 1 or args.episodes > 200:
        raise SystemExit("episodes must be between 1 and 200")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    latencies: list[float] = []
    started = time.perf_counter()
    with Session(engine) as session:
        for index in range(args.episodes):
            learner_id = uuid4()
            now = datetime.now(UTC)
            session.add(
                LearnerModel(
                    id=learner_id,
                    grade=5,
                    preferred_language="si",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            service = LearningFlowOrchestrator(
                SqlAlchemyLearningFlowStore(session),
                probe_gateway=SqlAlchemyProbeGateway(session),
                evidence_publisher=SqlAlchemyLearningFlowEvidencePublisher(session),
            )
            one = time.perf_counter()
            opened = service.open_episode(
                learner_id=learner_id,
                session_id=uuid4(),
                grade=5,
                medium="si",
                condition="proposed",
                environment="test",
                allow_draft=True,
                idempotency_key=f"load-{index}-open",
            )
            episode_id = UUID(str(opened["episode_id"]))
            service.submit_before(episode_id, option_id="A", idempotency_key=f"load-{index}-b")
            service.complete_support(
                episode_id,
                duration_ms=1,
                steps_viewed=1,
                idempotency_key=f"load-{index}-s",
            )
            service.withdraw_support(episode_id, idempotency_key=f"load-{index}-w")
            service.present_after(episode_id, idempotency_key=f"load-{index}-p")
            result = service.submit_after(
                episode_id, option_id="C", idempotency_key=f"load-{index}-a"
            )
            if result["status"] != "completed":
                raise RuntimeError("load fixture did not complete")
            service.reconstruct(episode_id)
            latencies.append((time.perf_counter() - one) * 1000)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "environment": "sqlite_in_memory_single_process_engineering_only",
                "episodes": args.episodes,
                "operations_per_episode": 7,
                "elapsed_seconds": round(elapsed, 6),
                "episode_latency_ms_mean": round(statistics.fmean(latencies), 3),
                "episode_latency_ms_p50": round(percentile(latencies, 0.50), 3),
                "episode_latency_ms_p95": round(percentile(latencies, 0.95), 3),
                "production_capacity_claim": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
