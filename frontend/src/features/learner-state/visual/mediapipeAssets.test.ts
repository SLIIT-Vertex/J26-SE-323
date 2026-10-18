import { describe, expect, it } from "vitest";

import packageJson from "../../../../package.json";
import modelDataUrl from "./assets/face_landmarker.task?inline";
import {
  FACE_LANDMARKER_MODEL,
  FACE_LANDMARKER_OPTIONS,
  MEDIAPIPE_TASKS_VISION_VERSION,
} from "./faceLandmarker";

async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

describe("pinned MediaPipe assets", () => {
  it("pins @mediapipe/tasks-vision to the exact notebook version", () => {
    expect(packageJson.dependencies["@mediapipe/tasks-vision"]).toBe(
      MEDIAPIPE_TASKS_VISION_VERSION,
    );
    expect(MEDIAPIPE_TASKS_VISION_VERSION).toBe("1.0.1");
  });

  it("bundles the expected face landmarker model file", async () => {
    const base64 = modelDataUrl.slice(modelDataUrl.indexOf(",") + 1);
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));

    expect(bytes.length).toBe(FACE_LANDMARKER_MODEL.sizeBytes);
    expect(await sha256Hex(bytes)).toBe(FACE_LANDMARKER_MODEL.sha256);
  });

  it("uses the notebook's detector options", () => {
    expect(FACE_LANDMARKER_OPTIONS).toMatchObject({
      runningMode: "IMAGE",
      numFaces: 1,
      minFaceDetectionConfidence: 0.5,
      minFacePresenceConfidence: 0.5,
    });
  });
});
