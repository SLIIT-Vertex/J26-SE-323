import json
import os
from pathlib import Path

from app.gamification.domain.types import SupportActionType
from app.gamification.modeling.offline.dataset_manifest import DatasetRow

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
GAMIFICATION_DATA_DIRECTORY = Path(
    os.environ.get("MINDBRIDGE_GAMIFICATION_DATA_DIR", _PROJECT_ROOT / "data" / "gamification")
).expanduser().resolve()
SYNTHETIC_MODEL_DATA_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "synthetic-model-data" / "v1"
DEFAULT_PROTOTYPE_EPISODES = SYNTHETIC_MODEL_DATA_DIRECTORY / "default-prototype-episodes.json"
DEFAULT_PROTOTYPE_STATUS = "TODO_EXPERT_AUTHORIZATION_AND_REVIEW"
EXPERT_REVIEW_SIMULATION = SYNTHETIC_MODEL_DATA_DIRECTORY / "expert-review-simulation.json"


def load_dataset_rows(path: Path) -> list[DatasetRow]:
    if path.resolve() == EXPERT_REVIEW_SIMULATION.resolve():
        return load_fake_expert_review_rows()
    payload = json.loads(path.read_text())
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("dataset must be a list or an object containing a records list")
    return [DatasetRow(**row) for row in records]


def load_default_prototype_rows() -> list[DatasetRow]:
    """Load synthetic defaults; these rows are not authorized expert evidence."""

    return load_dataset_rows(DEFAULT_PROTOTYPE_EPISODES)


def load_fake_expert_review_simulation() -> dict[str, object]:
    """Load and validate the realistic synthetic expert-review fallback."""

    payload = json.loads(EXPERT_REVIEW_SIMULATION.read_text())
    if not isinstance(payload, dict):
        raise ValueError("fake expert-review simulation must be an object")
    if payload.get("synthetic") is not True or payload.get("authorized_research_evidence") is not False:
        raise ValueError("fake expert-review simulation must remain synthetic and unauthorized")
    if payload.get("schema_version") != "fake-expert-review-simulation-v2":
        raise ValueError("unsupported fake expert-review simulation schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fake expert-review simulation requires cases")
    required = {
        "reviewer_id",
        "expert_misconception_label",
        "alternative_plausible_label",
        "reason_for_label",
        "expert_confidence",
        "appropriate_support_actions",
        "inappropriate_support_actions",
    }
    required_case_fields = {
        "case_id",
        "item_id",
        "game_id",
        "subject",
        "language",
        "provisional_skill_id",
        "question_item",
        "synthetic_learner_observation",
        "model_record",
        "adjudicated_label",
        "adjudication_reason",
    }
    allowed_support_actions = {action.value for action in SupportActionType}
    case_ids: set[str] = set()
    episode_ids: set[str] = set()
    learner_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not required_case_fields <= set(case):
            raise ValueError("expert-review case is missing required fields")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or case_id in case_ids:
            raise ValueError("expert-review cases require unique string IDs")
        case_ids.add(case_id)
        reviews = case.get("independent_reviews")
        if not isinstance(reviews, list) or len(reviews) < 2:
            raise ValueError("each case requires at least two independent reviews")
        reviewers = set()
        for review in reviews:
            if not isinstance(review, dict) or not required <= set(review):
                raise ValueError("expert review is missing required fields")
            reviewers.add(review["reviewer_id"])
            if review["expert_confidence"] not in {"low", "medium", "high"}:
                raise ValueError("expert confidence must be low, medium, or high")
            support_actions = set(review["appropriate_support_actions"]) | set(
                review["inappropriate_support_actions"]
            )
            if not support_actions <= allowed_support_actions:
                raise ValueError("expert review contains an unsupported action type")
        if len(reviewers) != len(reviews):
            raise ValueError("independent reviews require distinct reviewer IDs")
        if not case.get("adjudicated_label"):
            raise ValueError("each fake case requires an adjudicated label")
        model_record = case["model_record"]
        if not isinstance(model_record, dict):
            raise ValueError("each fake case requires a model-ready record")
        row = DatasetRow(**model_record)
        if row.label != case["adjudicated_label"]:
            raise ValueError("model record label must match the adjudicated label")
        if not row.learner_id.startswith("synthetic-expert-sim-"):
            raise ValueError("fake expert-review learners must be explicitly synthetic")
        if row.features.get("item_id") != case["item_id"]:
            raise ValueError("model record item must match the reviewed case")
        if row.episode_id in episode_ids or row.learner_id in learner_ids:
            raise ValueError("model-ready episode and learner IDs must be unique")
        episode_ids.add(row.episode_id)
        learner_ids.add(row.learner_id)
    return payload


def load_fake_expert_review_rows() -> list[DatasetRow]:
    """Return model-ready rows from the validated synthetic review simulation."""

    payload = load_fake_expert_review_simulation()
    return [DatasetRow(**case["model_record"]) for case in payload["cases"]]  # type: ignore[index]
