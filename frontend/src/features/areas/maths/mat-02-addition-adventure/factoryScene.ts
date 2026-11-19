/**
 * The Number Factory machine: one bin per place, filled with place-value blocks, and a conveyor
 * that carries each bundle of ten to the next place. It only draws; React owns the state.
 */

import type PhaserNamespace from "phaser";

export const FACTORY_WIDTH = 1200;
export const FACTORY_HEIGHT = 470;

const BIN_TOP = 10;
const BIN_HEIGHT = 380;
const CONVEYOR_Y = 432;

type Kind = { width: number; height: number; colour: number; edge: number };

/** Block shape by power of ten: cube, rod, flat, big cube, bigger cube. */
const KINDS: Kind[] = [
	{ width: 36, height: 36, colour: 0x3d8bfd, edge: 0x1d4f9e },
	{ width: 24, height: 120, colour: 0xffc83d, edge: 0xb07d00 },
	{ width: 72, height: 72, colour: 0x9b5de5, edge: 0x5b2a9a },
	{ width: 84, height: 84, colour: 0x2ec27e, edge: 0x16784a },
	{ width: 92, height: 92, colour: 0xef5b5b, edge: 0x9e2a2a },
];
const BIN_TINT = [0xdcebff, 0xfff3c9, 0xece0fb, 0xd8f5e6, 0xfde0e0];
const GAP = 6;

export type FactoryEvent =
	| { type: "set" }
	| { type: "feed" }
	| { type: "bundle"; from: number };

export type FactoryHandle = {
	show(counts: readonly number[], event: FactoryEvent): void;
	refuse(power: number): void;
	destroy(): void;
};

export async function mountFactory(
	host: HTMLElement,
	places: number,
	reducedMotion: boolean,
): Promise<FactoryHandle> {
	const { default: Phaser } = await import("phaser");
	return new Promise((resolve) => {
		const Factory = createFactoryScene(Phaser, places, reducedMotion, (scene) =>
			resolve({
				show: (counts, event) => scene.show(counts, event),
				refuse: (power) => scene.refuse(power),
				destroy: () => scene.game.destroy(true),
			}),
		);
		new Phaser.Game({
			type: Phaser.AUTO,
			parent: host,
			width: FACTORY_WIDTH,
			height: FACTORY_HEIGHT,
			transparent: true,
			scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
			scene: Factory,
			banner: false,
		});
	});
}

/** Where the blocks of one bin sit, filled from the bottom, shrunk if they would overflow. */
export function binLayout(count: number, power: number, binWidth: number) {
	const kind = KINDS[power] ?? KINDS[0];
	let scale = 1;
	let perRow = 1;
	let rows = 1;
	for (let attempt = 0; attempt < 12; attempt++) {
		const cellWidth = (kind.width + GAP) * scale;
		const cellHeight = (kind.height + GAP) * scale;
		perRow = Math.max(1, Math.floor((binWidth - 16) / cellWidth));
		rows = Math.max(1, Math.ceil(count / perRow));
		if (rows * cellHeight <= BIN_HEIGHT - 16) break;
		scale *= 0.88;
	}
	const cellWidth = (kind.width + GAP) * scale;
	const cellHeight = (kind.height + GAP) * scale;
	const usedWidth = Math.min(count, perRow) * cellWidth;
	return {
		scale,
		positions: Array.from({ length: count }, (_, at) => ({
			x: (binWidth - usedWidth) / 2 + (at % perRow) * cellWidth + cellWidth / 2,
			y:
				BIN_TOP +
				BIN_HEIGHT -
				8 -
				Math.floor(at / perRow) * cellHeight -
				cellHeight / 2,
		})),
	};
}

