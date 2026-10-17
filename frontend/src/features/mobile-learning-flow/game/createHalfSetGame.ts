import type { HalfSetManifest } from "../bridge/contracts";
import type { HalfSetSceneController } from "./HalfSetSceneController";

export interface GameHandle {
	destroy(): void;
	resize(): void;
	clearForWithdrawal(): void;
}

const mounted = new WeakMap<HTMLElement, GameHandle | null>();

export function reserveGameHost(host: HTMLElement): void {
	if (mounted.has(host)) throw new Error("PHASER_INSTANCE_ALREADY_MOUNTED");
	mounted.set(host, null);
}

export function releaseGameHost(host: HTMLElement): void {
	mounted.delete(host);
}

export async function createHalfSetGame(
	host: HTMLElement,
	controller: HalfSetSceneController,
	manifest: HalfSetManifest,
	reducedMotion: boolean,
): Promise<GameHandle> {
	reserveGameHost(host);
	let module: typeof import("phaser");
	try {
		module = await import("phaser");
	} catch (error) {
		releaseGameHost(host);
		throw error;
	}
	const PhaserRuntime = (
		module as unknown as { default?: typeof import("phaser") }
	).default ?? module;

	class HalfSetScene extends PhaserRuntime.Scene {
		private objects: import("phaser").GameObjects.Arc[] = [];

		create() {
			const width = this.scale.width;
			const height = this.scale.height;
			this.add
				.rectangle(
					width * 0.25,
					height * 0.72,
					width * 0.42,
					height * 0.38,
					0xded2ff,
					0.75,
				)
				.setStrokeStyle(3, 0x6941c6);
			this.add
				.rectangle(
					width * 0.75,
					height * 0.72,
					width * 0.42,
					height * 0.38,
					0xc9f3e8,
					0.75,
				)
				.setStrokeStyle(3, 0x168b7a);
			const columns = Math.max(
				4,
				Math.ceil(Math.sqrt(manifest.totalObjects * 2)),
			);
			for (let index = 0; index < manifest.totalObjects; index += 1) {
				const id = `object-${index + 1}`;
				const x =
					34 + (index % columns) * ((width - 68) / Math.max(1, columns - 1));
				const y = 42 + Math.floor(index / columns) * 44;
				const circle = this.add
					.circle(x, y, 15, index % 2 ? 0xffa94d : 0x62b6ff)
					.setStrokeStyle(2, 0x39255f)
					.setInteractive({ useHandCursor: true });
				circle.setData("id", id);
				circle.on("pointerdown", () => {
					const group = circle.x < width / 2 ? 1 : 0;
					controller.place(id, group as 0 | 1);
					const destinationX = group === 0 ? width * 0.25 : width * 0.75;
					const destinationY = height * 0.62 + (index % 3) * 32;
					if (reducedMotion) circle.setPosition(destinationX, destinationY);
					else
						this.tweens.add({
							targets: circle,
							x: destinationX,
							y: destinationY,
							duration: 180,
						});
				});
				this.objects.push(circle);
			}
		}
	}

	let game: import("phaser").Game;
	try {
		game = new PhaserRuntime.Game({
			type: PhaserRuntime.AUTO,
			parent: host,
			width: Math.max(280, host.clientWidth),
			height: Math.max(320, host.clientHeight),
			backgroundColor: "#fff9ec",
			scene: [HalfSetScene],
			banner: false,
			audio: { noAudio: true },
			render: { antialias: true, failIfMajorPerformanceCaveat: false },
			scale: {
				mode: PhaserRuntime.Scale.RESIZE,
				autoCenter: PhaserRuntime.Scale.CENTER_BOTH,
			},
		});
	} catch (error) {
		releaseGameHost(host);
		throw error;
	}
	const handle: GameHandle = {
		resize: () =>
			game.scale.resize(
				Math.max(280, host.clientWidth),
				Math.max(320, host.clientHeight),
			),
		destroy: () => {
			game.destroy(true);
			releaseGameHost(host);
		},
		clearForWithdrawal: () => {
			for (const scene of game.scene.getScenes(true)) {
				scene.tweens.killAll();
				scene.input.removeAllListeners();
				for (const child of [...scene.children.list]) {
					const interactive = child as import("phaser").GameObjects.GameObject & {
						disableInteractive?: () => unknown;
						removeAllListeners?: () => unknown;
					};
					interactive.disableInteractive?.();
					interactive.removeAllListeners?.();
					child.destroy();
				}
			}
		},
	};
	mounted.set(host, handle);
	return handle;
}

export function hasMountedGame(host: HTMLElement): boolean {
	return mounted.has(host);
}
