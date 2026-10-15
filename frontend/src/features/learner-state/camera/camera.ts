// Live camera access with getUserMedia. Works in browsers and in Capacitor's WebView
// (Android, iOS 14.3+). The stream is only shown locally and sampled on this device.

export type CameraErrorKind =
  | "insecure-context"
  | "unsupported"
  | "permission-denied"
  | "no-camera"
  | "camera-busy"
  | "unknown";

export class CameraError extends Error {
  constructor(
    readonly kind: CameraErrorKind,
    cause?: unknown,
  ) {
    super(`Camera unavailable: ${kind}`, { cause });
    this.name = "CameraError";
  }
}

/** Front camera, no audio, close to the 640 x 480 training frames. */
export const CAMERA_CONSTRAINTS: MediaStreamConstraints = {
  audio: false,
  video: {
    facingMode: "user",
    width: { ideal: 640 },
    height: { ideal: 480 },
    frameRate: { ideal: 15, max: 30 },
  },
};

export function classifyCameraError(error: unknown): CameraErrorKind {
  const name = error instanceof Error || error instanceof DOMException ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
    case "PermissionDeniedError":
      return "permission-denied";
    case "NotFoundError":
    case "DevicesNotFoundError":
    case "OverconstrainedError":
      return "no-camera";
    case "NotReadableError":
    case "TrackStartError":
    case "AbortError":
      return "camera-busy";
    default:
      return "unknown";
  }
}

export type CameraEnvironment = {
  isSecureContext: boolean;
  mediaDevices: Pick<MediaDevices, "getUserMedia"> | undefined;
};

function browserEnvironment(): CameraEnvironment {
  return {
    isSecureContext: globalThis.isSecureContext ?? false,
    mediaDevices: globalThis.navigator?.mediaDevices,
  };
}

export async function openCamera(
  environment: CameraEnvironment = browserEnvironment(),
): Promise<MediaStream> {
  // getUserMedia only exists on HTTPS pages, localhost and the Capacitor app.
  if (!environment.isSecureContext) throw new CameraError("insecure-context");
  if (!environment.mediaDevices?.getUserMedia) throw new CameraError("unsupported");

  try {
    return await environment.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS);
  } catch (error) {
    throw new CameraError(classifyCameraError(error), error);
  }
}

/** Stop every track so the camera turns off (and its indicator light goes out). */
export function stopStream(stream: Pick<MediaStream, "getTracks"> | null | undefined): void {
  for (const track of stream?.getTracks() ?? []) track.stop();
}
