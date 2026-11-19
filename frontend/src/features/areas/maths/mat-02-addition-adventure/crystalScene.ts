/**
 * Nimo's crystal flight: Nimo's plane follows the child's finger through the sky; flying through
 * a crystal collects its energy. The energy gate waits on the right. It only draws and reports.
 */

import type PhaserNamespace from "phaser";
import { readyArt, type SkyArtKey } from "./skyArt";

export const FLIGHT_WIDTH = 1200;
export const FLIGHT_HEIGHT = 560;

const FLIGHT_ART: SkyArtKey[] = ["nimoPlane", "crystal", "energyGate"];
const PLANE_SPEED = 520;
const PLANE_WIDTH = 190;
const NUMBER_FONT = "Fredoka Variable, sans-serif";

export type CrystalFlightHandle = {
	collect(index: number): void;
	destroy(): void;
};

type Options = {
	values: readonly number[];
	collected: readonly number[];
	/** A worked example: everything is already collected and the plane does not move. */
	still: boolean;
	reducedMotion: boolean;
	onCollect(index: number): void;
};

/** Crystal positions spread across the sky between the plane and the gate. */
export function crystalSpots(count: number): Array<{ x: number; y: number }> {
	return Array.from({ length: count }, (_, at) => ({
		x: count === 1 ? 600 : 380 + (at * 440) / (count - 1),
		y: at % 2 === 0 ? 170 : 390,
	}));
}

export async function mountCrystalFlight(
	host: HTMLElement,
	options: Options,
): Promise<CrystalFlightHandle> {
	const { default: Phaser } = await import("phaser");
	return new Promise((resolve) => {
		const Flight = createFlightScene(Phaser, options, (scene) =>
			resolve({
				collect: (index) => scene.collect(index),
				destroy: () => scene.game.destroy(true),
			}),
		);
		new Phaser.Game({
			type: Phaser.AUTO,
			parent: host,
			width: FLIGHT_WIDTH,
			height: FLIGHT_HEIGHT,
			transparent: true,
			physics: { default: "arcade", arcade: { gravity: { x: 0, y: 0 } } },
			scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
			scene: Flight,
			banner: false,
		});
	});
}

