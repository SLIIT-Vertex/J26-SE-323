"""
Local engineering equivalence test: browser MediaPipe vs the Python training pipeline.

Checks that browser MediaPipe 1.0.1 plus the TypeScript feature code produce sufficiently
equivalent final 11 visual features to the visual notebook's Python MediaPipe 1.0.1 pipeline on
the same input frames (docs/learner-state/10_FRONTEND_INTEGRATION.md §9). This is NOT learner or
research-participant data and NOT a validation of confusion or disengagement detection.

Developer-owned clips (own face only) live in research/learner-state/local-test-frames/clips/,
which is git-ignored, as is everything this script writes there. Only the numeric comparison in
research/learner-state/results/ is meant to be committed: differences, counts and versions, no
frames, landmarks or feature values.

Use a separate environment with the notebook's versions (the backend does not need MediaPipe):

    py -3.12 -m venv research/learner-state/.venv
    research/learner-state/.venv/Scripts/python -m pip install mediapipe==1.0.1 "opencv-contrib-python==4.14.0.*"

Steps, from the repository root:

    PY=research/learner-state/.venv/Scripts/python
    $PY research/learner-state/tools/mediapipe_equivalence.py extract   # clips -> 30 PNG frames each
    $PY research/learner-state/tools/mediapipe_equivalence.py python    # notebook pipeline
    # browser: dev page ?dev=learner-state -> "Equivalence test" -> save browser-results.json
    $PY research/learner-state/tools/mediapipe_equivalence.py compare   # numeric comparison
"""

import argparse
import json
import math
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The notebook's per-frame and aggregation functions, already copied unchanged for the
# landmark-level fixtures.
from generate_visual_feature_fixtures import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    aggregate,
    per_frame_values,
)

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / "research/learner-state/local-test-frames"
CLIPS = LOCAL / "clips"
FRAMES = LOCAL / "frames"
PYTHON_RESULTS = LOCAL / "python-results.json"
BROWSER_RESULTS = LOCAL / "browser-results.json"
OUTPUT = ROOT / "research/learner-state/results/mediapipe_equivalence_results.json"
MODEL = ROOT / "frontend/src/features/learner-state/visual/assets/face_landmarker.task"

SAMPLES = 30
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".avi", ".mkv"}

WINDOW_FEATURES = (
    "mean_eye_openness",
    "std_eye_openness",
    "mean_gaze_ratio",
    "std_gaze_ratio",
    "mean_pitch",
    "mean_yaw",
    "mean_roll",
    "mean_abs_pitch",
    "mean_abs_yaw",
    "mean_abs_roll",
    "face_visibility_ratio",
)
FRAME_FEATURES = ("eye", "gaze", "pitch", "yaw", "roll")

# Acceptance tolerances for the final 11 features, stated before the first comparison run
# (absolute differences per clip window). Eye openness and gaze ratio are ratios of landmark
# distances; angles are in degrees, compared with the reliability quantiles of 6-11 degrees
# (Q75) in backend/app/learner_state/infrastructure/reliability.py.
TOLERANCES = {
    "mean_eye_openness": 0.01,
    "std_eye_openness": 0.01,
    "mean_gaze_ratio": 0.01,
    "std_gaze_ratio": 0.01,
    "mean_pitch": 1.0,
    "mean_yaw": 1.0,
    "mean_roll": 1.0,
    "mean_abs_pitch": 1.0,
    "mean_abs_yaw": 1.0,
    "mean_abs_roll": 1.0,
    # At most one of the 30 frames may differ in face detection.
    "face_visibility_ratio": 1 / SAMPLES,
}


def centre_crop_4x3(frame: np.ndarray) -> np.ndarray:
    """Same crop as the browser's centreCrop4x3 (frameCapture.ts)."""
    h, w = frame.shape[:2]
    target = FRAME_WIDTH / FRAME_HEIGHT
    if w / h > target:
        sw = round(h * target)
        sx = (w - sw) // 2
        return frame[:, sx : sx + sw]
    sh = round(w / target)
    sy = (h - sh) // 2
    return frame[sy : sy + sh, :]


