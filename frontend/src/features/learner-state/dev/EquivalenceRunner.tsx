// Browser half of the local engineering equivalence test (docs/learner-state/10 §9).
//
// The developer picks the git-ignored folder of their own test frames written by
// research/learner-state/tools/mediapipe_equivalence.py. Each frame is decoded on this device,
// passed through the same MediaPipe detector and feature code as the live pipeline, and only the
// resulting numbers are saved to a file the developer chooses. Nothing is sent anywhere.

import { useState } from "react";

import { createFaceDetector, MEDIAPIPE_TASKS_VISION_VERSION } from "../visual/faceLandmarker";
import {
  extractFrameFeatures,
  FRAME_HEIGHT,
  FRAME_WIDTH,
  type FrameFeatures,
} from "../visual/frameFeatures";
import { aggregateWindow, type VisualWindowFeatures } from "../visual/windowFeatures";

type FrameResult = {
  file: string;
  landmarks: [number, number][] | null;
  features: { eye: number; gaze: number; pitch: number | null; yaw: number | null; roll: number | null } | null;
};
type Results = {
  pipeline: "browser";
  versions: Record<string, string>;
  clips: Record<string, { frames: FrameResult[]; window: VisualWindowFeatures }>;
};
type SavePicker = (options: {
  suggestedName: string;
  types: { description: string; accept: Record<string, string[]> }[];
}) => Promise<FileSystemFileHandle>;

const FRAME_FILE = /^frame_\d+\.png$/;
const CLIP_FOLDER = /^clip\d+$/;

/** Groups the picked files by clip folder: .../clipNN/frame_KK.png. */
export function groupFrames(files: readonly File[]): Map<string, File[]> {
  const clips = new Map<string, File[]>();
  for (const file of files) {
    const parts = file.webkitRelativePath.split("/");
    const clip = parts.at(-2) ?? "";
    if (!CLIP_FOLDER.test(clip) || !FRAME_FILE.test(file.name)) continue;
    clips.set(clip, [...(clips.get(clip) ?? []), file]);
  }
  for (const frames of clips.values()) frames.sort((a, b) => a.name.localeCompare(b.name));
  return new Map([...clips].sort(([a], [b]) => a.localeCompare(b)));
}

async function runEquivalence(
  clips: Map<string, File[]>,
  onProgress: (done: number) => void,
): Promise<Results> {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_WIDTH;
  canvas.height = FRAME_HEIGHT;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("2D canvas is not available");

  const detector = await createFaceDetector();
  const results: Results = {
    pipeline: "browser",
    versions: { mediapipe_tasks_vision: MEDIAPIPE_TASKS_VISION_VERSION, user_agent: navigator.userAgent },
    clips: {},
  };
  let done = 0;
  try {
    for (const [clip, files] of clips) {
      const frames: FrameResult[] = [];
      const faceFrames: FrameFeatures[] = [];
      for (const file of files) {
        // PNG is lossless, so this canvas holds the same pixels the Python pipeline reads.
        const bitmap = await createImageBitmap(file, {
          colorSpaceConversion: "none",
          premultiplyAlpha: "none",
        });
        if (bitmap.width !== FRAME_WIDTH || bitmap.height !== FRAME_HEIGHT) {
          throw new Error(`${clip}/${file.name} is not ${FRAME_WIDTH}x${FRAME_HEIGHT}`);
        }
        context.drawImage(bitmap, 0, 0);
        bitmap.close();

        const landmarks = detector.detect(canvas);
        if (landmarks === null) {
          frames.push({ file: file.name, landmarks: null, features: null });
        } else {
          const features = extractFrameFeatures(landmarks);
          faceFrames.push(features);
          frames.push({
            file: file.name,
            landmarks: landmarks.map(({ x, y }) => [x, y]),
            features: {
              eye: features.eyeOpenness,
              gaze: features.gazeRatio,
              pitch: features.pitch,
              yaw: features.yaw,
              roll: features.roll,
            },
          });
        }
        onProgress(++done);
      }
      results.clips[clip] = { frames, window: aggregateWindow(files.length, faceFrames) };
    }
  } finally {
    detector.close();
  }
  return results;
}

export function EquivalenceRunner() {
  const [clips, setClips] = useState<Map<string, File[]> | null>(null);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<Results | null>(null);
  const [message, setMessage] = useState("");

  const total = clips ? [...clips.values()].reduce((sum, files) => sum + files.length, 0) : 0;
  const picker = (window as unknown as { showSaveFilePicker?: SavePicker }).showSaveFilePicker;

  async function run() {
    if (!clips) return;
    setResults(null);
    setMessage("Running…");
    try {
      const output = await runEquivalence(clips, setProgress);
      setResults(output);
      setMessage("Done. Save the results as browser-results.json in local-test-frames.");
    } catch (error) {
      setMessage(`Failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  async function save() {
    if (!results || !picker) return;
    try {
      const handle = await picker({
        suggestedName: "browser-results.json",
        types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(JSON.stringify(results));
      await writable.close();
      setMessage("Saved.");
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setMessage(`Could not save: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
  }

  return (
    <section>
      <h2>Equivalence test (local frames)</h2>
      <p>
        Pick the <code>research/learner-state/local-test-frames/frames</code> folder. Frames are
        processed on this device; only the numbers are saved, to a file you choose.
      </p>
      <input
        type="file"
        multiple
        {...{ webkitdirectory: "" }}
        onChange={(event) => {
          setResults(null);
          setProgress(0);
          setMessage("");
          setClips(groupFrames(Array.from(event.target.files ?? [])));
        }}
      />
      {clips ? (
        <p>
          {clips.size} clips, {total} frames.{" "}
          <button type="button" onClick={run} disabled={total === 0 || message === "Running…"}>
            Run
          </button>{" "}
          {progress}/{total}
        </p>
      ) : null}
      {results ? (
        <button type="button" onClick={save} disabled={!picker}>
          Save results
        </button>
      ) : null}
      {results && !picker ? <p>Saving needs Microsoft Edge or Google Chrome.</p> : null}
      <p role="status">{message}</p>
    </section>
  );
}
