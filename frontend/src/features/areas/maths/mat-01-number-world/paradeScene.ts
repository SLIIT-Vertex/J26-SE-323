/**
 * The Toy Parade stage: four wind-up toys wait backstage with number badges; the child drags (or
 * taps) them into the four parade slots. Every placed toy does a little hop, wherever it lands,
 * so the scene never tells the answer. React owns the line-up; the scene only draws and reports.
 */

import type PhaserNamespace from "phaser";
import {
	PARADE_ART,
	readyToyArt,
	TOY_ART_KEYS,
	type ToyArtKey,
} from "./toyArt";
import { spaced, TOYS, type ParadeLine } from "./toyRules";

export const WIDTH = 1920;
export const HEIGHT = 1080;

/** Where toys wait backstage and where the parade slots are (design px). */
export const HOME_X = [520, 860, 1200, 1540];
/** Toys stand on the painted stage edge; the slots lie on the red carpet below it. */
export const HOME_Y = 525;
export const SLOT_Y = 905;
export const TOY_SIZE = 230;

export type ParadeHandle = {
	setLine(line: ParadeLine, placed?: number): void;
	select(toy: number | null): void;
	march(): void;
	confused(): void;
	destroy(): void;
};

type Options = {
	values: readonly number[];
	reducedMotion: boolean;
	onDrop(toy: number, slot: number | null): void;
	onTapToy(toy: number): void;
	onTapSlot(slot: number): void;
};

type Scene = PhaserNamespace.Scene;
type Container = PhaserNamespace.GameObjects.Container;

const NUMBER_FONT = "Fredoka Variable, sans-serif";
const TOY_COLOURS = [0x4a90e2, 0x5cc35a, 0xe2483d, 0xb5793f];

