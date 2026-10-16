"""
Generate reference predictions from real XGBoost for the learner-state model loader tests.

The backend evaluates the committed XGBoost JSON models with its own tree evaluator
(backend/app/learner_state/infrastructure/model_loader.py) and no longer depends on XGBoost.
This script records what XGBoost itself predicts, so the tests can prove the evaluator matches it.

Inputs per model:
- "boundary": values placed exactly on and next to the model's own split thresholds, where a
  float32/float64 mismatch would send a sample down the wrong branch;
- "realistic": values built with the backend feature builder from synthetic learner sessions
  (behaviour models) or plausible derived visual features (visual models).

Run from the repository root with a Python environment that has numpy and xgboost installed
(XGBoost is not a backend dependency):

    python research/learner-state/tools/generate_model_reference_predictions.py

No learner, participant or dataset rows are used.
"""

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.learner_state.infrastructure.feature_builder import (
    BehaviorObservation,
    build_confusion_behavior_features,
    build_disengagement_behavior_features,
)

MODEL_DIRECTORY = ROOT / "backend/app/learner_state/infrastructure/models"
OUTPUT = ROOT / "backend/tests/learner_state/fixtures/model_reference_predictions.json"
ROWS_PER_KIND = 150


def feature_names(path: Path) -> list[str]:
    return json.loads(path.read_text(encoding="utf-8"))["learner"]["feature_names"]


def split_thresholds(path: Path) -> dict[int, list[float]]:
    trees = json.loads(path.read_text(encoding="utf-8"))["learner"]["gradient_booster"]["model"][
        "trees"
    ]
    thresholds: dict[int, set[float]] = {}
    for tree in trees:
        for node, left in enumerate(tree["left_children"]):
            if left != -1:
                thresholds.setdefault(tree["split_indices"][node], set()).add(
                    tree["split_conditions"][node]
                )
    return {index: sorted(values) for index, values in thresholds.items()}


def near(value: float, rng: random.Random) -> float:
    """The threshold itself or a float64 value too close to it to differ in float32."""
    choice = rng.randrange(5)
    if choice == 0:
        return value
    if choice == 1:
        return float(np.nextafter(value, math.inf))
    if choice == 2:
        return float(np.nextafter(value, -math.inf))
    if choice == 3:
        return value * (1 + 1e-9) if value else 1e-12
    return float(np.float32(value))


def boundary_rows(path: Path, count: int, rng: random.Random) -> list[list[float]]:
    names = feature_names(path)
    thresholds = split_thresholds(path)
    rows = []
    for _ in range(count):
        row = []
        for index in range(len(names)):
            if index in thresholds and rng.random() < 0.85:
                row.append(near(rng.choice(thresholds[index]), rng))
            else:
                row.append(math.nan if rng.random() < 0.1 else rng.uniform(-50, 300))
        rows.append(row)
    return rows


def behaviour_rows(names: list[str], disengagement: bool, count: int, rng: random.Random):
    rows: list[list[float]] = []
    while len(rows) < count:
        history: list[BehaviorObservation] = []
        for _ in range(25):
            observation = BehaviorObservation(
                correct=float(rng.random() < 0.6),
                bottom_hint=rng.choice([None, 0.0, 1.0]),
                hint_count=float(rng.choice([0, 0, 1, 2, 3])),
                attempt_count=float(rng.choice([1, 1, 2, 3])),
                ms_first_response=rng.uniform(1500, 60000),
                overlap_time=rng.uniform(2000, 90000),
                original=1.0,
            )
            features = (
                build_disengagement_behavior_features(observation, history)
                if disengagement
                else build_confusion_behavior_features(observation)
            )
            rows.append([math.nan if features[n] is None else float(features[n]) for n in names])
            history.append(observation)
    return rows[:count]


def visual_rows(count: int, rng: random.Random) -> list[list[float]]:
    rows = []
    for _ in range(count):
        pitch, yaw, roll = rng.uniform(-30, 30), rng.uniform(-40, 40), rng.uniform(-25, 25)
        rows.append([
            rng.uniform(0.1, 0.5),  # mean_eye_openness
            rng.uniform(0.0, 0.12),  # std_eye_openness
            rng.uniform(0.3, 0.7),  # mean_gaze_ratio
            rng.uniform(0.0, 0.15),  # std_gaze_ratio
            pitch,
            yaw,
            roll,
            abs(pitch) + rng.uniform(0, 3),
            abs(yaw) + rng.uniform(0, 3),
            abs(roll) + rng.uniform(0, 3),
            # face_visibility_ratio: share of 30 samples with a face, usually all of them
            rng.choice([1.0, 1.0, rng.randint(0, 30) / 30]),
        ])
    return rows


def as_json(value: float) -> float | None:
    return None if math.isnan(value) else value


def main() -> None:
    rng = random.Random(20261015)
    output = {
        "source": "research/learner-state/tools/generate_model_reference_predictions.py",
        "xgboost_version": xgb.__version__,
        "models": {},
    }

    for filename in sorted(p.name for p in MODEL_DIRECTORY.glob("*.json")):
        path = MODEL_DIRECTORY / filename
        names = feature_names(path)
        booster = xgb.Booster()
        booster.load_model(path)

        if "visual" in filename:
            realistic = visual_rows(ROWS_PER_KIND, rng)
        else:
            realistic = behaviour_rows(names, "disengagement" in filename, ROWS_PER_KIND, rng)
        boundary = boundary_rows(path, ROWS_PER_KIND, rng)

        cases = []
        for kind, rows in (("boundary", boundary), ("realistic", realistic)):
            matrix = xgb.DMatrix(
                np.asarray(rows, dtype=np.float32), feature_names=names, missing=np.nan
            )
            for row, probability in zip(rows, booster.predict(matrix), strict=True):
                cases.append({
                    "kind": kind,
                    "values": [as_json(v) for v in row],
                    "probability": float(probability),
                })

        output["models"][filename] = {"features": names, "cases": cases}

    # One case per line keeps the file compact and its diffs readable.
    lines = [
        "{",
        f'"source": {json.dumps(output["source"])},',
        f'"xgboost_version": {json.dumps(output["xgboost_version"])},',
        '"models": {',
    ]
    models = list(output["models"].items())
    for model_index, (filename, model) in enumerate(models):
        lines.append(f'{json.dumps(filename)}: {{"features": {json.dumps(model["features"])},')
        lines.append('"cases": [')
        cases = model["cases"]
        for case_index, case in enumerate(cases):
            comma = "," if case_index < len(cases) - 1 else ""
            lines.append(json.dumps(case, separators=(",", ":")) + comma)
        lines.append("]}" + ("," if model_index < len(models) - 1 else ""))
    lines += ["}", "}"]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    total = sum(len(m["cases"]) for m in output["models"].values())
    print(f"wrote {total} reference predictions (XGBoost {xgb.__version__}) to {OUTPUT}")


if __name__ == "__main__":
    main()