function createFactoryScene(
	Phaser: typeof PhaserNamespace,
	places: number,
	reducedMotion: boolean,
	onReady: (scene: FactoryScene) => void,
) {
	const binWidth = FACTORY_WIDTH / places;
	/** Left edge of the bin for a power of ten; the largest place is on the left. */
	const binLeft = (power: number) => (places - 1 - power) * binWidth;

	class FactoryScene extends Phaser.Scene {
		private blocks: PhaserNamespace.GameObjects.Image[][] = [];
		private counts: number[] = [];
		private bins: PhaserNamespace.GameObjects.Container[] = [];

		constructor() {
			super("number-factory");
		}

		create() {
			this.makeTextures();
			this.blocks = Array.from({ length: places }, () => []);
			this.counts = Array.from({ length: places }, () => 0);
			this.bins = [];
			for (let power = 0; power < places; power++) {
				const bin = this.add.container(binLeft(power), 0);
				const frame = this.add.graphics();
				frame.fillStyle(BIN_TINT[power] ?? 0xffffff, 0.92);
				frame.fillRoundedRect(8, BIN_TOP, binWidth - 16, BIN_HEIGHT, 18);
				frame
					.lineStyle(6, 0x50607a)
					.strokeRoundedRect(8, BIN_TOP, binWidth - 16, BIN_HEIGHT, 18);
				bin.add(frame);
				this.bins.push(bin);
			}
			const belt = this.add.graphics();
			belt
				.fillStyle(0x3a4256)
				.fillRoundedRect(0, CONVEYOR_Y - 22, FACTORY_WIDTH, 44, 22);
			belt.fillStyle(0xffd23f);
			for (let x = 12; x < FACTORY_WIDTH; x += 48)
				belt.fillRect(x, CONVEYOR_Y - 22, 24, 6);
			belt.fillStyle(0x8a94a8);
			for (let x = 30; x < FACTORY_WIDTH; x += 60)
				belt.fillCircle(x, CONVEYOR_Y + 4, 12);
			onReady(this);
		}

		private makeTextures() {
			KINDS.forEach((kind, power) => {
				const key = `block-${power}`;
				if (this.textures.exists(key)) return;
				const g = this.add.graphics();
				g.fillStyle(kind.colour).fillRoundedRect(
					0,
					0,
					kind.width,
					kind.height,
					6,
				);
				g.lineStyle(3, kind.edge).strokeRoundedRect(
					1.5,
					1.5,
					kind.width - 3,
					kind.height - 3,
					6,
				);
				g.lineStyle(1.5, kind.edge, 0.55);
				if (power === 1) {
					for (let y = 12; y < kind.height; y += 12)
						g.lineBetween(3, y, kind.width - 3, y);
				} else if (power === 2) {
					for (let at = 7.2; at < kind.width - 1; at += 7.2) {
						g.lineBetween(at, 3, at, kind.height - 3);
						g.lineBetween(3, at, kind.width - 3, at);
					}
				} else if (power >= 3) {
					g.lineBetween(kind.width / 2, 3, kind.width / 2, kind.height - 3);
					g.lineBetween(3, kind.height / 2, kind.width - 3, kind.height / 2);
				}
				g.fillStyle(0xffffff, 0.35).fillRoundedRect(
					4,
					4,
					kind.width - 8,
					Math.min(10, kind.height / 4),
					4,
				);
				g.generateTexture(key, kind.width, kind.height);
				g.destroy();
			});
		}

		/** Redraws one bin; `fresh` blocks (the newest) drop in from above. */
		private drawBin(power: number, count: number, fresh = 0) {
			for (const block of this.blocks[power] ?? []) block.destroy();
			const { scale, positions } = binLayout(count, power, binWidth);
			const bin = this.bins[power];
			this.blocks[power] = positions.map((position, at) => {
				const block = this.add
					.image(position.x, position.y, `block-${power}`)
					.setScale(scale);
				bin?.add(block);
				if (!reducedMotion && at >= count - fresh) {
					block.y = -60;
					this.tweens.add({
						targets: block,
						y: position.y,
						duration: 420,
						delay: (at - (count - fresh)) * 40,
						ease: "Bounce.easeOut",
					});
				}
				return block;
			});
			this.counts[power] = count;
		}

		show(counts: readonly number[], event: FactoryEvent) {
			if (event.type === "bundle" && !reducedMotion) {
				this.animateBundle(event.from, counts);
				return;
			}
			counts.forEach((count, power) => {
				const before = this.counts[power] ?? 0;
				const fresh = event.type === "feed" ? Math.max(0, count - before) : 0;
				if (count !== before || event.type === "set")
					this.drawBin(power, count, fresh);
			});
		}

		private animateBundle(from: number, counts: readonly number[]) {
			const leaving = (this.blocks[from] ?? []).slice(-10);
			const startX = binLeft(from) + binWidth / 2;
			const ghosts = leaving.map((block) =>
				this.add
					.image(binLeft(from) + block.x, block.y, `block-${from}`)
					.setScale(block.scale),
			);
			this.drawBin(from, counts[from] ?? 0);
			this.tweens.add({
				targets: ghosts,
				x: startX,
				y: CONVEYOR_Y - 30,
				scale: 0.35,
				duration: 380,
				ease: "Cubic.easeIn",
				onComplete: () => {
					for (const ghost of ghosts) ghost.destroy();
					const made = this.add
						.image(startX, CONVEYOR_Y - 34, `block-${from + 1}`)
						.setScale(0.6);
					const flash = this.add.circle(
						startX,
						CONVEYOR_Y - 34,
						70,
						0xfff3a6,
						0.8,
					);
					this.tweens.add({
						targets: flash,
						scale: 1.8,
						alpha: 0,
						duration: 400,
						onComplete: () => flash.destroy(),
					});
					this.tweens.add({
						targets: made,
						x: binLeft(from + 1) + binWidth / 2,
						duration: 650,
						delay: 150,
						ease: "Sine.easeInOut",
						onComplete: () => {
							made.destroy();
							this.drawBin(from + 1, counts[from + 1] ?? 0, 1);
						},
					});
				},
			});
		}

		refuse(power: number) {
			const bin = this.bins[power];
			if (!bin || reducedMotion) return;
			const x = bin.x;
			this.tweens.add({
				targets: bin,
				x: x + 10,
				duration: 50,
				yoyo: true,
				repeat: 3,
				onComplete: () => bin.setX(x),
			});
		}
	}
	return FactoryScene;
}

type FactoryScene = InstanceType<ReturnType<typeof createFactoryScene>>;