export async function mountParade(
	host: HTMLElement,
	options: Options,
): Promise<ParadeHandle> {
	const { default: Phaser } = await import("phaser");
	return new Promise((resolve) => {
		const Parade = createParadeScene(Phaser, options, (scene) =>
			resolve({
				setLine: (line, placed) => scene.setLine(line, placed),
				select: (toy) => scene.select(toy),
				march: () => scene.march(),
				confused: () => scene.confused(),
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
			scene: Parade,
			banner: false,
		});
	});
}

function createParadeScene(
	Phaser: typeof PhaserNamespace,
	options: Options,
	onReady: (scene: ParadeScene) => void,
) {
	const count = Math.min(4, options.values.length);
	const xs = HOME_X.slice(0, count);

	class ParadeScene extends Phaser.Scene {
		private toys: Container[] = [];
		private line: ParadeLine = [];
		private nimo?: PhaserNamespace.GameObjects.Image | Container;

		constructor() {
			super("toy-parade");
		}

		preload() {
			for (const [key, url] of readyToyArt(PARADE_ART))
				this.load.image(key, url);
		}

		create() {
			this.line = Array.from({ length: count }, () => null);
			drawStage(this);
			drawSlots(this, xs);
			xs.forEach((x, slot) => {
				this.add
					.zone(x, SLOT_Y, 280, 230)
					.setInteractive({ useHandCursor: true })
					.on("pointerup", () => options.onTapSlot(slot));
			});
			this.nimo = this.drawNimo();
			this.toys = options.values
				.slice(0, count)
				.map((value, index) => this.drawToy(index, value));
			onReady(this);
		}

		private drawNimo() {
			const key: ToyArtKey = this.textures.exists("nimoDirector")
				? "nimoDirector"
				: "nimoIdle";
			if (this.textures.exists(key)) {
				const image = this.add.image(170, 1000, key).setOrigin(0.5, 1);
				image.setScale(330 / image.height);
				return image;
			}
			const shape = this.add.container(170, 900);
			shape.add([
				this.add.ellipse(0, 40, 120, 140, 0x3f8fe0),
				this.add.circle(0, -45, 58, 0x3f8fe0),
				this.add.ellipse(0, -28, 64, 40, 0xffffff),
				this.add.rectangle(0, 8, 110, 20, 0xf27a1a),
			]);
			return shape;
		}

		private drawToy(index: number, value: number) {
			const toy = this.add.container(xs[index] ?? 960, HOME_Y);
			const art = TOY_ART_KEYS[index];
			if (art && this.textures.exists(art)) {
				const image = this.add.image(0, 0, art);
				image.setScale(TOY_SIZE / Math.max(image.width, image.height));
				toy.add(image);
			} else {
				toy.add(
					drawToyShape(
						this,
						TOYS[index] ?? "robot",
						TOY_COLOURS[index] ?? 0x999999,
					),
				);
			}
			const badge = this.add.container(0, 118);
			badge.add([
				this.add.rectangle(0, 0, 190, 78, 0xfff6df).setStrokeStyle(6, 0x8a5a2b),
				this.add
					.text(0, 2, spaced(value), {
						fontFamily: NUMBER_FONT,
						fontSize: "52px",
						fontStyle: "bold",
						color: "#3a2a1a",
					})
					.setOrigin(0.5),
			]);
			toy.add(badge);
			toy
				.setSize(TOY_SIZE, TOY_SIZE)
				.setInteractive({ draggable: true, useHandCursor: true });
			let dragged = false;
			toy.on("dragstart", () => {
				dragged = false;
			});
			toy.on("drag", (_pointer: unknown, x: number, y: number) => {
				dragged = true;
				toy.setPosition(x, y).setDepth(10);
			});
			toy.on("dragend", () => {
				toy.setDepth(0);
				if (dragged) options.onDrop(index, this.slotNear(toy.x, toy.y));
			});
			// A tap without dragging picks the toy up (then a slot tap places it).
			toy.on("pointerup", () => {
				if (!dragged) options.onTapToy(index);
			});
			if (!options.reducedMotion) {
				// Wind-up toys never stand quite still.
				this.tweens.add({
					targets: toy,
					angle: { from: -2, to: 2 },
					duration: 700 + index * 90,
					yoyo: true,
					repeat: -1,
					ease: "Sine.easeInOut",
				});
			}
			return toy;
		}

		private slotNear(x: number, y: number): number | null {
			if (y < SLOT_Y - 170) return null;
			let best: number | null = null;
			let distance = Number.POSITIVE_INFINITY;
			xs.forEach((slotX, slot) => {
				const gap = Math.abs(slotX - x);
				if (gap < distance) {
					distance = gap;
					best = slot;
				}
			});
			return distance < 200 ? best : null;
		}

		private move(target: Container, x: number, y: number) {
			this.tweens.add({
				targets: target,
				x,
				y,
				duration: options.reducedMotion ? 0 : 300,
				ease: "Back.easeOut",
			});
		}

		setLine(line: ParadeLine, placed?: number) {
			this.line = [...line];
			this.toys.forEach((toy, index) => {
				const slot = this.line.indexOf(index);
				if (slot === -1) this.move(toy, xs[index] ?? 960, HOME_Y);
				else this.move(toy, xs[slot] ?? 960, SLOT_Y);
			});
			if (placed !== undefined && !options.reducedMotion) this.dance(placed);
		}

		/** A hop and a wiggle: the toy is happy to be in the parade, wherever it is. */
		private dance(index: number) {
			const toy = this.toys[index];
			if (!toy) return;
			this.tweens.add({
				targets: toy,
				scaleX: { from: 1, to: 1.12 },
				scaleY: { from: 1, to: 0.9 },
				duration: 120,
				yoyo: true,
				repeat: 1,
				delay: 300,
			});
		}

		select(toy: number | null) {
			this.toys.forEach((container, index) => {
				container.setAlpha(toy === null || toy === index ? 1 : 0.75);
				container.setScale(toy === index ? 1.08 : 1);
			});
		}

		march() {
			const order = this.line.filter((toy): toy is number => toy !== null);
			if (this.nimo && !options.reducedMotion) {
				if (
					this.nimo instanceof Phaser.GameObjects.Image &&
					this.textures.exists("nimoCheer")
				) {
					this.nimo.setTexture("nimoCheer");
					this.nimo.setScale(330 / this.nimo.height);
				}
				this.tweens.add({
					targets: this.nimo,
					y: "-=50",
					duration: 240,
					yoyo: true,
					repeat: 4,
				});
			}
			if (options.reducedMotion) return;
			order.forEach((toyIndex, position) => {
				const toy = this.toys[toyIndex];
				if (!toy) return;
				this.tweens.killTweensOf(toy);
				this.tweens.add({
					targets: toy,
					x: WIDTH + 300,
					duration: 2200,
					delay: 500 + position * 350,
					ease: "Sine.easeIn",
				});
				this.tweens.add({
					targets: toy,
					y: SLOT_Y - 40,
					duration: 180,
					delay: 500 + position * 350,
					yoyo: true,
					repeat: 6,
				});
			});
			for (let piece = 0; piece < 40; piece++) {
				const confetti = this.add.rectangle(
					Phaser.Math.Between(300, 1700),
					-20,
					16,
					26,
					[0xffd23f, 0xef5b5b, 0x4a90e2, 0x5cc35a, 0xb44ff0][piece % 5],
				);
				this.tweens.add({
					targets: confetti,
					y: HEIGHT + 40,
					angle: Phaser.Math.Between(180, 720),
					duration: Phaser.Math.Between(1400, 2400),
					delay: Phaser.Math.Between(0, 600),
					onComplete: () => confetti.destroy(),
				});
			}
		}

		/** A gentle head-shake: the toys are puzzled, nobody is in trouble. */
		confused() {
			if (options.reducedMotion) return;
			for (const toy of this.toys) {
				this.tweens.add({
					targets: toy,
					angle: { from: -8, to: 8 },
					duration: 110,
					yoyo: true,
					repeat: 3,
				});
			}
		}
	}
	return ParadeScene;
}

type ParadeScene = InstanceType<ReturnType<typeof createParadeScene>>;

function drawStage(scene: Scene) {
	if (scene.textures.exists("bgToyStage")) {
		scene.add
			.image(WIDTH / 2, HEIGHT / 2, "bgToyStage")
			.setDisplaySize(WIDTH, HEIGHT);
		return;
	}
	const stage = scene.add.graphics();
	stage
		.fillGradientStyle(0xffe7c2, 0xffe7c2, 0xf6c98f, 0xf6c98f, 1)
		.fillRect(0, 0, WIDTH, HEIGHT);
	stage.fillStyle(0xc9873f).fillRect(0, 580, WIDTH, 70);
	stage.fillStyle(0xa86a2c).fillRect(0, 650, WIDTH, 90);
	stage.fillStyle(0xd94b4b).fillRect(0, 740, WIDTH, 220);
	stage.fillStyle(0xb53a3a).fillRect(0, 955, WIDTH, 125);
	stage.fillStyle(0xc0392b);
	stage.fillTriangle(0, 0, 260, 0, 0, 900);
	stage.fillTriangle(WIDTH, 0, WIDTH - 260, 0, WIDTH, 900);
}

function drawSlots(scene: Scene, xs: readonly number[]) {
	const slots = scene.add.graphics();
	slots.lineStyle(6, 0xffffff, 0.85);
	for (const x of xs) {
		slots.strokeRoundedRect(x - 140, SLOT_Y - 120, 280, 230, 30);
	}
}

/** Placeholder toys made of shapes, used until the art is ready. */
function drawToyShape(scene: Scene, kind: string, colour: number) {
	const toy = scene.add.container(0, -30);
	if (kind === "robot") {
		toy.add([
			scene.add.rectangle(0, 20, 130, 120, colour).setStrokeStyle(6, 0x1d3f75),
			scene.add.rectangle(0, -70, 100, 70, colour).setStrokeStyle(6, 0x1d3f75),
			scene.add.circle(-22, -72, 12, 0xffd23f),
			scene.add.circle(22, -72, 12, 0xffd23f),
			scene.add.rectangle(0, -118, 8, 26, 0x1d3f75),
		]);
	} else if (kind === "dino") {
		toy.add([
			scene.add.ellipse(0, 20, 170, 120, colour).setStrokeStyle(6, 0x2c6b2b),
			scene.add.ellipse(55, -50, 90, 80, colour).setStrokeStyle(6, 0x2c6b2b),
			scene.add.triangle(-30, -40, 0, 30, 20, 0, 40, 30, 0xffd23f),
			scene.add.circle(70, -60, 9, 0x1d1d28),
		]);
	} else if (kind === "train") {
		toy.add([
			scene.add
				.rectangle(-10, 10, 180, 110, colour)
				.setStrokeStyle(6, 0x7a1f1a),
			scene.add.rectangle(45, -70, 70, 60, colour).setStrokeStyle(6, 0x7a1f1a),
			scene.add.circle(-50, 70, 24, 0x333333),
			scene.add.circle(40, 70, 24, 0x333333),
			scene.add.rectangle(-55, -60, 26, 50, 0xffd23f),
		]);
	} else {
		toy.add([
			scene.add.circle(0, 20, 72, colour).setStrokeStyle(6, 0x6e4520),
			scene.add.circle(0, -70, 52, colour).setStrokeStyle(6, 0x6e4520),
			scene.add.circle(-42, -110, 20, colour),
			scene.add.circle(42, -110, 20, colour),
			scene.add.circle(-16, -76, 7, 0x1d1d28),
			scene.add.circle(16, -76, 7, 0x1d1d28),
		]);
	}
	return toy;
}
