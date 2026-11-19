/**
 * The Bubble Rush course: Nimo's bubble submarine waits on the left; a junction of numbered bubble
 * rings floats on the right. The child taps a ring (or drags the submarine to its lane) and the
 * submarine speeds through it. Every ring is passed the same way, right or wrong, so the course
 * never tells the answer. React owns the choices; the scene only draws and reports.
 */

import type PhaserNamespace from "phaser";
import { type BubbleArtKey, RUSH_ART, readyBubbleArt } from "./bubbleArt";

export const WIDTH = 1920;
export const HEIGHT = 1080;

export const SUB_X = 330;
export const RING_X = 1300;
export const RING_SIZE = 140;
const LANE_TOP = 340;
const LANE_BOTTOM = 960;
const SUB_LENGTH = 330;
const SUB_Y = 620;

/** The centre heights of `count` lanes, top to bottom (design px). */
export function laneYs(count: number): number[] {
	if (count <= 1) return [(LANE_TOP + LANE_BOTTOM) / 2];
	const gap = Math.min(180, (LANE_BOTTOM - LANE_TOP) / (count - 1));
	const top = (LANE_TOP + LANE_BOTTOM) / 2 - (gap * (count - 1)) / 2;
	return Array.from({ length: count }, (_, lane) => top + lane * gap);
}

export type RingKind = "rule" | "number" | "finish";

export type RushHandle = {
	/** Show a junction (or the finish arch) without driving. */
	showJunction(labels: readonly string[], kind: RingKind): void;
	/** Drive through `lane`, then show the next junction. */
	drive(lane: number, next: readonly string[], kind: RingKind): void;
	celebrate(): void;
	puzzled(): void;
	destroy(): void;
};

type Options = {
	reducedMotion: boolean;
	onTapRing(lane: number): void;
	/** The submarine finished passing a ring. */
	onPassed(): void;
};

type Scene = PhaserNamespace.Scene;
type Container = PhaserNamespace.GameObjects.Container;

const NUMBER_FONT = "Fredoka Variable, sans-serif";
const RULE_COLOURS = [0xffc93c, 0x7fd8ff, 0xff9ad5, 0xb79cff, 0x8fe388];

export async function mountBubbleRush(
	host: HTMLElement,
	options: Options,
): Promise<RushHandle> {
	const { default: Phaser } = await import("phaser");
	return new Promise((resolve) => {
		const Rush = createRushScene(Phaser, options, (scene) =>
			resolve({
				showJunction: (labels, kind) => scene.showJunction(labels, kind),
				drive: (lane, next, kind) => scene.drive(lane, next, kind),
				celebrate: () => scene.celebrate(),
				puzzled: () => scene.puzzled(),
				destroy: () => scene.game.destroy(true),
			}),
		);
		new Phaser.Game({
			type: Phaser.AUTO,
			parent: host,
			width: WIDTH,
			height: HEIGHT,
			transparent: true,
			scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
			scene: Rush,
			banner: false,
		});
	});
}

