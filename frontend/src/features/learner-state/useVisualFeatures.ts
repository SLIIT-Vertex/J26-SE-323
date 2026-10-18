// React hook that runs the on-device visual pipeline for one learning screen:
// camera -> 640x480 frame -> MediaPipe landmarks -> per-frame features -> 10-second window.
//
// Raw frames never leave the device: only the aggregated numbers from `getVisualFeatures()`
// are meant to be sent to the learner-state API.

import { type RefObject, useCallback, useEffect, useRef, useState } from "react";

import { CameraError, type CameraErrorKind, openCamera, stopStream } from "./camera/camera";
import { type ApiVisualResult, toApiVisualFeatures } from "./visual/apiVisualFeatures";
import { createFaceDetector, type FaceDetector } from "./visual/faceLandmarker";
import { createFrameGrabber } from "./visual/frameCapture";
import { SAMPLE_INTERVAL_MS, VisualFeatureSampler } from "./visual/sampler";

export type VisualPipelineStatus =
  | { state: "idle" }
  | { state: "requesting-permission" }
  | { state: "loading-model" }
  | { state: "running" }
  | { state: "stopped" }
  | { state: "error"; kind: CameraErrorKind | "model-load-failed" };

type Running = {
  stream: MediaStream;
  video: HTMLVideoElement;
  ownsVideo: boolean;
  detector: FaceDetector | null;
  timer: ReturnType<typeof setTimeout> | null;
  sampler: VisualFeatureSampler<HTMLCanvasElement> | null;
};

/**
 * @param previewRef optional visible <video> for a camera preview. Without it, a detached
 *   (never displayed) video element is used.
 */
export function useVisualFeatures(previewRef?: RefObject<HTMLVideoElement | null>) {
  const [status, setStatus] = useState<VisualPipelineStatus>({ state: "idle" });
  const running = useRef<Running | null>(null);
  const attempt = useRef(0);

  const teardown = useCallback(() => {
    const current = running.current;
    running.current = null;
    if (!current) return;
    if (current.timer !== null) clearTimeout(current.timer);
    current.detector?.close();
    stopStream(current.stream);
    current.video.pause();
    current.video.srcObject = null;
    if (current.ownsVideo) current.video.remove();
  }, []);

  const stop = useCallback(() => {
    attempt.current += 1; // cancels a start() that is still in progress
    teardown();
    setStatus({ state: "stopped" });
  }, [teardown]);

  const start = useCallback(async () => {
    teardown();
    const id = ++attempt.current;
    const cancelled = () => id !== attempt.current;

    setStatus({ state: "requesting-permission" });
    let stream: MediaStream;
    try {
      stream = await openCamera();
    } catch (error) {
      if (!cancelled()) {
        setStatus({ state: "error", kind: error instanceof CameraError ? error.kind : "unknown" });
      }
      return;
    }
    if (cancelled()) {
      stopStream(stream);
      return;
    }

    const preview = previewRef?.current ?? null;
    const video = preview ?? document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    running.current = {
      stream,
      video,
      ownsVideo: preview === null,
      detector: null,
      timer: null,
      sampler: null,
    };

    // If the camera is unplugged or taken by the operating system, stop cleanly.
    for (const track of stream.getVideoTracks()) {
      track.addEventListener("ended", () => {
        if (!cancelled()) stop();
      });
    }

    setStatus({ state: "loading-model" });
    try {
      await video.play();
      const detector = await createFaceDetector();
      if (cancelled() || !running.current) {
        detector.close();
        return;
      }
      running.current.detector = detector;
    } catch {
      if (!cancelled()) {
        teardown();
        setStatus({ state: "error", kind: "model-load-failed" });
      }
      return;
    }

    const grabber = createFrameGrabber(video);
    const { detector } = running.current;
    const sampler = new VisualFeatureSampler<HTMLCanvasElement>({
      grabFrame: grabber.grab,
      detectLandmarks: (frame) => detector?.detect(frame) ?? null,
      now: () => performance.now(),
    });
    running.current.sampler = sampler;

    const tick = () => {
      const current = running.current;
      if (cancelled() || !current) return;
      sampler.sampleOnce();
      current.timer = setTimeout(tick, SAMPLE_INTERVAL_MS);
    };
    tick();
    setStatus({ state: "running" });
  }, [previewRef, stop, teardown]);

  // Leaving the learning screen unmounts the hook: stop the camera and release MediaPipe.
  useEffect(
    () => () => {
      attempt.current += 1;
      teardown();
    },
    [teardown],
  );

  /** Visual features of the last 10 seconds, ready for the learner-state API. */
  const getVisualFeatures = useCallback((): ApiVisualResult => {
    return toApiVisualFeatures(running.current?.sampler?.currentWindow() ?? null);
  }, []);

  /** Number of samples and of samples with a face in the last 10 seconds (for display). */
  const getSampleCounts = useCallback(() => {
    const recent = running.current?.sampler?.recentSamples() ?? [];
    return {
      samples: recent.length,
      withFace: recent.filter((sample) => sample.features !== null).length,
    };
  }, []);

  return { status, start, stop, getVisualFeatures, getSampleCounts };
}
