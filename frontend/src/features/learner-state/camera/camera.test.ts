import { describe, expect, it, vi } from "vitest";

import {
  CAMERA_CONSTRAINTS,
  CameraError,
  type CameraEnvironment,
  classifyCameraError,
  openCamera,
  stopStream,
} from "./camera";

function environment(getUserMedia: (c: MediaStreamConstraints) => unknown): CameraEnvironment {
  return {
    isSecureContext: true,
    mediaDevices: { getUserMedia: getUserMedia as MediaDevices["getUserMedia"] },
  };
}

async function errorKindOf(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    return error instanceof CameraError ? error.kind : "not-a-camera-error";
  }
  return "no-error";
}

describe("openCamera", () => {
  it("requests the front camera at 640x480 and never audio", async () => {
    const stream = {} as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);

    await expect(openCamera(environment(getUserMedia))).resolves.toBe(stream);
    expect(getUserMedia).toHaveBeenCalledWith(CAMERA_CONSTRAINTS);
    expect(CAMERA_CONSTRAINTS.audio).toBe(false);
    expect(CAMERA_CONSTRAINTS.video).toMatchObject({
      facingMode: "user",
      width: { ideal: 640 },
      height: { ideal: 480 },
    });
  });

  it("refuses to run outside a secure context", async () => {
    const getUserMedia = vi.fn();
    const kind = await errorKindOf(
      openCamera({
        isSecureContext: false,
        mediaDevices: { getUserMedia: getUserMedia as MediaDevices["getUserMedia"] },
      }),
    );
    expect(kind).toBe("insecure-context");
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("reports missing camera support", async () => {
    expect(await errorKindOf(openCamera({ isSecureContext: true, mediaDevices: undefined }))).toBe(
      "unsupported",
    );
  });

  it.each([
    ["NotAllowedError", "permission-denied"],
    ["SecurityError", "permission-denied"],
    ["NotFoundError", "no-camera"],
    ["OverconstrainedError", "no-camera"],
    ["NotReadableError", "camera-busy"],
    ["AbortError", "camera-busy"],
    ["SomethingElse", "unknown"],
  ])("maps %s to %s", async (name, kind) => {
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException("failed", name));
    expect(await errorKindOf(openCamera(environment(getUserMedia)))).toBe(kind);
  });

  it("classifies non-DOM errors as unknown", () => {
    expect(classifyCameraError("boom")).toBe("unknown");
  });
});

describe("stopStream", () => {
  it("stops every track", () => {
    const tracks = [{ stop: vi.fn() }, { stop: vi.fn() }];
    stopStream({ getTracks: () => tracks as unknown as MediaStreamTrack[] });
    for (const track of tracks) expect(track.stop).toHaveBeenCalledOnce();
  });

  it("accepts a missing stream", () => {
    expect(() => stopStream(null)).not.toThrow();
  });
});