function createRushScene(
	Phaser: typeof PhaserNamespace,
	options: Options,
	onReady: (scene: RushScene) => void,
) {
	const quick = (ms: number) => (options.reducedMotion ? 0 : ms);

	class RushScene extends Phaser.Scene {
		private sub!: Container;
		private octopus!: Container;
		private rings: Container[] = [];
		private kind: RingKind = "rule";
		private moving = false;
		private trail?: PhaserNamespace.GameObjects.Particles.ParticleEmitter;
		private drift: PhaserNamespace.GameObjects.Arc[] = [];

		constructor() {
			super("bubble-rush");
		}

		preload() {
			for (const [key, url] of readyBubbleArt(RUSH_ART))
				this.load.image(key, url);
		}

		create() {
			drawReef(this);
			makeBubbleTexture(this);
			this.drift = drawDriftingBubbles(this, options.reducedMotion);
			this.octopus = drawOctopus(this);
			this.sub = this.drawSub();
			this.trail = this.add.particles(0, 0, "rush-bubble", {
				speedX: { min: -260, max: -90 },
				speedY: { min: -60, max: 60 },
				scale: { start: 0.9, end: 0.2 },
				alpha: { start: 0.9, end: 0 },
				lifespan: 700,
				frequency: 30,
				emitting: false,
			});
			this.trail.startFollow(this.sub, -SUB_LENGTH / 2, 10);
			this.trail.setDepth(4);
			if (!options.reducedMotion) {
				this.tweens.add({
					targets: this.sub,
					y: "+=14",
					duration: 900,
					yoyo: true,
					repeat: -1,
					ease: "Sine.easeInOut",
				});
				this.tweens.add({
					targets: this.octopus,
					y: "-=24",
					angle: { from: -3, to: 3 },
					duration: 1300,
					yoyo: true,
					repeat: -1,
					ease: "Sine.easeInOut",
				});
			}
			onReady(this);
		}

		update(_time: number, delta: number) {
			// Bubbles drift up all the time, and stream past faster while the submarine speeds.
			const speed = this.moving ? 1.1 : 0.12;
			for (const bubble of this.drift) {
				bubble.x -= speed * delta;
				bubble.y -= 0.05 * delta;
				if (bubble.x < -30) bubble.x = WIDTH + 30;
				if (bubble.y < -30) bubble.y = HEIGHT + 30;
			}
		}

		private drawSub() {
			const sub = this.add.container(SUB_X, SUB_Y);
			if (this.textures.exists("nimoSub")) {
				const image = this.add.image(0, 0, "nimoSub");
				image.setScale(SUB_LENGTH / image.width);
				sub.add(image);
			} else {
				sub.add([
					this.add
						.ellipse(-150, 20, 50, 90, 0xf2a31b)
						.setStrokeStyle(5, 0x8a5a12),
					this.add
						.ellipse(0, 30, 280, 150, 0xffc93c)
						.setStrokeStyle(7, 0x8a5a12),
					this.add
						.circle(20, -40, 72, 0xbfefff, 0.85)
						.setStrokeStyle(6, 0x5fb6d9),
					this.add.circle(20, -40, 40, 0x3f8fe0),
					this.add.ellipse(20, -26, 36, 22, 0xffffff),
					this.add.rectangle(20, 2, 70, 14, 0xf27a1a),
					this.add.circle(100, 40, 22, 0xffffff).setStrokeStyle(5, 0x8a5a12),
					this.add.circle(-60, 45, 26, 0x3f8fe0).setStrokeStyle(5, 0x8a5a12),
				]);
			}
			sub.setDepth(5);
			sub
				.setSize(SUB_LENGTH, 220)
				.setInteractive({ draggable: true, useHandCursor: true });
			let startY = sub.y;
			sub.on("dragstart", () => {
				startY = sub.y;
			});
			sub.on("drag", (_pointer: unknown, _x: number, y: number) => {
				if (this.moving) return;
				sub.y = Phaser.Math.Clamp(y, LANE_TOP - 60, LANE_BOTTOM + 40);
			});
			sub.on("dragend", () => {
				if (this.moving) return;
				if (Math.abs(sub.y - startY) < 30 || this.kind === "finish") {
					this.tweens.add({ targets: sub, y: startY, duration: quick(200) });
					return;
				}
				const ys = laneYs(this.rings.length);
				let best = 0;
				ys.forEach((laneY, lane) => {
					if (Math.abs(laneY - sub.y) < Math.abs((ys[best] ?? 0) - sub.y))
						best = lane;
				});
				options.onTapRing(best);
			});
			return sub;
		}

		showJunction(labels: readonly string[], kind: RingKind) {
			for (const ring of this.rings) {
				this.tweens.killTweensOf(ring);
				ring.destroy();
			}
			this.kind = kind;
			const ys = kind === "finish" ? laneYs(1) : laneYs(labels.length);
			const shown = kind === "finish" ? [""] : labels;
			this.rings = shown.map((label, lane) =>
				this.drawRing(RING_X, ys[lane] ?? 600, label, kind, lane),
			);
			this.rings.forEach((ring, lane) => {
				ring.setScale(0.2).setAlpha(0);
				this.tweens.add({
					targets: ring,
					scale: 1,
					alpha: 1,
					duration: quick(380),
					delay: quick(lane * 70),
					ease: "Back.easeOut",
				});
			});
			this.tweens.add({
				targets: this.octopus,
				alpha: kind === "rule" ? 1 : 0.85,
				duration: quick(300),
			});
		}

		private drawRing(
			x: number,
			y: number,
			label: string,
			kind: RingKind,
			lane: number,
		) {
			const ring = this.add.container(x, y);
			if (kind === "finish") {
				const arch = this.add.graphics();
				for (let row = 0; row < 12; row++) {
					arch.fillStyle(row % 2 ? 0xffffff : 0x2a1f5c);
					arch.fillRect(-20, -330 + row * 55, 40, 55);
				}
				ring.add([
					arch,
					this.add.circle(0, -350, 34, 0xffc93c).setStrokeStyle(5, 0x8a5a12),
				]);
				ring.setDepth(3);
				return ring;
			}
			const colour = RULE_COLOURS[lane % RULE_COLOURS.length] ?? 0xffffff;
			const size = RING_SIZE;
			ring.add([
				this.add
					.circle(0, 0, size / 2, kind === "rule" ? colour : 0x9fe3ff, 0.28)
					.setStrokeStyle(10, kind === "rule" ? colour : 0xffffff, 0.95),
				this.add.ellipse(
					-size * 0.2,
					-size * 0.24,
					size * 0.26,
					size * 0.14,
					0xffffff,
					0.75,
				),
				this.add
					.text(0, 4, label, {
						fontFamily: NUMBER_FONT,
						fontSize: label.length > 3 ? "50px" : "60px",
						fontStyle: "bold",
						color: "#2a1f5c",
						stroke: "#ffffff",
						strokeThickness: 6,
					})
					.setOrigin(0.5),
			]);
			ring.setDepth(3);
			ring
				.setSize(size + 40, size + 20)
				.setInteractive({ useHandCursor: true })
				.on("pointerup", () => {
					if (!this.moving) options.onTapRing(lane);
				});
			if (!options.reducedMotion) {
				this.tweens.add({
					targets: ring,
					y: y + 10,
					duration: 1100 + lane * 130,
					yoyo: true,
					repeat: -1,
					ease: "Sine.easeInOut",
				});
			}
			return ring;
		}

		drive(lane: number, next: readonly string[], kind: RingKind) {
			if (this.moving) return;
			const target = this.rings[lane];
			if (!target) return;
			this.moving = true;
			this.tweens.killTweensOf(this.sub);
			this.sub.setAngle(0);
			const laneY = target.y;
			const passed = () => {
				// The ring bursts into bubbles behind the submarine, whichever ring it was.
				this.tweens.add({
					targets: target,
					scale: 1.6,
					alpha: 0,
					duration: quick(260),
				});
				this.trail?.explode(18, target.x, target.y);
			};
			this.trail?.start();
			this.tweens.chain({
				targets: this.sub,
				tweens: [
					{ y: laneY, duration: quick(260), ease: "Sine.easeInOut" },
					{
						x: RING_X + 80,
						duration: quick(520),
						ease: "Cubic.easeIn",
						onComplete: passed,
					},
					{ x: WIDTH + SUB_LENGTH, duration: quick(360), ease: "Linear" },
				],
				onComplete: () => {
					for (const ring of this.rings) if (ring !== target) ring.setAlpha(0);
					// Each new stretch starts at mid-height, clear of the buttons below.
					this.sub.setPosition(-SUB_LENGTH, SUB_Y);
					this.showJunction(next, kind);
					this.tweens.add({
						targets: this.sub,
						x: SUB_X,
						duration: quick(650),
						ease: "Cubic.easeOut",
						onComplete: () => {
							this.trail?.stop();
							this.moving = false;
							if (!options.reducedMotion) {
								this.tweens.add({
									targets: this.sub,
									y: "+=14",
									duration: 900,
									yoyo: true,
									repeat: -1,
									ease: "Sine.easeInOut",
								});
							}
							options.onPassed();
						},
					});
				},
			});
		}

		/** The submarine bursts through the finish arch in a storm of bubbles. */
		celebrate() {
			this.moving = true;
			this.trail?.start();
			this.tweens.killTweensOf(this.sub);
			this.tweens.add({
				targets: this.sub,
				x: WIDTH + SUB_LENGTH,
				y: 600,
				duration: quick(1200),
				ease: "Cubic.easeIn",
			});
			for (let burst = 0; burst < 6; burst++) {
				this.time.delayedCall(quick(200 + burst * 180), () =>
					this.trail?.explode(
						30,
						Phaser.Math.Between(500, 1700),
						Phaser.Math.Between(300, 900),
					),
				);
			}
			this.tweens.add({
				targets: this.octopus,
				alpha: 1,
				angle: 360,
				duration: quick(1200),
			});
		}

		/** A gentle wobble: the bubbles got muddled, nobody is in trouble. */
		puzzled() {
			if (options.reducedMotion) return;
			this.tweens.killTweensOf(this.sub);
			this.tweens.add({
				targets: this.sub,
				angle: { from: -9, to: 9 },
				duration: 120,
				yoyo: true,
				repeat: 4,
				onComplete: () => this.sub.setAngle(0),
			});
		}
	}
	return RushScene;
}

