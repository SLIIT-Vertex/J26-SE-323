"""Demo seed for the shared development learner.

    python -m app.gamification.demo_seed plan    [--file demo_seeds/shared_learner_demo_v1.yaml]
    python -m app.gamification.demo_seed seed    [--file ...]
    python -m app.gamification.demo_seed verify  [--file ...] [--json]
    python -m app.gamification.demo_seed cleanup [--file ...] --yes

`seed` plays the scripted child through the real models; `verify` re-checks every model from the
stored episodes; `cleanup` deletes only episodes tagged with the file's seed version.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from uuid import UUID

from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.demo_seed.cleanup import delete_seeded
from app.gamification.demo_seed.plan import build_plan, load_config
from app.gamification.demo_seed.runner import SeedRunner, multi_help_areas
from app.gamification.demo_seed.verify import verify
from app.shared.database.session import SessionLocal

DEFAULT_FILE = Path(__file__).resolve().parents[3] / "demo_seeds" / "shared_learner_demo_v1.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.gamification.demo_seed")
    parser.add_argument("command", choices=("plan", "seed", "verify", "cleanup", "checklist"))
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--json", action="store_true", help="verify: print the checks as JSON")
    parser.add_argument("--yes", action="store_true", help="cleanup: confirm the deletion")
    parser.add_argument(
        "--allow-demo-learner",
        action="store_true",
        help="Explicitly permit scripted rehearsal on the protected demo learner",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[4] / "private-notes/demo-play-checklist.md",
    )
    args = parser.parse_args(argv)
    config = load_config(args.file)
    session = SessionLocal()
    try:
        orchestrator = get_learning_flow_orchestrator(session)
        plan = build_plan(config, multi_help_areas(orchestrator))
        learner = UUID(plan.learner_id)
        if args.command == "checklist":
            from app.gamification.demo_seed.checklist import save_checklist

            print(save_checklist(session, orchestrator, learner, args.output))
            return 0
        if args.command == "plan":
            for skill in plan.skills:
                print(
                    f"{skill.area_id}  {skill.skill_id:34} {skill.pattern:28} "
                    f"aim={skill.target_family:14} episodes={len(skill.episodes)}"
                )
            patterns = Counter(skill.pattern for skill in plan.skills)
            print(f"\n{len(plan.skills)} skills, {plan.episode_count} episodes; {dict(patterns)}")
            return 0
        if args.command == "seed":
            if (
                str(learner) == "00000000-0000-4000-8000-000000000721"
                and not args.allow_demo_learner
            ):
                print(
                    "Refusing to script the demo learner. Use a rehearsal database, or explicitly pass --allow-demo-learner."
                )
                return 2
            report = SeedRunner(orchestrator, plan).run()
            print(
                f"played {report.played}, already seeded {report.already_seeded}, "
                f"item pool exhausted {len(report.pool_exhausted)}, failed {len(report.failed)}"
            )
            for label in report.pool_exhausted:
                print(f"  pool exhausted (Model 3 never reuses an after-item): {label}")
            for failure in report.failed:
                print(f"  FAILED {failure}")
            hit = sum(1 for aim, got in report.families.values() if aim == got)
            if report.families:
                print(
                    f"Model 1 reason family reached as aimed: {hit}/{len(report.families)} "
                    "(the rest: the game's scorer has no such error for that item)"
                )
            return 1 if report.failed else 0
        if args.command == "verify":
            checks = verify(
                session,
                orchestrator,
                learner,
                expected_skills=[skill.skill_id for skill in plan.skills],
                seed_version=plan.version,
            )
            if args.json:
                print(
                    json.dumps(
                        [check.as_record() for check in checks], ensure_ascii=False, indent=2
                    )
                )
            else:
                for check in checks:
                    print(
                        f"{'PASS' if check.passed else 'FAIL'}  [{check.model}] {check.name}"
                        f"  ({check.checked} checked)"
                    )
                    if check.detail:
                        print(f"        {check.detail}")
                    for failure in check.failures[:10]:
                        print(f"        ✗ {failure}")
                failed = sum(not check.passed for check in checks)
                print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
            return 0 if all(check.passed for check in checks) else 1
        if not args.yes:
            print("cleanup deletes every episode tagged", plan.version, "— rerun with --yes")
            return 2
        print(f"deleted {delete_seeded(session, learner, plan.version)} seeded episodes")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
