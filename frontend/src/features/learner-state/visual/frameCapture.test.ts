import { describe, expect, it } from "vitest";

import { centreCrop4x3 } from "./frameCapture";

describe("centreCrop4x3", () => {
  it("keeps a 640x480 frame unchanged", () => {
    expect(centreCrop4x3(640, 480)).toEqual({ sx: 0, sy: 0, sw: 640, sh: 480 });
  });

  it("crops the sides of a 16:9 frame", () => {
    expect(centreCrop4x3(1280, 720)).toEqual({ sx: 160, sy: 0, sw: 960, sh: 720 });
  });

  it("crops the top and bottom of a portrait frame", () => {
    expect(centreCrop4x3(480, 640)).toEqual({ sx: 0, sy: 140, sw: 480, sh: 360 });
  });

  it("always produces the 4:3 training aspect ratio", () => {
    for (const [w, h] of [
      [1920, 1080],
      [720, 1280],
      [1000, 1000],
      [800, 600],
    ]) {
      const { sw, sh } = centreCrop4x3(w, h);
      expect(sw / sh).toBeCloseTo(4 / 3, 12);
    }
  });
});