type RushScene = InstanceType<ReturnType<typeof createRushScene>>;

function drawReef(scene: Scene) {
	if (scene.textures.exists("bgReefRace")) {
		scene.add
			.image(WIDTH / 2, HEIGHT / 2, "bgReefRace")
			.setDisplaySize(WIDTH, HEIGHT);
		return;
	}
	const sea = scene.add.graphics();
	sea
		.fillGradientStyle(0x3fc6f0, 0x3fc6f0, 0x1567b8, 0x1567b8, 1)
		.fillRect(0, 0, WIDTH, HEIGHT);
	sea.fillStyle(0xffffff, 0.08);
	for (let ray = 0; ray < 5; ray++) {
		sea.fillTriangle(
			300 + ray * 340,
			0,
			420 + ray * 340,
			0,
			160 + ray * 380,
			HEIGHT,
		);
	}
	sea.fillStyle(0xf3d9a4).fillEllipse(WIDTH / 2, HEIGHT + 40, WIDTH * 1.3, 220);
	sea.fillStyle(0xff7aa8);
	for (const x of [90, 610, 1010, 1820]) {
		sea.fillRoundedRect(x, HEIGHT - 170, 34, 120, 14);
		sea.fillRoundedRect(x + 40, HEIGHT - 130, 30, 90, 14);
	}
	sea.fillStyle(0x3fbf7f);
	for (const x of [240, 820, 1500]) {
		sea.fillEllipse(x, HEIGHT - 110, 40, 200);
		sea.fillEllipse(x + 36, HEIGHT - 90, 34, 150);
	}
}