def extract() -> None:
    clips = sorted(p for p in CLIPS.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)
    if not clips:
        raise SystemExit(f"no clips in {CLIPS}")

    manifest = {"samples": SAMPLES, "frame_size": [FRAME_WIDTH, FRAME_HEIGHT], "clips": {}}
    for number, clip in enumerate(clips, start=1):
        clip_id = f"clip{number:02d}"
        out = FRAMES / clip_id
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("*.png"):
            old.unlink()

        cap = cv2.VideoCapture(str(clip))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        written = []
        # As in the notebook: 30 frames spread over the clip, frames that cannot be read skipped.
        for k, index in enumerate(np.linspace(0, total - 1, SAMPLES).astype(int)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = cap.read()
            if not ok:
                continue
            frame = cv2.resize(
                centre_crop_4x3(frame), (FRAME_WIDTH, FRAME_HEIGHT), interpolation=cv2.INTER_AREA
            )
            name = f"frame_{k:02d}.png"
            cv2.imwrite(str(out / name), frame)  # lossless, so both pipelines see the same pixels
            written.append(name)
        cap.release()

        # The original file name stays in this git-ignored manifest only.
        manifest["clips"][clip_id] = {"source": clip.name, "frames": written}
        print(f"{clip_id}: {len(written)} frames")

    (FRAMES / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def finite_or_none(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else float(value)


def run_python() -> None:
    import mediapipe as mp

    manifest = json.loads((FRAMES / "manifest.json").read_text(encoding="utf-8"))
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
    )

    results = {"pipeline": "python", "versions": versions(), "clips": {}}
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
        for clip_id, clip in manifest["clips"].items():
            frames, face_frames = [], []
            for name in clip["frames"]:
                frame = cv2.imread(str(FRAMES / clip_id / name))
                if frame is None:
                    raise SystemExit(f"cannot read {clip_id}/{name}; run the extract step again")
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                detection = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
                if not detection.face_landmarks:
                    frames.append({"file": name, "landmarks": None, "features": None})
                    continue
                landmarks = detection.face_landmarks[0]
                eye, gaze, pitch, yaw, roll = per_frame_values(frame, landmarks)
                values = {"eye": eye, "gaze": gaze, "pitch": pitch, "yaw": yaw, "roll": roll}
                face_frames.append(values)
                frames.append({
                    "file": name,
                    "landmarks": [[p.x, p.y] for p in landmarks],
                    "features": {k: finite_or_none(v) for k, v in values.items()},
                })
            window = aggregate(len(clip["frames"]), face_frames) if clip["frames"] else None
            results["clips"][clip_id] = {
                "frames": frames,
                "window": None if window is None else {k: finite_or_none(v) for k, v in window.items()},
            }
            print(f"{clip_id}: {len(face_frames)}/{len(clip['frames'])} frames with a face")

    PYTHON_RESULTS.write_text(json.dumps(results), encoding="utf-8")


def versions() -> dict[str, str]:
    import mediapipe as mp

    return {
        "mediapipe": mp.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "python": platform.python_version(),
    }


def summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "max": None, "mean": None}
    return {"count": len(values), "max": max(values), "mean": sum(values) / len(values)}


def compare() -> None:
    python = json.loads(PYTHON_RESULTS.read_text(encoding="utf-8"))
    browser = json.loads(BROWSER_RESULTS.read_text(encoding="utf-8"))
    if set(python["clips"]) != set(browser["clips"]):
        raise SystemExit("python and browser results cover different clips")

    detection = {"frames": 0, "both": 0, "neither": 0, "python_only": 0, "browser_only": 0}
    landmark_px: list[float] = []
    frame_diffs: dict[str, list[float]] = {k: [] for k in FRAME_FEATURES}
    window_diffs: dict[str, list[float]] = {k: [] for k in WINDOW_FEATURES}
    clips = {}
    missing_mismatch = 0

    for clip_id in sorted(python["clips"]):
        p_clip, b_clip = python["clips"][clip_id], browser["clips"][clip_id]
        b_frames = {f["file"]: f for f in b_clip["frames"]}
        for p_frame in p_clip["frames"]:
            b_frame = b_frames[p_frame["file"]]
            detection["frames"] += 1
            p_face, b_face = p_frame["landmarks"] is not None, b_frame["landmarks"] is not None
            key = {(True, True): "both", (False, False): "neither", (True, False): "python_only"}
            detection[key.get((p_face, b_face), "browser_only")] += 1
            if not (p_face and b_face):
                continue
            for (px, py), (bx, by) in zip(p_frame["landmarks"], b_frame["landmarks"], strict=True):
                landmark_px.append(math.hypot((px - bx) * FRAME_WIDTH, (py - by) * FRAME_HEIGHT))
            for name in FRAME_FEATURES:
                a, b = p_frame["features"][name], b_frame["features"][name]
                if a is not None and b is not None:
                    frame_diffs[name].append(abs(a - b))

        per_clip = {}
        for name in WINDOW_FEATURES:
            a, b = p_clip["window"][name], b_clip["window"][name]
            if a is None or b is None:
                # Both must be missing (no face, or no head pose) for the windows to agree.
                agree = a is None and b is None
                missing_mismatch += 0 if agree else 1
                per_clip[name] = {"difference": None, "both_missing": agree}
                continue
            difference = abs(a - b)
            window_diffs[name].append(difference)
            per_clip[name] = {"difference": difference, "within_tolerance": difference <= TOLERANCES[name]}
        clips[clip_id] = per_clip

    features = {}
    for name in WINDOW_FEATURES:
        stats = summary(window_diffs[name])
        stats["tolerance"] = TOLERANCES[name]
        stats["within_tolerance"] = stats["max"] is None or stats["max"] <= TOLERANCES[name]
        features[name] = stats

    passed = missing_mismatch == 0 and all(f["within_tolerance"] for f in features.values())
    output = {
        "description": (
            "Local engineering equivalence test of the learner-state visual pipeline: browser "
            "MediaPipe + TypeScript features vs the notebook's Python MediaPipe pipeline on the "
            "same developer-owned frames. Not learner or research-participant data, and not a "
            "validation of confusion or disengagement detection. Only differences are reported."
        ),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "research/learner-state/tools/mediapipe_equivalence.py",
        "configuration": {
            "clips": len(clips),
            "samples_per_clip": SAMPLES,
            "frame_size": [FRAME_WIDTH, FRAME_HEIGHT],
            "frame_selection": "np.linspace(0, frame_count - 1, 30), centre crop 4:3, INTER_AREA resize, PNG",
            "detector": "FaceLandmarker IMAGE mode, 1 face, detection/presence confidence 0.5",
            "model_sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        },
        "versions": {"python": python["versions"], "browser": browser["versions"]},
        "passed": passed,
        "window_features": features,
        "window_missing_value_mismatches": missing_mismatch,
        "per_clip_window_differences": clips,
        "supporting": {
            "face_detection": detection,
            "landmark_distance_px": summary(landmark_px),
            "per_frame_feature_differences": {k: summary(v) for k, v in frame_diffs.items()},
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: output[k] for k in ("passed", "window_missing_value_mismatches")}))
    for name, stats in features.items():
        mark = "ok  " if stats["within_tolerance"] else "FAIL"
        print(f"{mark} {name:22s} max {stats['max']} (tolerance {stats['tolerance']:.4g})")
    print(f"wrote {OUTPUT}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local equivalence test: browser MediaPipe vs the Python training pipeline."
    )
    parser.add_argument("step", choices=["extract", "python", "compare"])
    step = parser.parse_args().step
    {"extract": extract, "python": run_python, "compare": compare}[step]()


if __name__ == "__main__":
    main()
