import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { VisualFeatureWindow } from "../../gamification/api/generated";
import type { ApiVisualFeatures, ApiVisualResult } from "../visual/apiVisualFeatures";
import { toGameVisualSnapshot, useGameVisualFeatures } from "./useGameVisualFeatures";

const pipeline = vi.hoisted(() => ({
  start: vi.fn(async () => {}),
  stop: vi.fn(),
  result: { usable: false, reason: "no-samples" } as unknown,
}));

vi.mock("../useVisualFeatures", () => ({
  useVisualFeatures: () => ({
    status: { state: "idle" },
    start: pipeline.start,
    stop: pipeline.stop,
    getVisualFeatures: () => pipeline.result,
    getSampleCounts: () => ({ samples: 0, withFace: 0 }),
  }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const FEATURES: ApiVisualFeatures = {
  mean_eye_openness: 0.3,
  std_eye_openness: 0.05,
  mean_gaze_ratio: 0.5,
  std_gaze_ratio: 0.04,
  mean_pitch: 2,
  mean_yaw: -3,
  mean_roll: 1,
  mean_abs_pitch: 4,
  mean_abs_yaw: 5,
  mean_abs_roll: 2,
  face_visibility_ratio: 0.9,
};
const NO_VISUAL_EVIDENCE: ApiVisualFeatures = {
  ...Object.fromEntries(Object.keys(FEATURES).map((key) => [key, 0])),
} as ApiVisualFeatures;

describe("toGameVisualSnapshot", () => {
  it("sends nothing before the camera has taken a sample", () => {
    expect(
      toGameVisualSnapshot({ usable: false, reason: "no-samples", visual: NO_VISUAL_EVIDENCE }),
    ).toBeNull();
  });

  it("sends a copy of usable features", () => {
    const result: ApiVisualResult = { usable: true, visual: FEATURES };
    const snapshot = toGameVisualSnapshot(result);
    expect(snapshot).toEqual(FEATURES);
    expect(snapshot).not.toBe(FEATURES);
  });

  it.each(["no-face", "no-head-pose", "invalid-value"] as const)(
    "sends no visual evidence when the camera is on but %s",
    (reason) => {
      const snapshot = toGameVisualSnapshot({ usable: false, reason, visual: NO_VISUAL_EVIDENCE });
      expect(snapshot).toEqual(NO_VISUAL_EVIDENCE);
      expect(snapshot?.face_visibility_ratio).toBe(0);
    },
  );
});

describe("useGameVisualFeatures", () => {
  let host: HTMLDivElement;
  let root: Root;
  let latest: ReturnType<typeof useGameVisualFeatures>;

  function Probe({ enabled }: { enabled: boolean }) {
    latest = useGameVisualFeatures({ enabled });
    return null;
  }

  function render(enabled: boolean) {
    act(() => root.render(<Probe enabled={enabled} />));
  }

  beforeEach(() => {
    pipeline.start.mockClear();
    pipeline.stop.mockClear();
    pipeline.result = { usable: false, reason: "no-samples", visual: NO_VISUAL_EVIDENCE };
    host = document.createElement("div");
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
  });

  it("does not start the camera without consent", () => {
    render(false);
    expect(pipeline.start).not.toHaveBeenCalled();
    expect(latest.visualFeatures()).toBeNull();
  });

  it("starts the camera when enabled and stops it when consent is withdrawn", () => {
    render(true);
    expect(pipeline.start).toHaveBeenCalledTimes(1);

    render(false);
    expect(pipeline.stop).toHaveBeenCalledTimes(1);
  });

  it("stops the camera when the game screen unmounts", () => {
    render(true);
    act(() => root.unmount());
    expect(pipeline.stop).toHaveBeenCalledTimes(1);
    root = createRoot(host);
  });

  it("returns the current window when GameHost asks for it", () => {
    render(true);
    pipeline.result = { usable: true, visual: FEATURES };
    expect(latest.visualFeatures()).toEqual(FEATURES);
  });

  it("matches the callback type GameHost accepts", () => {
    render(true);
    const callback: () => VisualFeatureWindow | null = latest.visualFeatures;
    expect(typeof callback).toBe("function");
  });
});
