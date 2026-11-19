/**
 * The Sky City scene: airships bring three crates, the child drags (or taps) each one into the
 * warehouse, and the warehouse gate opens or stays shut. Rules and scoring live elsewhere; the
 * scene only draws and reports which crate was loaded.
 */

import type PhaserNamespace from "phaser";
import { readyArt, SKY_CITY_ART, type SkyArtKey } from "./skyArt";
import { CRATE_LABELS } from "./skyRules";

export const WIDTH = 1920;
export const HEIGHT = 1080;

export type NimoPose = "idle" | "think" | "cheer";

export type SkyCityHandle = {
	loadCrate(index: number): void;
	pose(pose: NimoPose): void;
	celebrate(): void;
	stayLocked(): void;
	destroy(): void;
};

type Options = {
	addends: readonly number[];
	reducedMotion: boolean;
	onCrateLoaded(index: number): void;
};

type Scene = PhaserNamespace.Scene;
type Container = PhaserNamespace.GameObjects.Container;
type TweenConfig = PhaserNamespace.Types.Tweens.TweenBuilderConfig;

// Crate centres rest on the boardwalk, whose top is at y ≈ 792 in the city background.
const DOCK_Y = 720;
const CRATE_X = [700, 960, 1220];
const WAREHOUSE = { x: 1670, y: 540, width: 400, height: 520 };
/** The painted warehouse stands on the boardwalk; its doorway is the drop target. */
const WAREHOUSE_ART = { baseY: 812, width: 420, doorFromBottom: 0.26 };
const AIRSHIP_WIDTH = 280;
const CRATE_SIZE = { width: 200, height: 150 };
const NIMO_HEIGHT = 300;
const NIMO_ART: Record<NimoPose, SkyArtKey> = {
	idle: "nimoIdle",
	think: "nimoThink",
	cheer: "nimoCheer",
};
const BALLOON_COLOURS = [0xef5b5b, 0x4a90e2, 0xf5a623];
const AIRSHIP_ART: SkyArtKey[] = ["airshipRed", "airshipBlue", "airshipOrange"];
const LETTER_COLOURS = ["#d64545", "#2f6fc9", "#2e9b4f"];
const NUMBER_FONT = "Fredoka Variable, sans-serif";

