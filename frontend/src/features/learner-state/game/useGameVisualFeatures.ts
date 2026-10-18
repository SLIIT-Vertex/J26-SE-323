// Connects the on-device visual pipeline to the game's answer flow (Option B).
//
// GameHost (features/gamification/GameHost.tsx) accepts an optional
// `visualFeatures: () => VisualFeatureWindow | null` callback, calls it once on Submit and sends
// the 11 numbers with the answer; the game backend records the learner-state window. This hook
// provides that callback. Raw frames never leave the device.
//
// The camera runs only while `enabled` is true. The caller sets it from the learner's camera
// consent (purpose `learner_state_camera`); this module does not decide consent.

import { useCallback, useEffect } from "react";

import { useVisualFeatures } from "../useVisualFeatures";
import type { ApiVisualFeatures, ApiVisualResult } from "../visual/apiVisualFeatures";

/**
 * The snapshot sent with one game answer, or null when there is no camera window.
 *
 * - No window yet (camera off, or no sample taken): null, so the answer carries no visual data.
 * - Camera on but no usable face data: the "no visual evidence" values with
 *   face_visibility_ratio = 0, which give the visual models zero weight in fusion.
 */
export function toGameVisualSnapshot(result: ApiVisualResult): ApiVisualFeatures | null {
  if (!result.usable && result.reason === "no-samples") return null;
  return { ...result.visual };
}

export function useGameVisualFeatures({ enabled }: { enabled: boolean }) {
  const { status, start, stop, getVisualFeatures } = useVisualFeatures();

  useEffect(() => {
    if (!enabled) return;
    void start();
    return stop;
  }, [enabled, start, stop]);

  /** Pass to `<GameHost visualFeatures={...} />`. */
  const visualFeatures = useCallback(
    () => toGameVisualSnapshot(getVisualFeatures()),
    [getVisualFeatures],
  );

  return { status, visualFeatures };
}
