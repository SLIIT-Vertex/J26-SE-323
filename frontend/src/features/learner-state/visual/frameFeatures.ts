// Per-frame visual features, ported from the visual training notebook
// (research/learner-state/notebooks/mindbridge-visual-model-01.ipynb, "rollfix" version).
// Landmarks are MediaPipe Face Landmarker outputs normalised to a 640 x 480 frame.

import { estimateHeadPose, type Landmark } from "./headPose";

export type { Landmark } from "./headPose";

/** Frame size used for DAiSEE during training; live frames must be processed at this size. */
export const FRAME_WIDTH = 640;
export const FRAME_HEIGHT = 480;

export const LEFT_EYE = [33, 160, 158, 133, 153, 144] as const;
export const RIGHT_EYE = [362, 385, 387, 263, 373, 380] as const;
const LEFT_IRIS = [468, 469, 470, 471, 472] as const;
const RIGHT_IRIS = [473, 474, 475, 476, 477] as const;
const LEFT_CORNERS = [33, 133] as const;
const RIGHT_CORNERS = [362, 263] as const;

export type FrameFeatures = {
  eyeOpenness: number;
  gazeRatio: number;
  /** Normalised pitch, yaw and normalised roll in degrees; null when head pose failed. */
  pitch: number | null;
  yaw: number | null;
  roll: number | null;
};

function distance(a: Landmark, b: Landmark): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

/** Eye-aspect-ratio style openness (notebook: calculate_eye_openness). */
export function eyeOpenness(landmarks: readonly Landmark[], eye: readonly number[]): number {
  const [p1, p2, p3, p4, p5, p6] = eye.map((index) => landmarks[index]);
  const horizontal = distance(p1, p4);
  if (horizontal === 0) return 0;
  return (distance(p2, p6) + distance(p3, p5)) / (2 * horizontal);
}

function meanX(landmarks: readonly Landmark[], indices: readonly number[]): number {
  return indices.reduce((sum, index) => sum + landmarks[index].x, 0) / indices.length;
}

function irisRatio(
  landmarks: readonly Landmark[],
  iris: readonly number[],
  corners: readonly number[],
): number {
  const x1 = landmarks[corners[0]].x;
  const x2 = landmarks[corners[1]].x;
  const min = Math.min(x1, x2);
  const max = Math.max(x1, x2);
  return (meanX(landmarks, iris) - min) / (max - min + 1e-6);
}

/** Horizontal iris position within each eye (notebook: calculate_gaze_ratio). */
export function gazeRatios(landmarks: readonly Landmark[]): {
  left: number;
  right: number;
  mean: number;
} {
  const left = irisRatio(landmarks, LEFT_IRIS, LEFT_CORNERS);
  const right = irisRatio(landmarks, RIGHT_IRIS, RIGHT_CORNERS);
  return { left, right, mean: (left + right) / 2 };
}

/** Notebook: normalize_pitch. */
export function normalizePitch(pitch: number): number {
  if (pitch > 90) return 180 - pitch;
  if (pitch < -90) return -180 - pitch;
  return pitch;
}

/** Python's `%` (result has the sign of the divisor); JavaScript's `%` differs for negatives. */
function pythonModulo(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}

/** Notebook: normalize_roll, ((roll + 90) % 180) - 90 with Python modulo semantics. */
export function normalizeRoll(roll: number): number {
  return pythonModulo(roll + 90, 180) - 90;
}

/** All per-frame values for one frame in which a face was detected. */
export function extractFrameFeatures(
  landmarks: readonly Landmark[],
  width: number = FRAME_WIDTH,
  height: number = FRAME_HEIGHT,
): FrameFeatures {
  const eyeOpennessValue =
    (eyeOpenness(landmarks, LEFT_EYE) + eyeOpenness(landmarks, RIGHT_EYE)) / 2;
  const pose = estimateHeadPose(landmarks, width, height);

  return {
    eyeOpenness: eyeOpennessValue,
    gazeRatio: gazeRatios(landmarks).mean,
    pitch: pose ? normalizePitch(pose.pitch) : null,
    yaw: pose ? pose.yaw : null,
    roll: pose ? normalizeRoll(pose.roll) : null,
  };
}
