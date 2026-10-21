from app.adaptive_tutor.application import TutorWorkflowStatus
from app.adaptive_tutor.application.orchestration import SYNTHETIC_DEMO_NOTICE
from app.adaptive_tutor.infrastructure.offline_pipeline import run_offline_pipeline


def test_controlled_offline_pipeline_covers_14_non_delivering_scenarios() -> None:
    results = run_offline_pipeline()
    by_name = {result.scenario: result for result in results}

    assert len(results) == 14
    assert [by_name[f"L{level}"].assistance_level for level in range(1, 6)] == [
        f"L{level}" for level in range(1, 6)
    ]
    assert by_name["L0_PRE_INTERACTION"].assistance_level == "L0"
    assert by_name["L6_SYNTHETIC_CURRICULUM"].assistance_level == "L6"
    assert by_name["L6_BLOCKED_NO_EVIDENCE"].status is (TutorWorkflowStatus.CURRICULUM_UNAVAILABLE)
    assert by_name["FAIL_THEN_REGENERATE"].draft_attempt_count == 2
    assert by_name["VERIFIER_INDETERMINATE"].status is (
        TutorWorkflowStatus.VERIFICATION_INDETERMINATE
    )
    assert by_name["UNSUPPORTED_LANGUAGE"].status is TutorWorkflowStatus.UNSUPPORTED_LANGUAGE
    assert by_name["SKILL_MAPPER_ABSTENTION"].status is (TutorWorkflowStatus.CLARIFICATION_REQUIRED)
    assert by_name["MISSING_CONTEXT"].status is TutorWorkflowStatus.CONTEXT_NOT_READY
    assert by_name["PROVIDER_FAILURE"].status is TutorWorkflowStatus.GENERATION_FAILED
    assert all(result.demonstration_notice == SYNTHETIC_DEMO_NOTICE for result in results)
