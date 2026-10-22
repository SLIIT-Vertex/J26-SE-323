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
				const bar = this.add
					.rectangle(180, y, 280, 36, 0x087443, 0.2)
					.setInteractive();
				const filled = Math.min(index + 1, parts);
				this.add.rectangle(
					40 + (280 * filled) / parts / 2,
					y,
					(280 * filled) / parts,
					36,
					0x087443,
				);
				this.add.text(16, y - 28, option.text, {
					color: "#173f35",
					fontSize: "16px",
				});
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
		transparent: true,
		scene: [FractionBarScene],
		banner: false,
		audio: { noAudio: true },
	});
}

export type SceneGameOptions = {
	/** Fonts that must be ready before the scene draws its first text, e.g. `"600 24px X"`. */
	fonts?: readonly string[];
	backgroundColor?: string;
	reducedMotion: boolean;
};

/**
 * The shared factory for full-surface scenes. The game fills its parent with
 * `Phaser.Scale.RESIZE`, so rotation and safe-area changes re-lay out instead of letterboxing.
 * The loop sleeps while the app is in the background. Fonts load first so Sinhala marks are
 * measured with the shaping font, not a fallback that clips above/below marks.
 */
export async function createSceneGame(
	parent: HTMLElement,
	scene: Phaser.Types.Scenes.SceneType,
	options: SceneGameOptions,
): Promise<Phaser.Game> {
	if (typeof document !== "undefined" && document.fonts) {
		await Promise.all(
			(options.fonts ?? []).map((font) =>
				document.fonts.load(font, "කෝ").catch(() => []),
			),
		);
	}
	const game = new Phaser.Game({
		type: Phaser.AUTO,
		parent,
		transparent: options.backgroundColor === undefined,
		backgroundColor: options.backgroundColor,
		scene: [scene],
		banner: false,
		audio: { noAudio: true },
		fps: { target: 30 },
		input: { activePointers: 2 },
		scale: {
			mode: Phaser.Scale.RESIZE,
			width: parent.clientWidth || 320,
			height: parent.clientHeight || 360,
		},
	});
	const onVisibility = () => {
		if (document.hidden) game.loop.sleep();
		else game.loop.wake();
	};
	document.addEventListener("visibilitychange", onVisibility);
	game.events.once(Phaser.Core.Events.DESTROY, () =>
		document.removeEventListener("visibilitychange", onVisibility),
	);
	return game;
}
