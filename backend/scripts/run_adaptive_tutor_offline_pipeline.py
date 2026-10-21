"""Print the controlled Adaptive Tutor offline research scenarios as JSON."""

import json

from app.adaptive_tutor.infrastructure.offline_pipeline import run_offline_pipeline


def main() -> None:
    print(
        json.dumps(
            [
                {
                    "scenario": result.scenario,
                    "status": result.status.value,
                    "assistance_level": result.assistance_level,
                    "draft_attempt_count": result.draft_attempt_count,
                    "demonstration_notice": result.demonstration_notice,
                }
                for result in run_offline_pipeline()
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
