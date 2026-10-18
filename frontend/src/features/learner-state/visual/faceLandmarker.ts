// MediaPipe Face Landmarker, configured like the visual training notebook
// (Python MediaPipe 1.0.1, IMAGE mode, one face, detection/presence confidence 0.5).
//
// All assets are bundled with the app by Vite and loaded from the app's own origin:
// nothing is fetched from Google's CDN at runtime.

import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import wasmLoaderUrl from "@mediapipe/tasks-vision/vision_wasm_internal.js?url";
import wasmBinaryUrl from "@mediapipe/tasks-vision/vision_wasm_internal.wasm?url";
import nosimdLoaderUrl from "@mediapipe/tasks-vision/vision_wasm_nosimd_internal.js?url";
import nosimdBinaryUrl from "@mediapipe/tasks-vision/vision_wasm_nosimd_internal.wasm?url";

import modelUrl from "./assets/face_landmarker.task?url";
import type { Landmark } from "./headPose";

/** Must equal the exact version in package.json (checked by a test). */
export const MEDIAPIPE_TASKS_VISION_VERSION = "1.0.1";

/** The bundled model file. `latest` and `1` were identical when it was pinned (2026-10-14). */
export const FACE_LANDMARKER_MODEL = {
  file: "assets/face_landmarker.task",
  source:
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
  sizeBytes: 3_758_596,
  sha256: "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
} as const;

/** Options matching FaceLandmarkerOptions in the notebook. */
export const FACE_LANDMARKER_OPTIONS = {
  runningMode: "IMAGE",
  numFaces: 1,
  minFaceDetectionConfidence: 0.5,
  minFacePresenceConfidence: 0.5,
  outputFaceBlendshapes: false,
  outputFacialTransformationMatrixes: false,
} as const;

export type FaceDetector = {
  /** Landmarks of the first face, or null when no face is detected. */
  detect: (frame: HTMLCanvasElement) => Landmark[] | null;
  close: () => void;
};

export async function createFaceDetector(): Promise<FaceDetector> {
  const simd = await FilesetResolver.isSimdSupported();
  const wasmFileset = simd
    ? { wasmLoaderPath: wasmLoaderUrl, wasmBinaryPath: wasmBinaryUrl }
    : { wasmLoaderPath: nosimdLoaderUrl, wasmBinaryPath: nosimdBinaryUrl };

  const landmarker = await FaceLandmarker.createFromOptions(wasmFileset, {
    // CPU, like the Python pipeline used for training; also the most reliable in mobile WebViews.
    baseOptions: { modelAssetPath: modelUrl, delegate: "CPU" },
    ...FACE_LANDMARKER_OPTIONS,
  });

  return {
    detect(frame) {
      const result = landmarker.detect(frame);
      const face = result.faceLandmarks[0];
      return face && face.length > 0 ? face.map(({ x, y }) => ({ x, y })) : null;
    },
    close() {
      landmarker.close();
    },
  };
}
