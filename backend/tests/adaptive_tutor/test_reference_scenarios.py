import json
from pathlib import Path

from app.adaptive_tutor.application import ScaffoldingController, TutoringContext
from app.adaptive_tutor.domain import AssistanceLevel

SCENARIO_FILE = (
    Path(__file__).parents[2]
    / "app"
    / "adaptive_tutor"
    / "application"
    / "reference_scenarios.json"
)


def test_reference_scenarios_conform_to_input_contract() -> None:
    document = json.loads(SCENARIO_FILE.read_text())
    scenarios = document["scenarios"]

    assert document["policy_version"] == "reference-policy-v1"
    assert "not experimentally validated" in document["status"]
    assert len(scenarios) == 20
    assert len({scenario["scenario_id"] for scenario in scenarios}) == 20
    assert {scenario["skill_id"] for scenario in scenarios} == {
        "APT-LOG",
        "MAT-FRC",
        "MAT-OPS",
        "MAT-TIM",
    }

    context_fields = set(TutoringContext.model_fields)
    for scenario in scenarios:
        TutoringContext.model_validate(
            {field: scenario[field] for field in context_fields}
        )
        AssistanceLevel(scenario["expected_assistance_level"])
        assert scenario["justification"].strip()


def test_reference_scenarios_cover_every_assistance_level() -> None:
    document = json.loads(SCENARIO_FILE.read_text())
    represented_levels = {
        scenario["expected_assistance_level"] for scenario in document["scenarios"]
    }

    assert represented_levels == {level.value for level in AssistanceLevel}


def test_controller_conforms_to_reference_policy_v1_scenarios() -> None:
    """Regression test for design-defined policy labels, not learner-outcome validation."""
    document = json.loads(SCENARIO_FILE.read_text())
    context_fields = set(TutoringContext.model_fields)
    controller = ScaffoldingController()

    for scenario in document["scenarios"]:
        context = TutoringContext.model_validate(
            {field: scenario[field] for field in context_fields}
        )

        decision = controller.decide(context)

        assert decision.assistance_level == AssistanceLevel(
            scenario["expected_assistance_level"]
        ), scenario["scenario_id"]
