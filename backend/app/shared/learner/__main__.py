"""Explicitly name an existing learner; never invent an identity."""

import argparse
from uuid import UUID

from app.shared.database.session import SessionLocal
from app.shared.learner.repository import SqlAlchemyLearnerRepository
from app.shared.learner.service import LearnerService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["set-name"])
    parser.add_argument("learner", type=UUID)
    parser.add_argument("name")
    args = parser.parse_args()
    with SessionLocal() as session:
        learner = LearnerService(SqlAlchemyLearnerRepository(session)).set_name(
            args.learner, args.name
        )
        print(f"Named learner {learner.id}: {learner.display_name}")


if __name__ == "__main__":
    main()
