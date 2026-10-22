import type Phaser from "phaser";
import type {
	BoardCard,
	BoardLayout,
	BoardLink,
	BoardPicture,
	BoardTarget,
} from "./types";

type PhaserModule = typeof Phaser;
type Container = Phaser.GameObjects.Container;
type Rect = { x: number; y: number; w: number; h: number };

export const WIDTH = 360;
const PAD = 12;
const CARD_H = 58;
const GAP = 10;
const FONT =
	'"Avenir Next", "Noto Sans Sinhala", "Nirmala UI", "Iskoola Pota", ui-rounded, system-ui, sans-serif';
const EMOJI =
	'"Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif';

export type BoardTheme = {
	background: number;
	card: number;
	cardStroke: number;
	target: number;
	targetStroke: number;
	accent: number;
	ink: string;
};

export const THEMES: Record<string, BoardTheme> = {
	meadow: {
		background: 0xeef8ef,
		card: 0xffffff,
		cardStroke: 0x7c4bad,
		target: 0xfffdf7,
		targetStroke: 0xc5b0d8,
		accent: 0x2fa36b,
		ink: "#24324a",
	},
	sky: {
		background: 0xeaf4ff,
		card: 0xffffff,
		cardStroke: 0x2f6fb5,
		target: 0xfdfeff,
		targetStroke: 0xa9c6e8,
		accent: 0xf2a33a,
		ink: "#1d3557",
	},
	market: {
		background: 0xfff3da,
		card: 0xffffff,
		cardStroke: 0xb5651d,
		target: 0xfffaf0,
		targetStroke: 0xe2bf8a,
		accent: 0x2fa36b,
		ink: "#4a2c12",
	},
	night: {
		background: 0x1f2a4a,
		card: 0xffffff,
		cardStroke: 0x6c5ce7,
		// Light targets on the night sky, so their dark labels stay readable.
		target: 0xf4f2ff,
		targetStroke: 0x8f9bd8,
		accent: 0xffd166,
		ink: "#1f2a4a",
	},
};

export type BoardSceneConfig = {
	layout: BoardLayout;
	cards: BoardCard[];
	targets: BoardTarget[];
	theme: BoardTheme;
	/** Hotspots: the picture the markers sit on; slots: an optional picture above the row. */
	background?: BoardPicture;
	reducedMotion: boolean;
	/** The illustrated banner above the board: a place, a guide who talks, a few props. */
	scene?: BoardSceneArt;
	/** What the guide says before the child starts. */
	instruction?: string;
};

export type BoardSceneArt = {
	/** A curriculum illustration filling the banner. */
	backdrop?: string;
	/** A character image standing in the banner. */
	guide?: string;
	/** Emoji that float about the banner. */
	props?: string[];
	/** Banner colour behind everything, when there is no backdrop. */
	sky?: number;
};

export const SCENE_H = 196;

export type BoardBridge = {
	links(): BoardLink[];
	marks(): ReadonlySet<string>;
	place(source: string, target: string, tap: boolean): void;
	remove(source: string, tap: boolean): void;
	invalid(): void;
	ready(): void;
};