/** A soft white bubble used by every particle effect. */
function makeBubbleTexture(scene: Scene) {
	if (scene.textures.exists("rush-bubble")) return;
	const dot = scene.make.graphics({ x: 0, y: 0 }, false);
	dot.fillStyle(0xffffff, 0.35).fillCircle(16, 16, 14);
	dot.lineStyle(3, 0xffffff, 0.95).strokeCircle(16, 16, 14);
	dot.fillStyle(0xffffff, 0.95).fillCircle(11, 10, 4);
	dot.generateTexture("rush-bubble", 32, 32);
	dot.destroy();
}

function drawDriftingBubbles(scene: Scene, still: boolean) {
	return Array.from({ length: still ? 0 : 26 }, () =>
		scene.add
			.circle(
				Math.random() * WIDTH,
				Math.random() * HEIGHT,
				4 + Math.random() * 12,
				0xffffff,
				0.18,
			)
			.setStrokeStyle(2, 0xffffff, 0.5)
			.setDepth(1),
	);
}

function drawOctopus(scene: Scene): Container {
	const octopus = scene.add.container(1700, 640);
	const key: BubbleArtKey = "octopus";
	if (scene.textures.exists(key)) {
		const image = scene.add.image(0, 0, key);
		image.setScale(320 / Math.max(image.width, image.height));
		octopus.add(image);
	} else {
		const legs = scene.add.graphics();
		legs.lineStyle(26, 0xa77bea);
		for (let leg = 0; leg < 6; leg++) {
			const x = -100 + leg * 40;
			legs.beginPath();
			legs.moveTo(x, 40);
			legs.lineTo(x + (leg % 2 ? 22 : -22), 140);
			legs.strokePath();
		}
		octopus.add([
			legs,
			scene.add.ellipse(0, -10, 230, 200, 0xb98cf5).setStrokeStyle(6, 0x6b43b5),
			scene.add.circle(-40, -20, 20, 0xffffff),
			scene.add.circle(40, -20, 20, 0xffffff),
			scene.add.circle(-36, -16, 9, 0x1d1d28),
			scene.add.circle(44, -16, 9, 0x1d1d28),
		]);
	}
	octopus.setDepth(2);
	return octopus;
}
