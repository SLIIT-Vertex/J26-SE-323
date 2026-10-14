// Window aggregation, ported from `extract_clip_features_fast` in the visual training notebook.
// Values are the 11 visual features expected by the learner-state API, in its field names.

import type { FrameFeatures } from "./frameFeatures";

/** Number of evenly spaced samples per window, as used for the 10-second DAiSEE clips. */
export const SAMPLES_PER_WINDOW = 30;

export type VisualWindowFeatures = {
  mean_eye_openness: number | null;
  std_eye_openness: number | null;
  mean_gaze_ratio: number | null;
  std_gaze_ratio: number | null;
  mean_pitch: number | null;
  mean_yaw: number | null;
  mean_roll: number | null;
  mean_abs_pitch: number | null;
  mean_abs_yaw: number | null;
  mean_abs_roll: number | null;
  face_visibility_ratio: number;
};

/** Mean, or null for an empty list (the notebook's safe_mean returns NaN). */
function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

/** Population standard deviation (NumPy's default np.std), or null for an empty list. */
function std(values: number[]): number | null {
  const m = mean(values);
  if (m === null) return null;
  return Math.sqrt(values.reduce((sum, v) => sum + (v - m) ** 2, 0) / values.length);
}

function present(values: (number | null)[]): number[] {
  return values.filter((v): v is number => v !== null);
}

/**
 * Aggregate one window.
 * @param processedFrames number of frames that were sampled and read (normally 30)
 * @param faceFrames per-frame features of the frames in which a face was detected
 */
export function aggregateWindow(
  processedFrames: number,
  faceFrames: readonly FrameFeatures[],
): VisualWindowFeatures {
  if (processedFrames <= 0) throw new Error("processedFrames must be positive");

  const eye = faceFrames.map((f) => f.eyeOpenness);
  const gaze = faceFrames.map((f) => f.gazeRatio);
  const pitch = present(faceFrames.map((f) => f.pitch));
  const yaw = present(faceFrames.map((f) => f.yaw));
  const roll = present(faceFrames.map((f) => f.roll));
  const abs = (values: number[]) => values.map(Math.abs);

  return {
    mean_eye_openness: mean(eye),
    std_eye_openness: std(eye),
    mean_gaze_ratio: mean(gaze),
    std_gaze_ratio: std(gaze),
    mean_pitch: mean(pitch),
    mean_yaw: mean(yaw),
    mean_roll: mean(roll),
    mean_abs_pitch: mean(abs(pitch)),
    mean_abs_yaw: mean(abs(yaw)),
    mean_abs_roll: mean(abs(roll)),
    face_visibility_ratio: faceFrames.length / processedFrames,
  };
}