/** Where everything goes, computed once from the config. */
export function measure(config: BoardSceneConfig) {
	const inner = WIDTH - PAD * 2;
	// Tray: cards flow in rows of up to three, wide enough for their words.
	const perRow = config.cards.length <= 4 ? 2 : 3;
	const cardW = (inner - GAP * (perRow - 1)) / perRow;
	const trayRows = Math.ceil(config.cards.length / perRow);
	const home = new Map<string, Rect>();
	config.cards.forEach((card, index) => {
		const col = index % perRow;
		const row = Math.floor(index / perRow);
		home.set(card.id, {
			x: PAD + col * (cardW + GAP) + cardW / 2,
			y: PAD + row * (CARD_H + GAP) + CARD_H / 2,
			w: cardW,
			h: CARD_H,
		});
	});
	let y = PAD + trayRows * (CARD_H + GAP) + 18;
	const targets = new Map<string, Rect>();
	const markers = new Map<string, Rect>();
	let picture: Rect | null = null;
	const { layout } = config;
	if (layout === "grid") {
		const cols = config.targets.length <= 4 ? 2 : 3;
		const w = (inner - GAP * (cols - 1)) / cols;
		const h = cols === 2 ? 178 : 156;
		config.targets.forEach((target, index) => {
			targets.set(target.id, {
				x: PAD + (index % cols) * (w + GAP) + w / 2,
				y: y + Math.floor(index / cols) * (h + GAP) + h / 2,
				w,
				h,
			});
		});
		y += Math.ceil(config.targets.length / cols) * (h + GAP);
	} else if (layout === "bins") {
		const cols = config.targets.length === 1 ? 1 : 2;
		const w = (inner - GAP * (cols - 1)) / cols;
		const most = Math.max(
			...config.targets.map(
				(target) =>
					target.capacity ??
					Math.ceil(config.cards.length / Math.max(1, config.targets.length)) +
						1,
			),
		);
		const h = 92 + Math.min(most, config.cards.length) * (CARD_H * 0.78 + 6);
		config.targets.forEach((target, index) => {
			targets.set(target.id, {
				x: PAD + (index % cols) * (w + GAP) + w / 2,
				y: y + Math.floor(index / cols) * (h + GAP) + h / 2,
				w,
				h,
			});
		});
		y += Math.ceil(config.targets.length / cols) * (h + GAP);
	} else if (layout === "slots") {
		if (config.background) {
			picture = { x: WIDTH / 2, y: y + 70, w: 160, h: 140 };
			y += 152;
		}
		const n = config.targets.length;
		const perRowSlots = Math.min(n, 4);
		const w = (inner - GAP * (perRowSlots - 1)) / perRowSlots;
		config.targets.forEach((target, index) => {
			targets.set(target.id, {
				x: PAD + (index % perRowSlots) * (w + GAP) + w / 2,
				y:
					y + Math.floor(index / perRowSlots) * (CARD_H + 30) + CARD_H / 2 + 12,
				w,
				h: CARD_H + 16,
			});
		});
		y += Math.ceil(n / perRowSlots) * (CARD_H + 30) + 12;
	} else {
		// Hotspots: the picture keeps its shape (at most the width, 420 tall) with numbered markers
		// on it; below it, one numbered answer slot per marker, so placed words never overlap.
		const aspect = config.background?.aspect ?? inner / 300;
		const h = Math.min(inner / aspect, 420);
		const w = h * aspect;
		const left = WIDTH / 2 - w / 2;
		picture = { x: WIDTH / 2, y: y + h / 2, w, h };
		for (const target of config.targets)
			markers.set(target.id, {
				x: left + ((target.x ?? 50) / 100) * w,
				y: y + ((target.y ?? 50) / 100) * h,
				w: 56,
				h: 56,
			});
		y += h + 14;
		const slotW = (inner - GAP) / 2;
		config.targets.forEach((target, index) => {
			targets.set(target.id, {
				x: PAD + (index % 2) * (slotW + GAP) + slotW / 2,
				y: y + Math.floor(index / 2) * (CARD_H + 22) + (CARD_H + 12) / 2,
				w: slotW,
				h: CARD_H + 12,
			});
		});
		y += Math.ceil(config.targets.length / 2) * (CARD_H + 22);
	}
	// Everything moves down below the illustrated banner, when there is one.
	const offset = config.scene ? SCENE_H + PAD : 0;
	const shift = (rect: Rect) => ({ ...rect, y: rect.y + offset });
	return {
		home: new Map([...home].map(([id, rect]) => [id, shift(rect)])),
		targets: new Map([...targets].map(([id, rect]) => [id, shift(rect)])),
		markers: new Map([...markers].map(([id, rect]) => [id, shift(rect)])),
		picture: picture ? shift(picture) : null,
		height: Math.ceil(y + PAD + offset),
		trayTop: offset,
		trayBottom: offset + PAD + trayRows * (CARD_H + GAP),
	};
}

