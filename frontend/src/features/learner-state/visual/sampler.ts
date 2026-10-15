// Samples per-frame visual features about three times per second and aggregates the most recent
// 10 seconds into one learner-state visual window.
//
// Only numeric per-frame features are kept in memory; frames are discarded after each sample.

import { extractFrameFeatures, type FrameFeatures, type Landmark } from "./frameFeatures";
import { aggregateWindow, SAMPLES_PER_WINDOW, type VisualWindowFeatures } from "./windowFeatures";

export const WINDOW_DURATION_MS = 10_000;

/**
 * 30 samples spread over 10 s with the first and last at the window edges, like
 * np.linspace(0, last_frame, 30) over a 10-second DAiSEE clip (≈ 2.9 samples per second).
 */
export const SAMPLE_INTERVAL_MS = WINDOW_DURATION_MS / (SAMPLES_PER_WINDOW - 1);

/** One processed sample: features when a face was detected, null when it was not. */
export type VisualSample = { at: number; features: FrameFeatures | null };

export type SamplerDependencies<Frame> = {
  grabFrame: () => Frame | null;
  detectLandmarks: (frame: Frame) => Landmark[] | null;
  now: () => number;
};

export class VisualFeatureSampler<Frame> {
  private samples: VisualSample[] = [];

  constructor(private readonly deps: SamplerDependencies<Frame>) {}

  /** Take one sample. Returns false if the video had no frame to sample yet. */
  sampleOnce(): boolean {
    const frame = this.deps.grabFrame();
    if (frame === null) return false;

    const landmarks = this.deps.detectLandmarks(frame);
    const features = landmarks ? extractFrameFeatures(landmarks) : null;

    this.samples.push({ at: this.deps.now(), features });
    if (this.samples.length > SAMPLES_PER_WINDOW) this.samples.shift();
    return true;
  }

  /** Samples from the last 10 seconds (at most 30). */
  recentSamples(): readonly VisualSample[] {
    // A small allowance keeps the oldest sample of a full 30-sample window when timers run late.
    const oldest = this.deps.now() - WINDOW_DURATION_MS - SAMPLE_INTERVAL_MS / 2;
    return this.samples.filter((sample) => sample.at >= oldest);
  }

  /** Aggregated features of the last 10 seconds, or null if nothing was sampled in that time. */
  currentWindow(): VisualWindowFeatures | null {
    const recent = this.recentSamples();
    if (recent.length === 0) return null;
    const faceFrames = recent
      .map((sample) => sample.features)
      .filter((features): features is FrameFeatures => features !== null);
    return aggregateWindow(recent.length, faceFrames);
  }

  reset(): void {
    this.samples = [];
  }
}
