"""
Generate reference values for the browser port of the visual feature extraction.

The feature functions below are copied unchanged from
research/learner-state/notebooks/mindbridge-visual-model-01.ipynb (the "rollfix" version that
produced the training features). They are run on synthetic MediaPipe-style landmarks, and the
results are written as a JSON fixture that the frontend tests compare against.

Run from the repository root with the backend virtual environment (it has OpenCV):

    backend/.venv/Scripts/python research/learner-state/tools/generate_visual_feature_fixtures.py

No images, video or real participant data are used.

Scope: the fixtures start from landmarks, so they validate the feature calculations only. They do
not validate MediaPipe landmark extraction itself.
"""

import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "frontend/src/features/learner-state/visual/__fixtures__/visual-features.json"
)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
LANDMARK_COUNT = 478


# ---------------------------------------------------------------------------
# Copied from the visual notebook (cells 19, 20, 22, 24, 37 and 38)
# ---------------------------------------------------------------------------

def point_distance(p1, p2):
    return np.sqrt(
        (p1.x - p2.x) ** 2 +
        (p1.y - p2.y) ** 2
    )


def calculate_eye_openness(landmarks, eye_indices):
    p1 = landmarks[eye_indices[0]]
    p2 = landmarks[eye_indices[1]]
    p3 = landmarks[eye_indices[2]]
    p4 = landmarks[eye_indices[3]]
    p5 = landmarks[eye_indices[4]]
    p6 = landmarks[eye_indices[5]]

    vertical_1 = point_distance(p2, p6)
    vertical_2 = point_distance(p3, p5)

    horizontal = point_distance(p1, p4)

    if horizontal == 0:
        return 0.0

    openness = (
        vertical_1 + vertical_2
    ) / (2.0 * horizontal)

    return openness


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def estimate_head_pose(frame, landmarks):
    h, w = frame.shape[:2]

    image_points = np.array([
        [landmarks[1].x * w,   landmarks[1].y * h],
        [landmarks[152].x * w, landmarks[152].y * h],
        [landmarks[33].x * w,  landmarks[33].y * h],
        [landmarks[263].x * w, landmarks[263].y * h],
        [landmarks[61].x * w,  landmarks[61].y * h],
        [landmarks[291].x * w, landmarks[291].y * h],
    ], dtype=np.float64)

    model_points = np.array([
        [0.0,    0.0,    0.0],
        [0.0, -330.0,  -65.0],
        [-225.0, 170.0, -135.0],
        [225.0, 170.0, -135.0],
        [-150.0, -150.0, -125.0],
        [150.0, -150.0, -125.0],
    ])

    focal_length = w

    camera_matrix = np.array([
        [focal_length, 0, w / 2],
        [0, focal_length, h / 2],
        [0, 0, 1]
    ], dtype=np.float64)

    distortion = np.zeros((4, 1))

    # Kept exactly as in the notebook, including the unused translation_vector.
    success, rotation_vector, translation_vector = cv2.solvePnP(  # noqa: RUF059
        model_points,
        image_points,
        camera_matrix,
        distortion,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        return None

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

    pitch = angles[0]
    yaw   = angles[1]
    roll  = angles[2]

    return pitch, yaw, roll


def normalize_pitch(pitch):
    if pitch > 90:
        pitch = 180 - pitch
    elif pitch < -90:
        pitch = -180 - pitch

    return pitch


def normalize_roll(roll):
    return ((roll + 90) % 180) - 90


def mean_point(landmarks, indices):
    xs = [landmarks[i].x for i in indices]
    ys = [landmarks[i].y for i in indices]

    return np.mean(xs), np.mean(ys)


def calculate_gaze_ratio(landmarks):
    LEFT_IRIS = [468, 469, 470, 471, 472]
    RIGHT_IRIS = [473, 474, 475, 476, 477]

    LEFT_CORNERS = [33, 133]
    RIGHT_CORNERS = [362, 263]

    left_iris_x, _ = mean_point(landmarks, LEFT_IRIS)
    right_iris_x, _ = mean_point(landmarks, RIGHT_IRIS)

    left_x1 = landmarks[LEFT_CORNERS[0]].x
    left_x2 = landmarks[LEFT_CORNERS[1]].x

    right_x1 = landmarks[RIGHT_CORNERS[0]].x
    right_x2 = landmarks[RIGHT_CORNERS[1]].x

    left_min = min(left_x1, left_x2)
    left_max = max(left_x1, left_x2)

    right_min = min(right_x1, right_x2)
    right_max = max(right_x1, right_x2)

    left_ratio = (
        (left_iris_x - left_min) /
        (left_max - left_min + 1e-6)
    )

    right_ratio = (
        (right_iris_x - right_min) /
        (right_max - right_min + 1e-6)
    )

    mean_ratio = (
        left_ratio + right_ratio
    ) / 2

    return left_ratio, right_ratio, mean_ratio


def per_frame_values(frame, landmarks):
    """Per-frame part of extract_clip_features_fast (notebook cell 38)."""
    left_eye = calculate_eye_openness(landmarks, LEFT_EYE)
    right_eye = calculate_eye_openness(landmarks, RIGHT_EYE)
    mean_eye = (left_eye + right_eye) / 2

    _, _, mean_gaze = calculate_gaze_ratio(landmarks)

    pose = estimate_head_pose(frame, landmarks)
    pitch = yaw = roll = None
    if pose is not None:
        pitch, yaw, roll = pose
        pitch = normalize_pitch(pitch)
        roll = normalize_roll(roll)

    return mean_eye, mean_gaze, pitch, yaw, roll


def aggregate(processed_frames, face_frames):
    """Aggregation part of extract_clip_features_fast (notebook cell 38)."""
    eye_values = [f["eye"] for f in face_frames]
    gaze_values = [f["gaze"] for f in face_frames]
    pitch_values = [f["pitch"] for f in face_frames if f["pitch"] is not None]
    yaw_values = [f["yaw"] for f in face_frames if f["yaw"] is not None]
    roll_values = [f["roll"] for f in face_frames if f["roll"] is not None]

    def safe_mean(values):
        arr = np.asarray(values, dtype=float)
        if arr.size == 0:
            return np.nan
        return float(np.mean(arr))

    def safe_std(values):
        arr = np.asarray(values, dtype=float)
        if arr.size == 0:
            return np.nan
        return float(np.std(arr))

    return {
        "mean_eye_openness": safe_mean(eye_values),
        "std_eye_openness": safe_std(eye_values),
        "mean_gaze_ratio": safe_mean(gaze_values),
        "std_gaze_ratio": safe_std(gaze_values),
        "mean_pitch": safe_mean(pitch_values),
        "mean_yaw": safe_mean(yaw_values),
        "mean_roll": safe_mean(roll_values),
        "mean_abs_pitch": safe_mean(np.abs(pitch_values)),
        "mean_abs_yaw": safe_mean(np.abs(yaw_values)),
        "mean_abs_roll": safe_mean(np.abs(roll_values)),
        "face_visibility_ratio": len(face_frames) / processed_frames,
    }


# ---------------------------------------------------------------------------
# Synthetic MediaPipe-style landmarks
# ---------------------------------------------------------------------------

# 3D positions in the same coordinate system as the notebook's generic face model
# (millimetre-like units, y up, nose tip at the origin).
POSE_POINTS = {
    1: (0.0, 0.0, 0.0),
    152: (0.0, -330.0, -65.0),
    33: (-225.0, 170.0, -135.0),
    263: (225.0, 170.0, -135.0),
    61: (-150.0, -150.0, -125.0),
    291: (150.0, -150.0, -125.0),
}


def eye_points(outer, inner, openness, gaze, lids):
    """Return 3D eye-contour and iris points for one eye."""
    ox, oy, oz = outer
    ix, _, _ = inner
    width = ix - ox
    half = 0.5 * openness * abs(width)
    u1, u2, l1, l2 = lids
    points = {
        u1: (ox + width / 3, oy + half, oz),
        u2: (ox + 2 * width / 3, oy + half, oz),
        l1: (ox + 2 * width / 3, oy - half, oz),
        l2: (ox + width / 3, oy - half, oz),
    }
    centre_x = ox + gaze * width
    return points, (centre_x, oy, oz + 5.0)


def build_face(openness, gaze):
    points = dict(POSE_POINTS)
    points[133] = (-75.0, 170.0, -140.0)
    points[362] = (75.0, 170.0, -140.0)
    left, left_iris = eye_points(points[33], points[133], openness, gaze, (160, 158, 153, 144))
    right, right_iris = eye_points(points[362], points[263], openness, gaze, (385, 387, 373, 380))
    points.update(left)
    points.update(right)
    iris_radius = 18.0
    for base, (cx, cy, cz) in ((468, left_iris), (473, right_iris)):
        points[base] = (cx, cy, cz)
        points[base + 1] = (cx + iris_radius, cy, cz)
        points[base + 2] = (cx, cy + iris_radius, cz)
        points[base + 3] = (cx - iris_radius, cy, cz)
        points[base + 4] = (cx, cy - iris_radius, cz)
    return points


def rotation_from_angles(pitch, yaw, roll):
    rx, ry, rz = (math.radians(a) for a in (pitch, yaw, roll))
    cx, sx, cy, sy, cz, sz = (
        math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    )
    x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    # Flip y so that the face's "up" maps to image "up" (image y grows downwards).
    flip = np.diag([1.0, -1.0, -1.0])
    return flip @ z @ y @ x


def project(points, rotation, translation, rng, noise_px):
    focal = FRAME_WIDTH
    centre = (FRAME_WIDTH / 2, FRAME_HEIGHT / 2)
    landmarks = {}
    for index, p in points.items():
        cam = rotation @ np.array(p) + translation
        u = focal * cam[0] / cam[2] + centre[0] + rng.normal(0, noise_px)
        v = focal * cam[1] / cam[2] + centre[1] + rng.normal(0, noise_px)
        landmarks[index] = (u / FRAME_WIDTH, v / FRAME_HEIGHT)
    return landmarks


def as_mediapipe(landmarks):
    full = [SimpleNamespace(x=0.5, y=0.5) for _ in range(LANDMARK_COUNT)]
    for index, (x, y) in landmarks.items():
        full[index] = SimpleNamespace(x=x, y=y)
    return full


FRAME = SimpleNamespace(shape=(FRAME_HEIGHT, FRAME_WIDTH, 3))


def make_frame_case(name, rng, *, pitch, yaw, roll, openness, gaze, distance=2600.0, noise_px=0.6):
    rotation = rotation_from_angles(pitch, yaw, roll)
    translation = np.array([rng.normal(0, 60), rng.normal(0, 40), distance])
    landmarks = project(build_face(openness, gaze), rotation, translation, rng, noise_px)
    mp = as_mediapipe(landmarks)

    raw_pose = estimate_head_pose(FRAME, mp)
    eye, gaze_ratio, pitch_n, yaw_v, roll_n = per_frame_values(FRAME, mp)
    left_eye = calculate_eye_openness(mp, LEFT_EYE)
    right_eye = calculate_eye_openness(mp, RIGHT_EYE)
    left_gaze, right_gaze, _ = calculate_gaze_ratio(mp)

    return {
        "name": name,
        "landmarks": {str(k): [float(v[0]), float(v[1])] for k, v in sorted(landmarks.items())},
        "expected": {
            "left_eye_openness": float(left_eye),
            "right_eye_openness": float(right_eye),
            "mean_eye_openness": float(eye),
            "left_gaze_ratio": float(left_gaze),
            "right_gaze_ratio": float(right_gaze),
            "mean_gaze_ratio": float(gaze_ratio),
            "raw_pitch": float(raw_pose[0]),
            "raw_yaw": float(raw_pose[1]),
            "raw_roll": float(raw_pose[2]),
            "pitch": float(pitch_n),
            "yaw": float(yaw_v),
            "roll": float(roll_n),
        },
    }


def main():
    rng = np.random.default_rng(20261014)
    frames = []

    fixed = [
        ("frontal", 0, 0, 0),
        ("look_down", 20, 0, 0),
        ("look_up", -20, 0, 0),
        ("turn_left", 0, -35, 0),
        ("turn_right", 0, 35, 0),
        ("tilt_left", 0, 0, -25),
        ("tilt_right", 0, 0, 25),
        ("combined", 15, -25, 10),
        ("near_upside_down_roll", 5, 10, 172),
        ("near_upside_down_roll_negative", -5, -10, -168),
    ]
    for name, pitch, yaw, roll in fixed:
        frames.append(
            make_frame_case(name, rng, pitch=pitch, yaw=yaw, roll=roll, openness=0.32, gaze=0.5)
        )

    for i in range(40):
        frames.append(
            make_frame_case(
                f"random_{i:02d}",
                rng,
                pitch=float(rng.uniform(-30, 30)),
                yaw=float(rng.uniform(-45, 45)),
                roll=float(rng.uniform(-30, 30)),
                openness=float(rng.uniform(0.05, 0.45)),
                gaze=float(rng.uniform(0.3, 0.7)),
                distance=float(rng.uniform(1800, 4200)),
            )
        )

    angles = [179.039877, -178.096820, 170.779493, -173.975938, 12.4, -8.5, 90.0, -90.0, 0.0]
    normalization = {
        "roll": [[a, float(normalize_roll(a))] for a in angles],
        "pitch": [[a, float(normalize_pitch(a))] for a in angles + [166.28, -150.0]],
    }

    # Window aggregation: per-frame values from the cases above, some frames without a face.
    def window_case(name, processed, use, missing_pose=()):
        face_frames = []
        for j, case in enumerate(use):
            e = case["expected"]
            pose_missing = j in missing_pose
            face_frames.append({
                "eye": e["mean_eye_openness"],
                "gaze": e["mean_gaze_ratio"],
                "pitch": None if pose_missing else e["pitch"],
                "yaw": None if pose_missing else e["yaw"],
                "roll": None if pose_missing else e["roll"],
            })
        features = aggregate(processed, face_frames)
        return {
            "name": name,
            "processed_frames": processed,
            "face_frames": face_frames,
            "expected": {k: (None if isinstance(v, float) and math.isnan(v) else v)
                         for k, v in features.items()},
        }

    windows = [
        window_case("all_30_frames_with_face", 30, frames[10:40]),
        window_case("20_of_30_frames_with_face", 30, frames[20:40]),
        window_case("pose_missing_in_some_frames", 30, frames[10:25], missing_pose=(0, 3, 7)),
        window_case("wrapped_rolls", 30, frames[8:10] + frames[0:4]),
        window_case("no_face", 30, []),
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "source": "research/learner-state/tools/generate_visual_feature_fixtures.py",
                "opencv_version": cv2.__version__,
                "frame": {"width": FRAME_WIDTH, "height": FRAME_HEIGHT},
                "frames": frames,
                "normalization": normalization,
                "windows": windows,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(frames)} frame cases and {len(windows)} window cases to {OUTPUT}")


if __name__ == "__main__":
    main()