function createFlightScene(
	Phaser: typeof PhaserNamespace,
	options: Options,
	onReady: (scene: FlightScene) => void,
) {
	class FlightScene extends Phaser.Scene {
		private plane?: PhaserNamespace.Types.Physics.Arcade.ImageWithDynamicBody;
		private target?: PhaserNamespace.Math.Vector2;
		private crystals: PhaserNamespace.GameObjects.Container[] = [];
		private taken = new Set<number>();

		constructor() {
			super("crystal-flight");
		}

		preload() {
			for (const [key, url] of readyArt(FLIGHT_ART)) this.load.image(key, url);
		}

		create() {
			this.taken = new Set(options.collected);
			this.crystals = [];
			this.drawGate();
			const spots = crystalSpots(options.values.length);
			options.values.forEach((value, index) => {
				const spot = spots[index] ?? { x: 600, y: 280 };
				this.crystals[index] = this.drawCrystal(spot.x, spot.y, value, index);
			});
			this.drawPlane();
			if (!options.still) {
				this.input.on("pointerdown", (pointer: PhaserNamespace.Input.Pointer) =>
					this.steer(pointer),
				);
				this.input.on(
					"pointermove",
					(pointer: PhaserNamespace.Input.Pointer) => {
						if (pointer.isDown) this.steer(pointer);
					},
				);
			}
			onReady(this);
		}

		private steer(pointer: PhaserNamespace.Input.Pointer) {
			this.target = new Phaser.Math.Vector2(pointer.worldX, pointer.worldY);
		}

		update() {
			const plane = this.plane;
			const target = this.target;
			if (!plane || !target) return;
			const distance = Phaser.Math.Distance.Between(
				plane.x,
				plane.y,
				target.x,
				target.y,
			);
			if (distance < 12) {
				plane.body.setVelocity(0);
				return;
			}
			this.physics.velocityFromRotation(
				Phaser.Math.Angle.Between(plane.x, plane.y, target.x, target.y),
				Math.min(PLANE_SPEED, distance * 6),
				plane.body.velocity,
			);
			plane.setFlipX(target.x < plane.x - 20);
		}

		private drawPlane() {
			const start = options.still ? { x: 1000, y: 300 } : { x: 130, y: 300 };
			if (this.textures.exists("nimoPlane")) {
				const plane = this.physics.add.image(start.x, start.y, "nimoPlane");
				plane.setScale(PLANE_WIDTH / plane.width);
				this.plane = plane;
			} else {
				const key = "plane-shape";
				if (!this.textures.exists(key)) {
					const g = this.add.graphics();
					g.fillStyle(0x3f8fe0).fillEllipse(90, 50, 170, 60);
					g.fillStyle(0xf27a1a).fillTriangle(60, 50, 120, 50, 90, 95);
					g.fillStyle(0xffffff).fillCircle(110, 35, 22);
					g.generateTexture(key, 180, 100);
					g.destroy();
				}
				this.plane = this.physics.add.image(start.x, start.y, key);
			}
			this.plane.setCollideWorldBounds(true);
			this.plane.body.setSize(
				this.plane.width * 0.6,
				this.plane.height * 0.5,
				true,
			);
			for (const [index, crystal] of this.crystals.entries()) {
				if (!crystal || this.taken.has(index)) continue;
				this.physics.add.overlap(this.plane, crystal, () =>
					this.collect(index, true),
				);
			}
		}

		private drawCrystal(x: number, y: number, value: number, index: number) {
			const crystal = this.add.container(x, y);
			if (this.textures.exists("crystal")) {
				const art = this.add.image(0, 0, "crystal");
				art.setScale(150 / art.height);
				crystal.add(art);
			} else {
				crystal.add(this.add.star(0, 0, 6, 34, 70, 0xb44ff0));
			}
			crystal.add(
				this.add
					.text(0, 4, `+${value}`, {
						fontFamily: NUMBER_FONT,
						fontSize: "52px",
						fontStyle: "bold",
						color: "#ffffff",
						stroke: "#5b1a8a",
						strokeThickness: 8,
					})
					.setOrigin(0.5),
			);
			crystal.setSize(120, 140);
			this.physics.add.existing(crystal, true);
			if (this.taken.has(index)) crystal.setAlpha(0.25);
			else if (!options.reducedMotion) {
				this.tweens.add({
					targets: crystal,
					y: y - 14,
					duration: 1100,
					yoyo: true,
					repeat: -1,
					ease: "Sine.easeInOut",
				});
			}
			return crystal;
		}

		private drawGate() {
			if (this.textures.exists("energyGate")) {
				const gate = this.add.image(1080, 300, "energyGate");
				gate.setScale(380 / gate.height);
			} else {
				const gate = this.add.graphics();
				gate.fillStyle(0x9aa3ad).fillRoundedRect(990, 140, 180, 300, {
					tl: 90,
					tr: 90,
					bl: 0,
					br: 0,
				});
				gate.fillStyle(0xffd23f, 0.85).fillRoundedRect(1020, 180, 120, 260, {
					tl: 60,
					tr: 60,
					bl: 0,
					br: 0,
				});
			}
		}

		collect(index: number, fromScene = false) {
			if (this.taken.has(index)) return;
			this.taken.add(index);
			const crystal = this.crystals[index];
			if (crystal) {
				this.tweens.killTweensOf(crystal);
				this.tweens.add({
					targets: crystal,
					scale: 1.5,
					alpha: 0.25,
					duration: options.reducedMotion ? 0 : 350,
					ease: "Back.easeOut",
				});
			}
			if (fromScene) options.onCollect(index);
		}
	}
	return FlightScene;
}

type FlightScene = InstanceType<ReturnType<typeof createFlightScene>>;
