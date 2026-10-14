import { describe, expect, it } from "vitest";

import { GameEventBridge } from "../../bridge/GameEventBridge";
import { BuildManipulateSceneController } from "./sceneController";

describe("fraction-bar bridge", () => {
  it("emits a domain selection and drops it while support is mounted", () => {
    const bridge = new GameEventBridge();
    const seen: string[] = [];
    bridge.subscribe((event) => seen.push(event.optionId));
    const scene = new BuildManipulateSceneController(bridge);
    scene.apply({
      type: "LOAD_MANIFEST",
      manifest: { item_id: "preview", options: [{ option_id: "A" }] },
    });
    scene.select("A");
    scene.apply({ type: "PRESENT_SUPPORT" });
    scene.select("B");
    scene.apply({ type: "WITHDRAW_SUPPORT" });
    scene.select("B");
    scene.apply({ type: "DISPOSE" });
    scene.select("A");
    expect(seen).toEqual(["A", "B"]);
    expect(scene.supportVisible).toBe(false);
    expect(scene.disposed).toBe(true);
  });
});