export function createBoardScene(
	PhaserLib: PhaserModule,
	config: BoardSceneConfig,
	bridge: BoardBridge,
) {
	const geometry = measure(config);
	const { theme } = config;
	const calm = config.reducedMotion;

	return class BoardScene extends PhaserLib.Scene {
		private pieces = new Map<string, Container>();
		private zones = new Map<string, Phaser.GameObjects.Rectangle>();
		private zoneGlow = new Map<string, Phaser.GameObjects.Rectangle>();
		private selected: string | null = null;
		private dragged = false;

		preload() {
			const images = [
				config.scene?.backdrop,
				config.scene?.guide,
				config.background?.image,
				...config.targets.map((target) => target.picture?.image),
				...config.cards.map((card) => card.picture?.image),
			].filter((src): src is string => Boolean(src));
			for (const src of new Set(images)) this.load.image(src, src);
		}

		create() {
			this.cameras.main.setBackgroundColor(theme.background);
			this.input.dragDistanceThreshold = 10;
			this.drawScene();
			this.drawTray();
			this.drawBackground();
			for (const target of config.targets) this.drawTarget(target);
			for (const card of config.cards) this.drawCard(card);
			this.wireInput();
			this.game.events.on("board-state", this.layoutPieces, this);
			this.game.events.on("board-marks", this.paintMarks, this);
			this.events.once("shutdown", () => {
				this.game.events.off("board-state", this.layoutPieces, this);
				this.game.events.off("board-marks", this.paintMarks, this);
			});
			this.layoutPieces(true);
			this.paintMarks();
			bridge.ready();
		}

		private drawTray() {
			const top = geometry.trayTop + 4;
			const h = geometry.trayBottom - geometry.trayTop + 4;
			const g = this.add.graphics();
			g.fillStyle(0xffffff, 0.55).fillRoundedRect(4, top, WIDTH - 8, h, 18);
			// Tapping the tray sends the selected card home.
			const tray = this.add
				.rectangle(WIDTH / 2, top + h / 2, WIDTH - 8, h)
				.setInteractive({ dropZone: true })
				.setAlpha(0.001);
			tray.setData("tray", true);
			tray.on("pointerup", () => {
				if (this.selected && this.linkOf(this.selected))
					bridge.remove(this.selected, true);
				this.select(null);
			});
		}

		private drawBackground() {
			const frame = geometry.picture;
			if (!frame || !config.background) return;
			if (
				config.background.image &&
				this.textures.exists(config.background.image)
			) {
				const image = this.add.image(frame.x, frame.y, config.background.image);
				if (config.layout === "hotspots") {
					// Markers are placed in percent of this frame, so the image fills it exactly.
					image.setDisplaySize(frame.w, frame.h);
				} else {
					image.setScale(
						Math.min(frame.w / image.width, frame.h / image.height),
					);
				}
			} else if (config.background.emoji) {
				this.add
					.text(frame.x, frame.y, config.background.emoji, {
						fontFamily: EMOJI,
						fontSize: "96px",
					})
					.setOrigin(0.5);
			}
		}

		private drawTarget(target: BoardTarget) {
			const box = geometry.targets.get(target.id);
			if (!box) return;
			const hotspot = config.layout === "hotspots";
			const g = this.add.graphics();
			if (hotspot) {
				const marker = geometry.markers.get(target.id) as Rect;
				if (target.picture?.emoji)
					this.add
						.text(marker.x, marker.y - 34, target.picture.emoji, {
							fontFamily: EMOJI,
							fontSize: "30px",
						})
						.setOrigin(0.5);
				g.fillStyle(theme.cardStroke).fillCircle(marker.x, marker.y, 20);
				g.lineStyle(4, 0xffffff).strokeCircle(marker.x, marker.y, 20);
				this.add
					.text(marker.x, marker.y, target.marker ?? "•", {
						fontFamily: FONT,
						fontSize: "20px",
						fontStyle: "bold",
						color: "#ffffff",
					})
					.setOrigin(0.5);
				// The numbered answer slot below the picture.
				g.fillStyle(theme.target).fillRoundedRect(
					box.x - box.w / 2,
					box.y - box.h / 2,
					box.w,
					box.h,
					16,
				);
				g.lineStyle(3, theme.targetStroke).strokeRoundedRect(
					box.x - box.w / 2,
					box.y - box.h / 2,
					box.w,
					box.h,
					16,
				);
				g.fillStyle(theme.cardStroke).fillCircle(
					box.x - box.w / 2 + 20,
					box.y,
					15,
				);
				this.add
					.text(box.x - box.w / 2 + 20, box.y, target.marker ?? "•", {
						fontFamily: FONT,
						fontSize: "16px",
						fontStyle: "bold",
						color: "#ffffff",
					})
					.setOrigin(0.5);
				// Dropping on the marker itself works too.
				const spot = this.add
					.rectangle(marker.x, marker.y, 64, 64)
					.setInteractive({ dropZone: true, useHandCursor: true })
					.setAlpha(0.001);
				spot.setData("target", target.id);
				spot.on("pointerup", () => {
					if (this.dragged || !this.selected) return;
					bridge.place(this.selected, target.id, true);
					this.select(null);
				});
			} else {
				g.fillStyle(theme.target).fillRoundedRect(
					box.x - box.w / 2,
					box.y - box.h / 2,
					box.w,
					box.h,
					18,
				);
				g.lineStyle(3, theme.targetStroke).strokeRoundedRect(
					box.x - box.w / 2,
					box.y - box.h / 2,
					box.w,
					box.h,
					18,
				);
				const top = box.y - box.h / 2;
				if (config.layout === "grid") {
					this.drawPicture(
						target.picture,
						box.x,
						top + 54,
						target.label ? 52 : 64,
					);
					if (target.label)
						this.add
							.text(
								box.x,
								target.picture ? top + 104 : top + 50,
								target.label,
								{
									fontFamily: FONT,
									fontSize: target.picture ? "19px" : "25px",
									fontStyle: "bold",
									color: theme.ink,
									align: "center",
									wordWrap: { width: box.w - 16 },
								},
							)
							.setOrigin(0.5);
					// The empty place where the word card will sit.
					g.lineStyle(2, theme.targetStroke, 0.9);
					g.strokeRoundedRect(
						box.x - box.w / 2 + 10,
						box.y + box.h / 2 - CARD_H - 18,
						box.w - 20,
						CARD_H + 8,
						12,
					);
				} else if (config.layout === "bins") {
					if (target.picture)
						this.drawPicture(
							target.picture,
							box.x - box.w / 2 + 34,
							top + 34,
							34,
						);
					this.add
						.text(
							target.picture ? box.x + 16 : box.x,
							top + 34,
							target.label ?? "",
							{
								fontFamily: FONT,
								fontSize: "20px",
								fontStyle: "bold",
								color: theme.ink,
								align: "center",
								wordWrap: { width: box.w - (target.picture ? 70 : 20) },
							},
						)
						.setOrigin(0.5);
					g.lineStyle(2, theme.targetStroke, 0.7).lineBetween(
						box.x - box.w / 2 + 14,
						top + 64,
						box.x + box.w / 2 - 14,
						top + 64,
					);
				} else if (target.label) {
					this.add
						.text(box.x, top - 2, target.label, {
							fontFamily: FONT,
							fontSize: "14px",
							color: "#75618b",
						})
						.setOrigin(0.5, 1);
				}
			}
			// The drop zone (and tap target) covers the whole box, or a generous circle on a hotspot.
			const zone = this.add
				.rectangle(box.x, box.y, box.w, box.h)
				.setInteractive({ dropZone: true, useHandCursor: true })
				.setAlpha(0.001);
			zone.setData("target", target.id);
			zone.on("pointerup", () => {
				if (this.dragged) return;
				if (this.selected) {
					bridge.place(this.selected, target.id, true);
					this.select(null);
				}
			});
			this.zones.set(target.id, zone);
			const glow = this.add
				.rectangle(box.x, box.y, box.w + 6, box.h + 6)
				.setStrokeStyle(4, theme.accent)
				.setFillStyle(theme.accent, 0.06)
				.setVisible(false);
			this.zoneGlow.set(target.id, glow);
		}

		private drawPicture(
			picture: BoardPicture | undefined,
			x: number,
			y: number,
			size: number,
		) {
			if (!picture) return;
			if (picture.image && this.textures.exists(picture.image)) {
				const image = this.add.image(x, y, picture.image);
				image.setScale(
					Math.min((size * 1.6) / image.width, (size * 1.6) / image.height),
				);
			} else if (picture.emoji) {
				this.add
					.text(x, y, picture.emoji, {
						fontFamily: EMOJI,
						fontSize: `${size}px`,
					})
					.setOrigin(0.5);
			}
		}

		private drawCard(card: BoardCard) {
			const home = geometry.home.get(card.id);
			if (!home) return;
			const bg = this.add.graphics();
			const paint = (fill: number, stroke: number, width: number) => {
				bg.clear();
				bg.fillStyle(0x000000, 0.12).fillRoundedRect(
					-home.w / 2 + 2,
					-home.h / 2 + 4,
					home.w,
					home.h,
					16,
				);
				bg.fillStyle(fill).fillRoundedRect(
					-home.w / 2,
					-home.h / 2,
					home.w,
					home.h,
					16,
				);
				bg.lineStyle(width, stroke).strokeRoundedRect(
					-home.w / 2,
					-home.h / 2,
					home.w,
					home.h,
					16,
				);
			};
			paint(theme.card, theme.cardStroke, 3);
			const text = `${card.picture?.emoji ? `${card.picture.emoji} ` : ""}${card.label}`;
			const label = this.add
				.text(0, 0, text, {
					fontFamily: `${FONT}, ${EMOJI}`,
					fontSize: text.length > 16 ? "18px" : "22px",
					fontStyle: "bold",
					color: theme.ink,
					align: "center",
					wordWrap: { width: home.w - 14 },
				})
				.setOrigin(0.5);
			const piece = this.add
				.container(home.x, home.y, [bg, label])
				.setSize(home.w, home.h)
				.setInteractive({ useHandCursor: true, draggable: true });
			piece.setData("source", card.id);
			piece.setData("paint", paint);
			piece.setDepth(5);
			piece.on("pointerup", () => {
				if (this.dragged) return;
				this.select(this.selected === card.id ? null : card.id);
			});
			this.pieces.set(card.id, piece);
		}

		private wireInput() {
			this.input.on("dragstart", (_p: unknown, piece: Container) => {
				this.dragged = true;
				this.select(null);
				piece.setDepth(20);
				if (!calm)
					this.tweens.add({ targets: piece, scale: 1.08, duration: 90 });
			});
			this.input.on(
				"drag",
				(_p: unknown, piece: Container, x: number, y: number) => {
					piece.setPosition(x, y);
				},
			);
			this.input.on(
				"dragenter",
				(
					_p: unknown,
					_piece: Container,
					zone: Phaser.GameObjects.Rectangle,
				) => {
					const id = zone.getData("target") as string | undefined;
					if (id) this.zoneGlow.get(id)?.setVisible(true);
				},
			);
			this.input.on(
				"dragleave",
				(
					_p: unknown,
					_piece: Container,
					zone: Phaser.GameObjects.Rectangle,
				) => {
					const id = zone.getData("target") as string | undefined;
					if (id) this.paintMarks();
				},
			);
			this.input.on(
				"drop",
				(_p: unknown, piece: Container, zone: Phaser.GameObjects.Rectangle) => {
					const source = String(piece.getData("source"));
					const target = zone.getData("target") as string | undefined;
					if (target) {
						bridge.place(source, target, false);
						this.burst(zone.x, zone.y);
					} else if (zone.getData("tray") && this.linkOf(source))
						bridge.remove(source, false);
					else this.layoutPieces();
				},
			);
			this.input.on(
				"dragend",
				(_p: unknown, piece: Container, dropped: boolean) => {
					piece.setScale(1);
					if (!dropped) {
						bridge.invalid();
						this.shake(piece);
						this.layoutPieces();
					}
					this.paintMarks();
					// Let the pointerup that ends this drag pass before taps count again.
					this.time.delayedCall(0, () => {
						this.dragged = false;
					});
				},
			);
		}

		private linkOf(source: string) {
			return bridge.links().find((link) => link.source === source);
		}

		private select(id: string | null) {
			this.selected = id;
			for (const [cardId, piece] of this.pieces) {
				const paint = piece.getData("paint") as (
					f: number,
					s: number,
					w: number,
				) => void;
				const on = cardId === id;
				paint(
					on ? 0xfff6cc : theme.card,
					on ? theme.accent : theme.cardStroke,
					on ? 5 : 3,
				);
				if (on && !calm)
					this.tweens.add({
						targets: piece,
						scale: { from: 1, to: 1.06 },
						yoyo: true,
						duration: 140,
					});
			}
			// While a card is chosen, every target shows it can take it.
			for (const glow of this.zoneGlow.values()) glow.setVisible(Boolean(id));
			if (!id) this.paintMarks();
		}

		/** Put every card where the links say: home in the tray, or inside its target. */
		layoutPieces(instant = false) {
			const links = bridge.links();
			this.react(links.length, instant);
			const byTarget = new Map<string, string[]>();
			for (const link of [...links].sort((a, b) => a.sequence - b.sequence)) {
				byTarget.set(link.target, [
					...(byTarget.get(link.target) ?? []),
					link.source,
				]);
			}
			for (const [id, piece] of this.pieces) {
				const link = links.find((item) => item.source === id);
				let x: number,
					y: number,
					scale = 1;
				const home = geometry.home.get(id) as Rect;
				if (!link) {
					({ x, y } = home);
				} else {
					const box = geometry.targets.get(link.target) as Rect;
					const index = (byTarget.get(link.target) ?? []).indexOf(id);
					({ x, y, scale } = this.slotFor(box, index, home));
				}
				piece.setDepth(link ? 8 : 5);
				if (instant || calm) piece.setPosition(x, y).setScale(scale);
				else
					this.tweens.add({
						targets: piece,
						x,
						y,
						scale,
						duration: 220,
						ease: "Back.easeOut",
					});
			}
			this.paintMarks();
		}

		private slotFor(box: Rect, index: number, home: Rect) {
			if (config.layout === "grid") {
				const scale = Math.min(1, (box.w - 16) / home.w);
				return {
					x: box.x,
					y: box.y + box.h / 2 - CARD_H * scale * 0.5 - 10,
					scale,
				};
			}
			if (config.layout === "bins") {
				const scale = Math.min(0.78, (box.w - 20) / home.w);
				return {
					x: box.x,
					y:
						box.y -
						box.h / 2 +
						64 +
						8 +
						(CARD_H * scale) / 2 +
						index * (CARD_H * scale + 6),
					scale,
				};
			}
			if (config.layout === "slots") {
				const scale = Math.min(1, (box.w - 8) / home.w);
				return { x: box.x, y: box.y, scale };
			}
			// A hotspot's word sits in its numbered slot, right of the number.
			const scale = Math.min(1, (box.w - 46) / home.w);
			return { x: box.x + 16, y: box.y, scale };
		}

		/** Support hints: tint the cards and targets the help marked on the hidden list. */
		paintMarks() {
			const marks = bridge.marks();
			for (const [id, glow] of this.zoneGlow) {
				glow.setVisible(marks.has(id) || this.selected !== null);
			}
			for (const [id, piece] of this.pieces) {
				if (id === this.selected) continue;
				const paint = piece.getData("paint") as (
					f: number,
					s: number,
					w: number,
				) => void;
				paint(
					marks.has(id) ? 0xfff3c4 : theme.card,
					marks.has(id) ? theme.accent : theme.cardStroke,
					marks.has(id) ? 4 : 3,
				);
			}
		}

		private guide: Phaser.GameObjects.Image | null = null;
		private bubble: Phaser.GameObjects.Text | null = null;
		private placed = 0;

		/** The banner: the place, the guide in it, a speech bubble and a few floating props. */
		private drawScene() {
			const art = config.scene;
			if (!art) return;
			const frame = this.add.graphics();
			frame
				.fillStyle(art.sky ?? 0xbfe6ff)
				.fillRoundedRect(4, 4, WIDTH - 8, SCENE_H - 4, 20);
			if (art.backdrop && this.textures.exists(art.backdrop)) {
				const image = this.add.image(WIDTH / 2, SCENE_H / 2, art.backdrop);
				image.setScale(
					Math.max((WIDTH - 8) / image.width, (SCENE_H - 4) / image.height),
				);
				const mask = this.make.graphics({}, false);
				mask
					.fillStyle(0xffffff)
					.fillRoundedRect(4, 4, WIDTH - 8, SCENE_H - 4, 20);
				image.setMask(mask.createGeometryMask());
			}
			(art.props ?? []).forEach((emoji, index) => {
				const prop = this.add
					.text(WIDTH - 40 - index * 46, 30 + (index % 2) * 18, emoji, {
						fontFamily: EMOJI,
						fontSize: "30px",
					})
					.setOrigin(0.5);
				if (!calm)
					this.tweens.add({
						targets: prop,
						y: prop.y - 7,
						duration: 1100 + index * 170,
						yoyo: true,
						repeat: -1,
						ease: "Sine.easeInOut",
					});
			});
			if (art.guide && this.textures.exists(art.guide)) {
				const guide = this.add
					.image(64, SCENE_H - 4, art.guide)
					.setOrigin(0.5, 1);
				guide.setScale(
					Math.min(118 / guide.width, (SCENE_H - 24) / guide.height),
				);
				guide.setData("scale", guide.scale);
				if (!calm)
					this.tweens.add({
						targets: guide,
						y: guide.y - 4,
						duration: 1400,
						yoyo: true,
						repeat: -1,
						ease: "Sine.easeInOut",
					});
				this.guide = guide;
			}
			// The speech bubble, with a tail pointing at the guide.
			const left = art.guide ? 126 : 16;
			const g = this.add.graphics();
			g.fillStyle(0xffffff, 0.96).fillRoundedRect(
				left,
				66,
				WIDTH - left - 18,
				96,
				18,
			);
			g.fillTriangle(left + 2, 120, left - 16, 138, left + 18, 132);
			g.lineStyle(3, theme.cardStroke, 0.55).strokeRoundedRect(
				left,
				66,
				WIDTH - left - 18,
				96,
				18,
			);
			this.bubble = this.add
				.text(left + (WIDTH - left - 18) / 2, 114, config.instruction ?? "", {
					fontFamily: `${FONT}, ${EMOJI}`,
					fontSize: "19px",
					fontStyle: "bold",
					color: theme.ink,
					align: "center",
					wordWrap: { width: WIDTH - left - 44 },
				})
				.setOrigin(0.5);
		}

		/** The guide cheers each new placement and celebrates a full board. */
		private react(count: number, instant: boolean) {
			const before = this.placed;
			this.placed = count;
			if (instant || !this.bubble) return;
			const total = config.cards.length;
			const slotsLeft =
				config.layout === "slots"
					? config.targets.length - count
					: total - count;
			if (count > before) {
				this.bubble.setText(
					slotsLeft <= 0
						? "All done! Press the button to check. 🎉"
						: `Great move! ${count} of ${total} placed.`,
				);
				if (this.guide && !calm) {
					const guide = this.guide;
					this.tweens.add({
						targets: guide,
						y: guide.y - 18,
						duration: 160,
						yoyo: true,
						ease: "Quad.easeOut",
					});
				}
				if (slotsLeft <= 0) this.celebrate();
			} else if (count < before) {
				this.bubble.setText(`${count} of ${total} placed. Keep going!`);
			}
		}

		private celebrate() {
			if (calm) return;
			const colours = [0xffd166, 0x06d6a0, 0xef476f, 0x118ab2, theme.accent];
			for (let i = 0; i < 36; i++) {
				const piece = this.add
					.rectangle(
						PhaserLib.Math.Between(20, WIDTH - 20),
						-10,
						8,
						14,
						colours[i % colours.length],
					)
					.setDepth(40)
					.setAngle(PhaserLib.Math.Between(0, 180));
				this.tweens.add({
					targets: piece,
					y: PhaserLib.Math.Between(SCENE_H, SCENE_H + 260),
					angle: piece.angle + PhaserLib.Math.Between(180, 540),
					alpha: 0,
					duration: PhaserLib.Math.Between(900, 1500),
					ease: "Cubic.easeIn",
					onComplete: () => piece.destroy(),
				});
			}
		}

		private burst(x: number, y: number) {
			if (calm) return;
			for (let i = 0; i < 8; i++) {
				const angle = (Math.PI * 2 * i) / 8;
				const dot = this.add
					.circle(x, y, 5, i % 2 ? theme.accent : 0xffd166)
					.setDepth(30);
				this.tweens.add({
					targets: dot,
					x: x + Math.cos(angle) * 46,
					y: y + Math.sin(angle) * 46,
					alpha: 0,
					scale: 0.4,
					duration: 420,
					ease: "Cubic.easeOut",
					onComplete: () => dot.destroy(),
				});
			}
		}

		private shake(piece: Container) {
			if (calm) return;
			this.tweens.add({
				targets: piece,
				angle: { from: -6, to: 6 },
				duration: 60,
				yoyo: true,
				repeat: 2,
				onComplete: () => piece.setAngle(0),
			});
		}
	};
}
