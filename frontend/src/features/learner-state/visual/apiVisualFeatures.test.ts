import { describe, expect, it } from "vitest";

import { toApiVisualFeatures } from "./apiVisualFeatures";
import type { VisualWindowFeatures } from "./windowFeatures";

const complete: VisualWindowFeatures = {
  mean_eye_openness: 0.27,
  std_eye_openness: 0.04,
  mean_gaze_ratio: 0.52,
  std_gaze_ratio: 0.08,
  mean_pitch: 8,
  mean_yaw: 5,
  mean_roll: 3,
  mean_abs_pitch: 8,
  mean_abs_yaw: 5,
  mean_abs_roll: 3,
  face_visibility_ratio: 0.9,
};

const noFace: VisualWindowFeatures = {
  mean_eye_openness: null,
  std_eye_openness: null,
  mean_gaze_ratio: null,
  std_gaze_ratio: null,
  mean_pitch: null,
  mean_yaw: null,
  mean_roll: null,
  mean_abs_pitch: null,
  mean_abs_yaw: null,
  mean_abs_roll: null,
  face_visibility_ratio: 0,
};

function expectNoVisualEvidence(result: ReturnType<typeof toApiVisualFeatures>) {
  expect(result.usable).toBe(false);
  expect(result.visual.face_visibility_ratio).toBe(0);
  for (const value of Object.values(result.visual)) expect(value).toBe(0);
}

describe("toApiVisualFeatures", () => {
  it("passes a complete window through unchanged", () => {
    expect(toApiVisualFeatures(complete)).toEqual({ usable: true, visual: complete });
  });

  it("marks a window without samples as unusable", () => {
    const result = toApiVisualFeatures(null);
    expectNoVisualEvidence(result);
    expect(result.usable || result.reason).toBe("no-samples");
  });

  it("marks a window without any face as unusable", () => {
    const result = toApiVisualFeatures(noFace);
    expectNoVisualEvidence(result);
    expect(result.usable || result.reason).toBe("no-face");
  });

  it("marks a window whose head pose never solved as unusable", () => {
    const result = toApiVisualFeatures({
      ...complete,
      mean_pitch: null,
      mean_yaw: null,
      mean_roll: null,
      mean_abs_pitch: null,
      mean_abs_yaw: null,
      mean_abs_roll: null,
    });
    expectNoVisualEvidence(result);
    expect(result.usable || result.reason).toBe("no-head-pose");
  });

  it("never sends non-finite numbers", () => {
    const result = toApiVisualFeatures({ ...complete, std_gaze_ratio: Number.NaN });
    expectNoVisualEvidence(result);
    expect(result.usable || result.reason).toBe("invalid-value");
  });

  it("does not share the placeholder object between calls", () => {
    const first = toApiVisualFeatures(null);
    first.visual.mean_yaw = 99;
    expect(toApiVisualFeatures(null).visual.mean_yaw).toBe(0);
  });
});
