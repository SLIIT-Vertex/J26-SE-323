// Converts an aggregated visual window into the `visual` object of POST /api/v1/learner-state.
//
// The API requires 11 finite numbers. When the window has no usable face data there is nothing
// real to send, so placeholder zeros are sent with face_visibility_ratio = 0. The backend then
// computes visual reliability = 0, which gives the visual model zero weight in fusion
// (see docs/learner-state/04_RELIABILITY_AND_FUSION.md and 07_EVALUATION_AND_LIMITATIONS.md).

import type { VisualWindowFeatures } from "./windowFeatures";

export type ApiVisualFeatures = {
  mean_eye_openness: number;
  std_eye_openness: number;
  mean_gaze_ratio: number;
  std_gaze_ratio: number;
  mean_pitch: number;
  mean_yaw: number;
  mean_roll: number;
  mean_abs_pitch: number;
  mean_abs_yaw: number;
  mean_abs_roll: number;
  face_visibility_ratio: number;
};

export type UnusableReason = "no-samples" | "no-face" | "no-head-pose" | "invalid-value";

export type ApiVisualResult =
  | { usable: true; visual: ApiVisualFeatures }
  | { usable: false; reason: UnusableReason; visual: ApiVisualFeatures };

const NO_VISUAL_EVIDENCE: ApiVisualFeatures = {
  mean_eye_openness: 0,
  std_eye_openness: 0,
  mean_gaze_ratio: 0,
  std_gaze_ratio: 0,
  mean_pitch: 0,
  mean_yaw: 0,
  mean_roll: 0,
  mean_abs_pitch: 0,
  mean_abs_yaw: 0,
  mean_abs_roll: 0,
  face_visibility_ratio: 0,
};

function unusable(reason: UnusableReason): ApiVisualResult {
  return { usable: false, reason, visual: { ...NO_VISUAL_EVIDENCE } };
}

export function toApiVisualFeatures(window: VisualWindowFeatures | null): ApiVisualResult {
  if (window === null) return unusable("no-samples");
  if (window.face_visibility_ratio === 0 || window.mean_eye_openness === null) {
    return unusable("no-face");
  }
  // Faces were seen but head pose could never be solved. Pose drives visual reliability,
  // so the window is treated as having no usable visual evidence.
  if (window.mean_pitch === null) return unusable("no-head-pose");

  const values = Object.values(window);
  if (values.some((value) => value === null || !Number.isFinite(value))) {
    return unusable("invalid-value");
  }
  return { usable: true, visual: window as ApiVisualFeatures };
}
