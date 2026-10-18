import { describe, expect, it } from "vitest";

import fixture from "./__fixtures__/visual-features.json";
import { extractFrameFeatures, type Landmark } from "./frameFeatures";
import {
  SAMPLE_INTERVAL_MS,
  type SamplerDependencies,
  VisualFeatureSampler,
  WINDOW_DURATION_MS,
} from "./sampler";
import { aggregateWindow, SAMPLES_PER_WINDOW } from "./windowFeatures";

type FakeFrame = { landmarks: Landmark[] | null };

function toLandmarks(sparse: Record<string, number[]>): Landmark[] {
  const landmarks: Landmark[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5 }));
  for (const [index, [x, y]] of Object.entries(sparse)) landmarks[Number(index)] = { x, y };
  return landmarks;
}

const faces = fixture.frames.map((frame) => toLandmarks(frame.landmarks));

function setup(frames: (FakeFrame | null)[]) {
  let clock = 0;
  let next = 0;
  const deps: SamplerDependencies<FakeFrame> = {
    grabFrame: () => frames[next++ % frames.length],
    detectLandmarks: (frame) => frame.landmarks,
    now: () => clock,
  };
  const sampler = new VisualFeatureSampler(deps);
  const advance = (ms: number) => {
    clock += ms;
  };
  return { sampler, advance };
}

describe("sampling rate", () => {
  it("takes 30 samples spread over 10 seconds (about 3 per second)", () => {
    expect(SAMPLE_INTERVAL_MS * (SAMPLES_PER_WINDOW - 1)).toBeCloseTo(WINDOW_DURATION_MS, 9);
    expect(1000 / SAMPLE_INTERVAL_MS).toBeGreaterThan(2.8);
    expect(1000 / SAMPLE_INTERVAL_MS).toBeLessThan(3.1);
  });
});

describe("VisualFeatureSampler", () => {
  it("returns null before anything has been sampled", () => {
    const { sampler } = setup([{ landmarks: faces[0] }]);
    expect(sampler.currentWindow()).toBeNull();
  });

  it("skips ticks when the video has no frame yet", () => {
    const { sampler } = setup([null]);
    expect(sampler.sampleOnce()).toBe(false);
    expect(sampler.recentSamples()).toHaveLength(0);
  });

  it("aggregates a full window exactly like aggregateWindow", () => {
    const { sampler, advance } = setup(faces.slice(0, 30).map((landmarks) => ({ landmarks })));
    for (let i = 0; i < 30; i++) {
      if (i > 0) advance(SAMPLE_INTERVAL_MS);
      sampler.sampleOnce();
    }

    const expected = aggregateWindow(
      30,
      faces.slice(0, 30).map((landmarks) => extractFrameFeatures(landmarks)),
    );
    expect(sampler.recentSamples()).toHaveLength(30);
    expect(sampler.currentWindow()).toEqual(expected);
  });

  it("keeps at most 30 samples", () => {
    const { sampler, advance } = setup([{ landmarks: faces[0] }]);
    for (let i = 0; i < 45; i++) {
      advance(SAMPLE_INTERVAL_MS);
      sampler.sampleOnce();
    }
    expect(sampler.recentSamples()).toHaveLength(30);
  });

  it("drops samples older than 10 seconds", () => {
    const { sampler, advance } = setup([{ landmarks: faces[0] }]);
    for (let i = 0; i < 5; i++) {
      advance(SAMPLE_INTERVAL_MS);
      sampler.sampleOnce();
    }
    // Just over 10 s plus the late-timer allowance after the fifth sample.
    advance(WINDOW_DURATION_MS + SAMPLE_INTERVAL_MS);
    sampler.sampleOnce();
    expect(sampler.recentSamples()).toHaveLength(1);

    advance(2 * WINDOW_DURATION_MS);
    expect(sampler.currentWindow()).toBeNull();
  });

  it("counts samples without a face towards visibility", () => {
    const frames: FakeFrame[] = [
      { landmarks: faces[0] },
      { landmarks: null },
      { landmarks: faces[1] },
      { landmarks: null },
    ];
    const { sampler, advance } = setup(frames);
    for (let i = 0; i < 4; i++) {
      advance(SAMPLE_INTERVAL_MS);
      sampler.sampleOnce();
    }
    const window = sampler.currentWindow();
    expect(window?.face_visibility_ratio).toBe(0.5);
    expect(window).toEqual(
      aggregateWindow(4, [extractFrameFeatures(faces[0]), extractFrameFeatures(faces[1])]),
    );
  });

  it("reports a window with no face at all", () => {
    const { sampler, advance } = setup([{ landmarks: null }]);
    for (let i = 0; i < 3; i++) {
      advance(SAMPLE_INTERVAL_MS);
      sampler.sampleOnce();
    }
    const window = sampler.currentWindow();
    expect(window?.face_visibility_ratio).toBe(0);
    expect(window?.mean_eye_openness).toBeNull();
  });

  it("reset clears all samples", () => {
    const { sampler } = setup([{ landmarks: faces[0] }]);
    sampler.sampleOnce();
    sampler.reset();
    expect(sampler.currentWindow()).toBeNull();
  });
});
