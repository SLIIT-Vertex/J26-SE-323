// Turns the live video into 640 x 480 frames for MediaPipe, like the DAiSEE frames used in training.
//
// Privacy: the canvas below exists only in memory. It is never added to the page, and its pixels
// are only passed to MediaPipe on this device. Nothing here encodes, stores or sends a frame.

import { FRAME_HEIGHT, FRAME_WIDTH } from "./frameFeatures";

export type CropRegion = { sx: number; sy: number; sw: number; sh: number };

/**
 * Centre crop of a source frame to the 4:3 training aspect ratio.
 * Eye openness depends on the aspect ratio, so frames are cropped, never stretched.
 */
export function centreCrop4x3(sourceWidth: number, sourceHeight: number): CropRegion {
  const target = FRAME_WIDTH / FRAME_HEIGHT;
  if (sourceWidth / sourceHeight > target) {
    const sw = sourceHeight * target;
    return { sx: (sourceWidth - sw) / 2, sy: 0, sw, sh: sourceHeight };
  }
  const sh = sourceWidth / target;
  return { sx: 0, sy: (sourceHeight - sh) / 2, sw: sourceWidth, sh };
}

export type FrameGrabber = {
  /** Current video frame as a 640 x 480 canvas, or null if the video has no frame yet. */
  grab: () => HTMLCanvasElement | null;
};

export function createFrameGrabber(video: HTMLVideoElement): FrameGrabber {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_WIDTH;
  canvas.height = FRAME_HEIGHT;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("2D canvas is not available");

  return {
    grab() {
      if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || video.videoWidth === 0) {
        return null;
      }
      const { sx, sy, sw, sh } = centreCrop4x3(video.videoWidth, video.videoHeight);
      // The raw (un-mirrored) camera image is used, as in the training videos.
      context.drawImage(video, sx, sy, sw, sh, 0, 0, FRAME_WIDTH, FRAME_HEIGHT);
      return canvas;
    },
  };
}
