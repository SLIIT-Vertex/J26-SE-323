import json
from pathlib import Path

from app.gamification.modeling.offline.dataset_manifest import DatasetRow

_DATA_DIRECTORY = Path(__file__).with_name("data")
DEFAULT_PROTOTYPE_DATASET = _DATA_DIRECTORY / "default_prototype_dataset.json"
DEFAULT_PROTOTYPE_STATUS = "TODO_EXPERT_AUTHORIZATION_AND_REVIEW"
FAKE_EXPERT_REVIEW_DATASET = _DATA_DIRECTORY / "fake_expert_reviewed_prototype_dataset.json"


def load_dataset_rows(path: Path) -> list[DatasetRow]:
    payload = json.loads(path.read_text())
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("dataset must be a list or an object containing a records list")
    return [DatasetRow(**row) for row in records]


def load_default_prototype_rows() -> list[DatasetRow]:
    """Load synthetic defaults; these rows are not authorized expert evidence."""

    return load_dataset_rows(DEFAULT_PROTOTYPE_DATASET)


def load_fake_expert_reviews() -> dict[str, object]:
    """Load and validate the synthetic expert-review workflow fixture."""

    payload = json.loads(FAKE_EXPERT_REVIEW_DATASET.read_text())
    if not isinstance(payload, dict):
        raise ValueError("fake expert-review dataset must be an object")
    if payload.get("synthetic") is not True or payload.get("authorized_research_evidence") is not False:
        raise ValueError("fake expert-review dataset must remain synthetic and unauthorized")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fake expert-review dataset requires cases")
    required = {
        "reviewer_id",
        "expert_misconception_label",
        "alternative_plausible_label",
        "reason_for_label",
        "expert_confidence",
        "appropriate_support_actions",
        "inappropriate_support_actions",
    }
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("expert-review cases must be objects")
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
        if len(reviewers) != len(reviews):
            raise ValueError("independent reviews require distinct reviewer IDs")
        if not case.get("adjudicated_label"):
            raise ValueError("each fake case requires an adjudicated label")
    return payload
