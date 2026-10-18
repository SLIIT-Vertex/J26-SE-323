// Developer-only page for trying the on-device visual pipeline (development builds only).
// Open the app with ?dev=learner-state. The preview is mirrored for display only; the
// features are computed from the un-mirrored camera image.

import { useEffect, useRef, useState } from "react";

import "./LearnerStateDevPage.css";

import { type VisualPipelineStatus, useVisualFeatures } from "../useVisualFeatures";
import type { ApiVisualResult } from "../visual/apiVisualFeatures";
import { EquivalenceRunner } from "./EquivalenceRunner";

const STATUS_TEXT: Record<VisualPipelineStatus["state"], string> = {
  idle: "Camera is off.",
  "requesting-permission": "Waiting for camera permission…",
  "loading-model": "Loading the face model…",
  running: "Running on this device.",
  stopped: "Camera stopped.",
  error: "Camera unavailable.",
};

const ERROR_TEXT: Record<string, string> = {
  "insecure-context": "The camera needs HTTPS (or localhost).",
  unsupported: "This browser does not support camera access.",
  "permission-denied": "Camera permission was denied. Allow it in the browser or app settings.",
  "no-camera": "No suitable camera was found.",
  "camera-busy": "The camera is being used by another app.",
  "model-load-failed": "The face model could not be loaded.",
  unknown: "The camera could not be started.",
};

export default function LearnerStateDevPage() {
  const previewRef = useRef<HTMLVideoElement>(null);
  const { status, start, stop, getVisualFeatures, getSampleCounts } =
    useVisualFeatures(previewRef);
  const [snapshot, setSnapshot] = useState<{
    result: ApiVisualResult;
    counts: { samples: number; withFace: number };
  } | null>(null);

  useEffect(() => {
    if (status.state !== "running") return;
    const timer = setInterval(
      () => setSnapshot({ result: getVisualFeatures(), counts: getSampleCounts() }),
      1000,
    );
    return () => clearInterval(timer);
  }, [status.state, getVisualFeatures, getSampleCounts]);

  const busy = status.state === "requesting-permission" || status.state === "loading-model";

  return (
    <main className="ls-dev">
      <p className="eyebrow">Developer tool</p>
      <h1>Learner-state visual pipeline</h1>
      <p>
        Video stays on this device. Only the numbers below would be sent to the learner-state API.
      </p>

      <div className="ls-dev__controls">
        <button type="button" onClick={start} disabled={busy || status.state === "running"}>
          Start camera
        </button>
        <button type="button" onClick={stop} disabled={status.state !== "running" && !busy}>
          Stop camera
        </button>
      </div>

      <p role="status">
        {STATUS_TEXT[status.state]}
        {status.state === "error" ? ` ${ERROR_TEXT[status.kind]}` : ""}
      </p>

      <video ref={previewRef} className="ls-dev__preview" muted playsInline />

      {snapshot && status.state === "running" ? (
        <section>
          <h2>Last 10 seconds</h2>
          <p>
            Samples: {snapshot.counts.samples} / 30, with a face: {snapshot.counts.withFace}
            {snapshot.result.usable ? "" : ` — no usable visual evidence (${snapshot.result.reason})`}
          </p>
          <table className="ls-dev__table">
            <tbody>
              {Object.entries(snapshot.result.visual).map(([name, value]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{value.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      <EquivalenceRunner />
    </main>
  );
}
