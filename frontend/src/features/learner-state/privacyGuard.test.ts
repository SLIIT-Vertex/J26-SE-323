import { describe, expect, it } from "vitest";

// Raw camera frames must stay on the device. This guard scans the on-device camera and visual
// code (not its tests) for browser APIs that could encode, record, store or send image data.
// Network calls belong only in the learner-state API client, which sends derived numbers.

const sources = import.meta.glob<string>(
  [
    "./camera/*.ts",
    "./visual/*.ts",
    "./game/*.ts",
    "./dev/*.tsx",
    "./useVisualFeatures.ts",
    "!./**/*.test.ts",
  ],
  { query: "?raw", import: "default", eager: true },
);

const FORBIDDEN = [
  "toDataURL",
  "toBlob",
  "convertToBlob",
  "getImageData",
  "MediaRecorder",
  "captureStream",
  "createObjectURL",
  "fetch(",
  "XMLHttpRequest",
  "sendBeacon",
  "WebSocket",
  "localStorage",
  "sessionStorage",
  "indexedDB",
  "caches.",
];

describe("on-device privacy guard", () => {
  it("scans the camera and visual pipeline files", () => {
    const files = Object.keys(sources);
    expect(files).toContain("./useVisualFeatures.ts");
    expect(files).toContain("./camera/camera.ts");
    expect(files).toContain("./visual/frameCapture.ts");
    expect(files).toContain("./visual/faceLandmarker.ts");
    expect(files).toContain("./game/useGameVisualFeatures.ts");
  });

  it.each(Object.entries(sources))("%s does not export, store or send frames", (_, code) => {
    // Comments may mention these names; only code is checked.
    const withoutComments = code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    for (const api of FORBIDDEN) expect(withoutComments).not.toContain(api);
  });
});
