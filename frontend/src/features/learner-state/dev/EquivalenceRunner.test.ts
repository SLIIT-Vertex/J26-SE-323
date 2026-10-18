import { describe, expect, it } from "vitest";

import { groupFrames } from "./EquivalenceRunner";

function frame(path: string): File {
  const file = new File([], path.split("/").at(-1) ?? path);
  Object.defineProperty(file, "webkitRelativePath", { value: path });
  return file;
}

describe("groupFrames", () => {
  it("groups the picked frames by clip folder in name order", () => {
    const clips = groupFrames([
      frame("frames/clip02/frame_01.png"),
      frame("frames/clip01/frame_10.png"),
      frame("frames/clip01/frame_02.png"),
      frame("frames/clip02/frame_00.png"),
    ]);

    expect([...clips.keys()]).toEqual(["clip01", "clip02"]);
    expect(clips.get("clip01")?.map((f) => f.name)).toEqual(["frame_02.png", "frame_10.png"]);
    expect(clips.get("clip02")?.map((f) => f.name)).toEqual(["frame_00.png", "frame_01.png"]);
  });

  it("ignores files that are not extracted frames", () => {
    const clips = groupFrames([
      frame("frames/manifest.json"),
      frame("frames/clip01/notes.txt"),
      frame("frames/other/frame_00.png"),
      frame("frames/clip01/frame_00.png"),
    ]);

    expect([...clips.keys()]).toEqual(["clip01"]);
    expect(clips.get("clip01")).toHaveLength(1);
  });
});