/** Starts one Phaser game in `host` and resolves once the scene has been built. */
export async function mountSkyCity(
	host: HTMLElement,
	options: Options,
): Promise<SkyCityHandle> {
	const { default: Phaser } = await import("phaser");
	return new Promise((resolve) => {
		const SkyCity = createSkyCityScene(Phaser, options, (scene) =>
			resolve({
				loadCrate: (index) => scene.loadCrate(index),
				pose: (pose) => scene.pose(pose),
				celebrate: () => scene.celebrate(),
				stayLocked: () => scene.stayLocked(),
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
			scene: SkyCity,
			banner: false,
		});
	});
}

function createSkyCityScene(
	Phaser: typeof PhaserNamespace,
	options: Options,
	onReady: (scene: SkyCityScene) => void,
) {
	class SkyCityScene extends Phaser.Scene {
		private crates: Container[] = [];
		private loaded = new Set<number>();
		private gate?: PhaserNamespace.GameObjects.Graphics;
		private gateGlow?: PhaserNamespace.GameObjects.Graphics;
		private house?: PhaserNamespace.GameObjects.Image;
		private doorY = WAREHOUSE.y + 160;
		private nimo?: Container;
		private nimoImage?: PhaserNamespace.GameObjects.Image;
		private windows: PhaserNamespace.GameObjects.Rectangle[] = [];

		constructor() {
			super("sky-city");
		}

		preload() {
			for (const [key, url] of readyArt(SKY_CITY_ART))
				this.load.image(key, url);
		}

		create() {
			this.crates = [];
			this.loaded = new Set();
			this.windows = [];
			// The painted city brings its own buildings and boardwalk; shapes stand in without it.
			const painted = drawSky(this, options.reducedMotion);
			if (!painted) this.windows = drawCity(this);
			this.drawWarehouse();
			if (!painted) drawDock(this);
			this.nimo = this.drawNimo();
			loop(this, options.reducedMotion, {
				targets: this.nimo,
				y: this.nimo.y - 12,
				duration: 900,
				yoyo: true,
				repeat: -1,
				ease: "Sine.easeInOut",
			});
			options.addends.slice(0, 3).forEach((value, index) => {
				this.flyInAirship(index, value);
			});
			onReady(this);
		}

		/** A one-off tween; with reduced motion it jumps straight to the end. */
		private move(config: TweenConfig) {
			this.tweens.add(
				options.reducedMotion
					? { ...config, duration: 0, delay: 0, yoyo: false, repeat: 0 }
					: config,
			);
		}

		private drawWarehouse() {
			const { x, y, width, height } = WAREHOUSE;
			if (this.textures.exists("warehouseLocked")) {
				const house = this.add
					.image(x, WAREHOUSE_ART.baseY, "warehouseLocked")
					.setOrigin(0.5, 1);
				house.setScale(WAREHOUSE_ART.width / house.width);
				this.house = house;
				this.doorY =
					WAREHOUSE_ART.baseY -
					house.displayHeight * WAREHOUSE_ART.doorFromBottom;
				return;
			} else {
				const house = this.add.graphics();
				house
					.fillStyle(0x9aa3ad)
					.fillRect(x - width / 2, y - height / 2 + 80, width, height - 80);
				house
					.fillStyle(0xb5413c)
					.fillTriangle(
						x - width / 2 - 30,
						y - height / 2 + 90,
						x + width / 2 + 30,
						y - height / 2 + 90,
						x,
						y - height / 2 - 40,
					);
			}
			this.gateGlow = this.add.graphics().setAlpha(0);
			this.gateGlow.fillStyle(0xffe066, 0.55).fillCircle(x, y + 130, 230);
			this.gate = this.add.graphics();
			this.paintGate(false);
		}

		private paintGate(open: boolean) {
			const gate = this.gate;
			if (!gate) return;
			const { x, y } = WAREHOUSE;
			gate.clear();
			gate
				.fillStyle(open ? 0xffd23f : 0x4b3a2a)
				.fillRoundedRect(x - 120, y - 20, 240, 300, {
					tl: 120,
					tr: 120,
					bl: 0,
					br: 0,
				});
			if (!open) {
				gate.fillStyle(0xd9a441).fillRoundedRect(x - 26, y + 110, 52, 60, 8);
				gate.lineStyle(10, 0xd9a441).strokeCircle(x, y + 104, 20);
			}
		}

		private flyInAirship(index: number, value: number) {
			const targetX = CRATE_X[index] ?? 960;
			const ship = this.add.container(-260, 280 + (index % 2) * 30);
			const artKey = AIRSHIP_ART[index] ?? "airshipRed";
			let basketY = 90;
			if (this.textures.exists(artKey)) {
				const art = this.add.image(0, 0, artKey);
				art.setScale(AIRSHIP_WIDTH / art.width);
				basketY = art.displayHeight / 2 - 20;
				ship.add(art);
			} else {
				ship.add([
					this.add.ellipse(
						0,
						-30,
						230,
						110,
						BALLOON_COLOURS[index] ?? 0xef5b5b,
					),
					this.add.ellipse(0, -30, 230, 40, 0xffffff, 0.35),
					this.add.rectangle(-60, 40, 6, 60, 0x6b4a2b),
					this.add.rectangle(60, 40, 6, 60, 0x6b4a2b),
					this.add.rectangle(0, 80, 140, 44, 0x8a5a2b),
				]);
			}
			this.move({
				targets: ship,
				x: targetX,
				duration: 1400,
				delay: index * 500,
				ease: "Cubic.easeOut",
				onComplete: () => {
					this.dropCrate(index, value, ship.x, ship.y + basketY);
					loop(this, options.reducedMotion, {
						targets: ship,
						y: ship.y - 14,
						duration: 1600,
						yoyo: true,
						repeat: -1,
						ease: "Sine.easeInOut",
					});
				},
			});
		}

		private dropCrate(
			index: number,
			value: number,
			fromX: number,
			fromY: number,
		) {
			const crate = this.add.container(fromX, fromY);
			if (this.textures.exists("crate")) {
				const art = this.add.image(0, 0, "crate");
				crate.add(art.setScale(CRATE_SIZE.width / art.width));
			} else {
				crate.add([
					this.add
						.rectangle(0, 0, 200, 150, 0xc98b4a)
						.setStrokeStyle(8, 0x8a5a2b),
					this.add.rectangle(0, 0, 200, 14, 0x8a5a2b),
				]);
			}
			crate.add([
				this.add.circle(0, -52, 30, 0xffffff).setStrokeStyle(4, 0x8a5a2b),
				this.add
					.text(0, -52, CRATE_LABELS[index] ?? "", {
						fontFamily: NUMBER_FONT,
						fontSize: "38px",
						fontStyle: "bold",
						color: LETTER_COLOURS[index] ?? "#333",
					})
					.setOrigin(0.5),
				this.add
					.rectangle(0, 22, 150, 64, 0xfff6df)
					.setStrokeStyle(4, 0x8a5a2b),
				this.add
					.text(0, 22, String(value), {
						fontFamily: NUMBER_FONT,
						fontSize: "50px",
						fontStyle: "bold",
						color: "#3a2a1a",
					})
					.setOrigin(0.5),
			]);
			crate
				.setSize(200, 150)
				.setInteractive({ draggable: true, useHandCursor: true });
			this.crates[index] = crate;
			if (this.loaded.has(index)) {
				// Loaded from the delivery board before the airship arrived.
				crate.setVisible(false).disableInteractive();
				return;
			}
			this.move({
				targets: crate,
				y: DOCK_Y,
				duration: 700,
				ease: "Bounce.easeOut",
			});

			let dragged = false;
			crate.on("dragstart", () => {
				dragged = false;
				crate.setScale(1.08);
			});
			crate.on("drag", (_pointer: unknown, x: number, y: number) => {
				dragged = true;
				crate.setPosition(x, y);
			});
			crate.on("dragend", () => {
				crate.setScale(1);
				if (crate.x > WAREHOUSE.x - WAREHOUSE.width / 2 - 40)
					this.loadCrate(index, true);
				else
					this.move({
						targets: crate,
						x: fromX,
						y: DOCK_Y,
						duration: 250,
						ease: "Back.easeOut",
					});
			});
			// A tap without dragging loads the crate too.
			crate.on("pointerup", () => {
				if (!dragged) this.loadCrate(index, true);
			});
		}

		loadCrate(index: number, fromScene = false) {
			if (this.loaded.has(index)) return;
			this.loaded.add(index);
			const crate = this.crates[index];
			if (crate) {
				crate.disableInteractive();
				this.move({
					targets: crate,
					x: WAREHOUSE.x,
					y: this.doorY,
					scale: 0.3,
					alpha: 0,
					duration: 500,
					ease: "Cubic.easeIn",
				});
			}
			if (fromScene) options.onCrateLoaded(index);
		}

		private drawNimo() {
			if (this.textures.exists(NIMO_ART.idle)) {
				const nimo = this.add.container(250, 870);
				this.nimoImage = this.add.image(0, 0, NIMO_ART.idle).setOrigin(0.5, 1);
				this.nimoImage.setScale(NIMO_HEIGHT / this.nimoImage.height);
				nimo.add(this.nimoImage);
				return nimo;
			}
			return drawNimoShape(this);
		}

		pose(pose: NimoPose) {
			const image = this.nimoImage;
			const key = NIMO_ART[pose];
			if (!image || !this.textures.exists(key)) return;
			image.setTexture(key);
			image.setScale(NIMO_HEIGHT / image.height);
		}

		celebrate() {
			this.pose("cheer");
			if (this.house) this.house.setTexture("warehouseOpen");
			else {
				this.paintGate(true);
				this.gateGlow?.setAlpha(1);
			}
			for (const window of this.windows) window.setFillStyle(0xffe066);
			if (this.nimo) {
				this.move({
					targets: this.nimo,
					y: this.nimo.y - 60,
					duration: 260,
					yoyo: true,
					repeat: 3,
					ease: "Quad.easeOut",
				});
			}
			if (options.reducedMotion) return;
			const { x } = WAREHOUSE;
			for (let spark = 0; spark < 24; spark++) {
				const angle = (spark / 24) * Math.PI * 2;
				const dot = this.add.circle(
					x,
					this.doorY,
					10,
					[0xffd23f, 0xffffff, 0x7fe0ff][spark % 3],
				);
				this.tweens.add({
					targets: dot,
					x: x + Math.cos(angle) * 320,
					y: this.doorY + Math.sin(angle) * 260,
					alpha: 0,
					duration: 1100,
					ease: "Cubic.easeOut",
					onComplete: () => dot.destroy(),
				});
			}
		}

		stayLocked() {
			this.pose("think");
			const target = this.house ?? this.gate;
			if (!target || options.reducedMotion) return;
			this.tweens.add({
				targets: target,
				x: target.x + 14,
				duration: 60,
				yoyo: true,
				repeat: 4,
			});
		}
	}
	return SkyCityScene;
}

type SkyCityScene = InstanceType<ReturnType<typeof createSkyCityScene>>;

/** An endless idle tween; skipped entirely with reduced motion. */
function loop(scene: Scene, reducedMotion: boolean, config: TweenConfig) {
	if (!reducedMotion) scene.tweens.add(config);
}

/** Draws the sky; returns true when the painted city background was used. */
function drawSky(scene: Scene, reducedMotion: boolean): boolean {
	if (scene.textures.exists("bgSkyCity")) {
		scene.add
			.image(WIDTH / 2, HEIGHT / 2, "bgSkyCity")
			.setDisplaySize(WIDTH, HEIGHT);
		return true;
	}
	const sky = scene.add.graphics();
	sky.fillGradientStyle(0x6ec6ff, 0x6ec6ff, 0xd8f1ff, 0xd8f1ff, 1);
	sky.fillRect(0, 0, WIDTH, HEIGHT);
	for (const [x, y, size] of [
		[260, 140, 1],
		[820, 90, 0.8],
		[1350, 170, 1.1],
		[1760, 80, 0.7],
	]) {
		const cloud = scene.add.container(x, y);
		for (const [dx, dy, r] of [
			[-60, 10, 50],
			[0, -10, 70],
			[70, 12, 48],
		]) {
			cloud.add(
				scene.add.circle(dx * size, dy * size, r * size, 0xffffff, 0.92),
			);
		}
		loop(scene, reducedMotion, {
			targets: cloud,
			x: x + 60,
			duration: 9000,
			yoyo: true,
			repeat: -1,
			ease: "Sine.easeInOut",
		});
	}
	for (const [x, y, w] of [
		[380, 420, 260],
		[1180, 330, 200],
	]) {
		const island = scene.add.graphics();
		island.fillStyle(0x7cc95b).fillEllipse(x, y, w, 50);
		island
			.fillStyle(0x9a8c7a)
			.fillTriangle(x - w / 2 + 10, y + 10, x + w / 2 - 10, y + 10, x, y + 110);
	}
	return false;
}

function drawCity(scene: Scene) {
	const city = scene.add.graphics();
	const windows: PhaserNamespace.GameObjects.Rectangle[] = [];
	for (const [x, y, w, h] of [
		[60, 560, 180, 340],
		[250, 620, 150, 280],
		[420, 520, 170, 380],
		[1240, 600, 180, 300],
	]) {
		city.fillStyle(0xe9d8b8).fillRect(x, y, w, h);
		city
			.fillStyle(0xc0504d)
			.fillTriangle(x - 12, y, x + w + 12, y, x + w / 2, y - 70);
		for (let row = 0; row < 3; row++) {
			for (let col = 0; col < 2; col++) {
				windows.push(
					scene.add.rectangle(
						x + w * (0.3 + col * 0.4),
						y + 60 + row * 80,
						36,
						44,
						0x5b6b82,
					),
				);
			}
		}
	}
	return windows;
}

function drawDock(scene: Scene) {
	const dock = scene.add.graphics();
	dock.fillStyle(0xa0703c).fillRect(560, DOCK_Y + 70, 1320, 36);
	dock.fillStyle(0x7a5229);
	for (let x = 600; x < 1860; x += 140) dock.fillRect(x, DOCK_Y + 106, 18, 120);
}

/** Placeholder Nimo made of shapes, used until the art is available. */
function drawNimoShape(scene: Scene) {
	const nimo = scene.add.container(250, 755);
	nimo.add([
		scene.add.ellipse(0, 40, 130, 150, 0x3f8fe0),
		scene.add.ellipse(0, 55, 70, 90, 0xffffff),
		scene.add.triangle(-38, -95, 0, 40, 18, 0, 36, 40, 0x3f8fe0),
		scene.add.triangle(38, -95, 0, 40, 18, 0, 36, 40, 0x3f8fe0),
		scene.add.circle(0, -45, 62, 0x3f8fe0),
		scene.add.ellipse(0, -28, 70, 44, 0xffffff),
		scene.add.circle(-20, -55, 8, 0x1d1d28),
		scene.add.circle(20, -55, 8, 0x1d1d28),
		scene.add.rectangle(0, 10, 120, 22, 0xf27a1a),
	]);
	return nimo;
}
