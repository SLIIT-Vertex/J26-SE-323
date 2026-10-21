"""python -m app.gamification.validation [--learners N]

Plays the simulated test learners through the real games and writes the validation report the
Research view shows. Safe to run again: sessions already played are reused.
"""

import argparse

from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.validation.simulated_cohort import (
    Assumptions,
    report,
    run_cohort,
    write_report,
)
from app.shared.database.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.gamification.validation")
    parser.add_argument("--learners", type=int, default=Assumptions.learners)
    args = parser.parse_args()
    assumptions = Assumptions(learners=args.learners)
    session = SessionLocal()
    try:
        result = run_cohort(session, get_learning_flow_orchestrator(session), assumptions)
        path = write_report(report(result, assumptions))
        print(f"{len(result.observations)} sessions, {result.skipped} not playable; report: {path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
