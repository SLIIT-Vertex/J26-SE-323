/// <reference types="vite/client" />

import { describe, expect, it } from "vitest";

import mediapipeBundle from "../node_modules/@mediapipe/tasks-vision/vision_bundle.mjs?raw";
import {
  DISABLED_TELEMETRY_URL,
  disableMediapipeTelemetry,
  isMediapipeBundle,
  MEDIAPIPE_TELEMETRY_URL,
} from "./mediapipeTelemetry";

describe("disableMediapipeTelemetry", () => {
  it("replaces every occurrence of the logging URL", () => {
    const result = disableMediapipeTelemetry(
      `send({url:"${MEDIAPIPE_TELEMETRY_URL}"}); other("${MEDIAPIPE_TELEMETRY_URL}")`,
    );
    expect(result.replaced).toBe(2);
    expect(result.code).not.toContain(MEDIAPIPE_TELEMETRY_URL);
    expect(result.code).toContain(DISABLED_TELEMETRY_URL);
  });

  it("leaves code without the URL unchanged", () => {
    expect(disableMediapipeTelemetry("const a = 1;")).toEqual({ code: "const a = 1;", replaced: 0 });
  });

  it("finds exactly one logging URL in the installed @mediapipe/tasks-vision bundle", () => {
    const result = disableMediapipeTelemetry(mediapipeBundle);
    expect(result.replaced).toBe(1);
    expect(result.code).not.toContain("odml.pa.googleapis.com");
  });

  it("uses an address that fetch rejects without sending anything", async () => {
    await expect(fetch(DISABLED_TELEMETRY_URL, { method: "POST", body: "x" })).rejects.toThrow();
  });
});

describe("isMediapipeBundle", () => {
  it.each([
    ["/app/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs", true],
    ["C:\\app\\node_modules\\@mediapipe\\tasks-vision\\vision_bundle.mjs", true],
    ["/app/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs?v=9a406cea", true],
    ["/app/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs?raw", false],
    ["/app/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs?url", false],
    ["/app/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs?inline", false],
    ["/app/build-plugins/mediapipeTelemetry.ts", false],
    ["/app/src/features/learner-state/visual/faceLandmarker.ts", false],
  ])("%s -> %s", (id, expected) => {
    expect(isMediapipeBundle(id)).toBe(expected);
  });

  it("the test's own constant is not rewritten", () => {
    expect(MEDIAPIPE_TELEMETRY_URL).toBe(["https://odml.pa", "googleapis.com/v1/log"].join("."));
  });
});
