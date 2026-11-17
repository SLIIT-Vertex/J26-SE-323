"""The games' Bayesian misconception model reproduces the frozen rule-based beliefs exactly.

Every comparison is against the reference fixtures, never against the rules themselves.
"""

import json
import shutil
from pathlib import Path

import pytest

from app.gamification.application.engine.area_flow import _model1_label, _model1_uncertain
from app.gamification.application.learning_flow_orchestration import GAME_FLOW_TYPES
from app.gamification.modeling.misconception_inference.bayesian_model import (
    GAME_FACTOR_WEIGHTS,
    GAME_MODEL_VERSION,
    BayesianMisconceptionModel,
)
from app.gamification.modeling.misconception_inference.expert_tables import (
    EXPERT_MODEL_DATA_DIRECTORY,
    load_game_misconception_model,
)
from app.gamification.modeling.misconception_inference.game_belief import learner_answer_window
from app.gamification.modeling.offline import DatasetManifest, DatasetRow
from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle

FIXTURES = Path(__file__).parents[2] / "fixtures"
BELIEFS = json.loads((FIXTURES / "rule_based_beliefs.json").read_text(encoding="utf-8"))
AREAS = {area["area_id"]: area for area in BELIEFS["areas"]}
SKILLS = {flow_type.area_id: tuple(flow_type.skills) for flow_type in GAME_FLOW_TYPES}
FAMILIES = json.loads(
    (EXPERT_MODEL_DATA_DIRECTORY / "reason_families.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def models() -> dict[str, BayesianMisconceptionModel]:
    return {area_id: load_game_misconception_model(area_id, SKILLS[area_id]) for area_id in AREAS}


def _predict(model, record, *, input_name=None, **changes):
    area = AREAS[record["area_id"]]
    given = area["inputs"][input_name or record["input"]]
    arguments = {
        "skill_id": SKILLS[record["area_id"]][0],
        "error_code": record["error_code"],
        "response_time_ms": given["response_time_ms"],
        "interaction_summary": given["interaction_summary"],
        "prior_window": record.get("prior_window", ()),
    }
    arguments.update(changes)
    return model.predict_game_belief(**arguments)


def test_every_frozen_belief_is_reproduced(models) -> None:
    for record in BELIEFS["game_belief"] + BELIEFS["learner_prior"]:
        belief = _predict(models[record["area_id"]], record)
        codes = AREAS[record["area_id"]]["codes"]
        probabilities = [belief["probabilities"][code] for code in codes]
        assert probabilities == pytest.approx(record["belief"]["probabilities"], abs=1e-9)
        assert sum(probabilities) == pytest.approx(1)
        # What Model 2 reads must agree exactly, with no tolerance on a threshold.
        assert _model1_label(belief) == record["model1_label"], record
        assert _model1_uncertain(belief) is record["model1_uncertain"], record
        assert belief["fallback_used"] is (belief["evidence_band"] in {"sparse", "low_quality"})
        subject = AREAS[record["area_id"]]["subject"]
        expected_family = FAMILIES["subjects"][subject]["labels"][belief["predicted_label"]]
        assert belief["reason_family"] == expected_family["reason_family"]


def test_sinhala_ignores_response_time(models) -> None:
    for record in BELIEFS["game_belief"]:
        if record["input"] != "no_interaction_signal":
            continue
        model = models[record["area_id"]]
        assert _predict(model, record) == _predict(model, record, input_name="no_response_time")


def test_motor_evidence_yields_to_a_clear_learner_history(models) -> None:
    # Motor difficulty only weakens the answer's evidence. Alone it leaves the reading uncertain;
    # a history of the same unaided mistake can still make it clear, as the games do today.
    area_id = "G5-AREA-SIN-03"
    codes = [code for code in AREAS[area_id]["codes"] if code != "unknown_or_other"]
    arguments = {
        "skill_id": SKILLS[area_id][0],
        "error_code": codes[0],
        "response_time_ms": 4000,
        "interaction_summary": {"correction_count": 3},
    }
    alone = models[area_id].predict_game_belief(**arguments)
    with_history = models[area_id].predict_game_belief(**arguments, prior_window=[codes[0]] * 4)
    assert alone["evidence_band"] == with_history["evidence_band"] == "motor"
    assert _model1_uncertain(alone) is True
    assert _model1_uncertain(with_history) is False
    assert with_history["fallback_used"] is False
    rendering = models[area_id].predict_game_belief(
        **{**arguments, "interaction_summary": {"rendering_issue_reported": True}},
        prior_window=[codes[0]] * 4,
    )
    assert "unknown_top" in rendering["uncertain_because"]


def test_answer_window_matches_every_frozen_window() -> None:
    for record in BELIEFS["learner_prior"]:
        history = AREAS[record["area_id"]]["prior_histories"][record["history"]]
        window = learner_answer_window(history, size=BELIEFS["learner_prior_cap"])
        assert list(window) == record["prior_window"]


def test_supported_answers_never_enter_the_prior(models) -> None:
    area_id = "G5-AREA-MAT-02"
    code = AREAS[area_id]["codes"][0]
    supported = {"role": "supported_practice", "assistance_state": "active", "correct": False}
    aided_after = {"role": "unsupported_after", "assistance_state": "active", "correct": False}
    history = [{"attempts": [{**supported, "structured_error_code": code}] * 3}]
    history.append({"attempts": [{**aided_after, "structured_error_code": code}]})
    assert learner_answer_window(history, size=5) == ()
    model = models[area_id]
    plain = model.predict_game_belief(
        skill_id=SKILLS[area_id][0],
        error_code=code,
        response_time_ms=4000,
        interaction_summary={"first_action_ms": 800},
        prior_window=learner_answer_window(history, size=5),
    )
    assert plain["learner_prior_used"] is False
    assert plain["prior_sample_size"] == 0


def test_missing_error_code_is_skipped_and_named(models) -> None:
    area_id = "G5-AREA-ENG-01"
    belief = models[area_id].predict_game_belief(
        skill_id=SKILLS[area_id][0],
        error_code=None,
        response_time_ms=4000,
        interaction_summary={},
    )
    assert belief["factors"]["structured_error"] == "missing"
    assert belief["likelihood"] is None
    assert sum(belief["probabilities"].values()) == pytest.approx(1)
    assert len(set(belief["probabilities"].values())) == 1


def test_switched_off_factors_change_nothing_until_switched_on() -> None:
    area_id = "G5-AREA-MAT-07"
    model = load_game_misconception_model(area_id, SKILLS[area_id])
    skill = SKILLS[area_id][0]
    codes = AREAS[area_id]["codes"]
    favour = {code: 4.0 if code == codes[0] else 1.0 for code in codes}
    model.attempt_likelihoods[skill] = {"1": favour, "2": favour, "3_plus": favour}
    model.response_time_likelihoods[skill] = {"fast": favour, "typical": favour, "slow": favour}
    model.support_need_likelihoods[skill] = {"low": favour, "elevated": favour}
    arguments = {
        "skill_id": skill,
        "error_code": codes[1],
        "response_time_ms": 4000,
        "interaction_summary": {},
    }
    plain = model.predict_game_belief(**arguments)
    with_evidence = model.predict_game_belief(
        **arguments, attempt_count=3, response_time_ratio=2.0, support_need=0.9
    )
    assert with_evidence["probabilities"] == plain["probabilities"]
    assert {with_evidence["factors"][name] for name in ("attempt_count", "support_need")} == {"off"}

    model.factor_weights["attempt_count"] = 1.0
    switched_on = model.predict_game_belief(**arguments, attempt_count=3)
    assert switched_on["factors"]["attempt_count"] == "matched"
    assert switched_on["probabilities"][codes[0]] > plain["probabilities"][codes[0]]


def test_game_model_records_its_settings() -> None:
    area_id = "G5-AREA-SIN-02"
    parameters = load_game_misconception_model(area_id, SKILLS[area_id]).to_parameters()
    assert parameters["model_version"] == GAME_MODEL_VERSION
    assert parameters["factor_weights"] == dict(sorted(GAME_FACTOR_WEIGHTS.items()))
    game = parameters["game"]
    assert game["uncertainty_rule"]["abstain_threshold_used"] is False
    assert game["uncertainty_rule"]["top_probability_below"] == 0.4
    assert game["evidence_status"] == "provisional_expert_assumption"
    assert set(game["file_sha256"]) == {
        f"misconception_tables/{area_id}.json",
        "misconception_settings.json",
        "reason_families.json",
    }


def test_game_model_survives_the_artifact_round_trip(models) -> None:
    area_id = "G5-AREA-MAT-04"
    model = models[area_id]
    manifest = DatasetManifest.build(
        [DatasetRow("episode", "learner", {"skill_id": "s"}, "action", None, None, False)],
        dataset_id="expert-game-tables",
        split_seed=1,
        synthetic=True,
    )
    artifact = ModelArtifactBundle.create(
        model_name="misconception-bayesian",
        model_version=GAME_MODEL_VERSION,
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v2",
        manifest=manifest,
        seed=7,
        parameters=model.to_parameters(),
    )
    restored = BayesianMisconceptionModel.from_artifact(artifact)
    for record in BELIEFS["game_belief"]:
        if record["area_id"] == area_id:
            assert _predict(restored, record) == _predict(model, record)


def test_loader_refuses_a_table_that_does_not_match_its_hash(tmp_path) -> None:
    copy = tmp_path / "v1"
    shutil.copytree(EXPERT_MODEL_DATA_DIRECTORY, copy)
    table = copy / "misconception_tables" / "G5-AREA-ENG-05.json"
    table.write_text(table.read_text(encoding="utf-8").replace("0.", "0.0", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest hash"):
        load_game_misconception_model("G5-AREA-ENG-05", SKILLS["G5-AREA-ENG-05"], directory=copy)
    with pytest.raises(KeyError):
        load_game_misconception_model("G5-AREA-ENV-01", ["s"], directory=copy)
