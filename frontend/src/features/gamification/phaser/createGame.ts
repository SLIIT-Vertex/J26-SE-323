import Phaser from "phaser";

import type { ManifestView } from "../api/generated";
import type { BuildManipulateSceneController } from "./templates/build-manipulate/sceneController";

/**
 * Phaser 3.88.2 is pinned in package.json because this fraction-bar scene is the only
 * canvas template in the pilot shell. choice_quest stays in React DOM. JSON cannot
 * carry the reason next to the dependency, so it lives here and in the vertical-slice note.
 */
export function createFractionBarGame(
  parent: HTMLElement,
  controller: BuildManipulateSceneController,
  manifest: ManifestView,
  reducedMotion: boolean,
): Phaser.Game {
  const duration = reducedMotion ? 0 : 160;
  class FractionBarScene extends Phaser.Scene {
    constructor() {
      super("fraction-bar");
    }

    create(): void {
      const parts = Math.max(manifest.options.length, 1);
      manifest.options.forEach((option, index) => {
        const y = 48 + index * 56;
        const bar = this.add.rectangle(180, y, 280, 36, 0x087443, 0.2).setInteractive();
        const filled = Math.min(index + 1, parts);
        this.add.rectangle(40 + (280 * filled) / parts / 2, y, (280 * filled) / parts, 36, 0x087443);
        this.add.text(16, y - 28, option.text, { color: "#173f35", fontSize: "16px" });
        bar.on("pointerdown", () => {
          this.tweens.add({ targets: bar, scaleX: 1.02, duration, yoyo: true });
          controller.select(option.option_id);
        });
      });
    }
  }

  return new Phaser.Game({
    type: Phaser.AUTO,
    parent,
    width: 360,
    height: Math.max(180, manifest.options.length * 56 + 24),
    backgroundColor: "#f3f7f1",
    scene: [FractionBarScene],
    banner: false,
    audio: { noAudio: true },
  });
}
