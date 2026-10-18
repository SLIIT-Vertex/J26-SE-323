import { describe, expect, it } from "vitest";

import fixture from "./__fixtures__/visual-features.json";
import {
  eyeOpenness,
  extractFrameFeatures,
  type FrameFeatures,
  gazeRatios,
  LEFT_EYE,
  type Landmark,
  normalizePitch,
  normalizeRoll,
  RIGHT_EYE,
} from "./frameFeatures";
import { estimateHeadPose } from "./headPose";
import { aggregateWindow } from "./windowFeatures";

// Reference values come from the training notebook's own functions run with OpenCV
// (research/learner-state/tools/generate_visual_feature_fixtures.py).
//
// Scope: these tests start from given landmarks. They show that the TypeScript feature
// calculations match the Python/OpenCV training implementation. They do NOT show that browser
// MediaPipe produces the same landmarks as the notebook's Python MediaPipe pipeline; that has to
// be verified separately on the same input frames.

const LANDMARK_COUNT = 478;
const ANGLE_TOLERANCE_DEGREES = 1e-3;
const { width, height } = fixture.frame;

function toLandmarks(sparse: Record<string, number[]>): Landmark[] {
  const landmarks: Landmark[] = Array.from({ length: LANDMARK_COUNT }, () => ({ x: 0.5, y: 0.5 }));
  for (const [index, [x, y]] of Object.entries(sparse)) landmarks[Number(index)] = { x, y };
  return landmarks;
}

describe.each(fixture.frames)("frame $name", ({ landmarks, expected }) => {
  const points = toLandmarks(landmarks);

  it("matches eye openness", () => {
    expect(eyeOpenness(points, LEFT_EYE)).toBeCloseTo(expected.left_eye_openness, 12);
    expect(eyeOpenness(points, RIGHT_EYE)).toBeCloseTo(expected.right_eye_openness, 12);
  });

  it("matches gaze ratio", () => {
    const gaze = gazeRatios(points);
    expect(gaze.left).toBeCloseTo(expected.left_gaze_ratio, 12);
    expect(gaze.right).toBeCloseTo(expected.right_gaze_ratio, 12);
  });

  it("matches the raw OpenCV head pose", () => {
    const pose = estimateHeadPose(points, width, height);
    expect(pose).not.toBeNull();
    expect(Math.abs((pose?.pitch ?? Number.NaN) - expected.raw_pitch)).toBeLessThan(
      ANGLE_TOLERANCE_DEGREES,
    );
    expect(Math.abs((pose?.yaw ?? Number.NaN) - expected.raw_yaw)).toBeLessThan(
      ANGLE_TOLERANCE_DEGREES,
    );
    expect(Math.abs((pose?.roll ?? Number.NaN) - expected.raw_roll)).toBeLessThan(
      ANGLE_TOLERANCE_DEGREES,
    );
  });

  it("matches the per-frame features after normalisation", () => {
    const features = extractFrameFeatures(points, width, height);
    expect(features.eyeOpenness).toBeCloseTo(expected.mean_eye_openness, 12);
    expect(features.gazeRatio).toBeCloseTo(expected.mean_gaze_ratio, 12);
    expect(Math.abs((features.pitch ?? Number.NaN) - expected.pitch)).toBeLessThan(
      ANGLE_TOLERANCE_DEGREES,
    );
    expect(Math.abs((features.yaw ?? Number.NaN) - expected.yaw)).toBeLessThan(
      ANGLE_TOLERANCE_DEGREES,
    );
    expect(Math.abs((features.roll ?? Number.NaN) - expected.roll)).toBeLessThan(
      ANGLE_TOLERANCE_DEGREES,
    );
  });
});

describe("angle normalisation", () => {
  it.each(fixture.normalization.roll)("roll %d", (input, expected) => {
    expect(normalizeRoll(input)).toBeCloseTo(expected, 10);
  });

  it.each(fixture.normalization.pitch)("pitch %d", (input, expected) => {
    expect(normalizePitch(input)).toBeCloseTo(expected, 10);
  });
});

describe.each(fixture.windows)("window $name", ({ processed_frames, face_frames, expected }) => {
  it("matches the notebook aggregation", () => {
    const frames: FrameFeatures[] = face_frames.map((f) => ({
      eyeOpenness: f.eye,
      gazeRatio: f.gaze,
      pitch: f.pitch,
      yaw: f.yaw,
      roll: f.roll,
    }));
    const features = aggregateWindow(processed_frames, frames);

    for (const [name, value] of Object.entries(expected)) {
      const actual = features[name as keyof typeof features];
      if (value === null) expect(actual).toBeNull();
      else expect(actual).toBeCloseTo(value, 12);
    }
  });
});
