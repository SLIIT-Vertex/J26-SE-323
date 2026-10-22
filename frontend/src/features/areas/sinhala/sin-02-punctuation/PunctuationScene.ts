import type Phaser from "phaser";
import type { SceneBridge } from "../../../gamification/phaser/bridge/GameEventBridge";

export type PunctuationSceneModel = {
	revision: string;
	chapter: string;
	tokens: string[];
	/** Gap id and the token index it follows (-1 = before the first token). */
	gaps: Array<{ id: string; after: number }>;
	cards: Array<{ id: string; text: string }>;
	placements: Record<string, string>;
	selected: string | null;
	emphasis: string | null;
	reducedMotion: boolean;
};
export type PunctuationSceneCommand = {
	type: "model";
	model: PunctuationSceneModel;
};
export type PunctuationSceneEvent =
	| { type: "select"; id: string }
	| { type: "place"; card: string; gap: string; via: "drag" | "tap" }
	| { type: "remove"; gap: string }
	| { type: "drag_cancelled"; id: string };

const FONT = '"Noto Sans Sinhala", "Iskoola Pota", sans-serif';
const INK = "#3b2a63";
const PURPLE = 0x6d4bb3;
const TARGET = 48;

/**
 * A sentence rail: tokens stay where they are while the child reads (nothing moves during
 * interaction), gaps between tokens are the only drop targets, and a mark card snaps into a
 * gap. A gap never falls inside a token, so no akshara or conjunct can be split.
 */
export function createPunctuationScene(
	PhaserRuntime: typeof Phaser,
	bridge: SceneBridge<PunctuationSceneCommand, PunctuationSceneEvent>,
): Phaser.Types.Scenes.SceneType {
	return class PunctuationScene extends PhaserRuntime.Scene {
		private model: PunctuationSceneModel | null = null;
		private drawn: string | null = null;
		private layer: Phaser.GameObjects.Container | null = null;
		private gapRects = new Map<string, Phaser.Geom.Rectangle>();
		private gapMarks = new Map<string, Phaser.GameObjects.Text>();
		private cardObjects = new Map<string, Phaser.GameObjects.Container>();
		private homes = new Map<string, { x: number; y: number }>();
		private unsubscribe: (() => void) | null = null;

		constructor() {
			super("punctuation-scene");
		}

		create(): void {
			this.input.dragDistanceThreshold = 8;
			this.unsubscribe = bridge.onCommand((command) => {
				this.model = command.model;
				this.render();
			});
			this.scale.on("resize", this.relayout, this);
			this.events.once("shutdown", () => this.cleanup());
			this.events.once("destroy", () => this.cleanup());
		}

		private cleanup(): void {
			this.unsubscribe?.();
			this.unsubscribe = null;
			this.scale.off("resize", this.relayout, this);
			this.tweens.killAll();
			this.layer?.destroy(true);
			this.layer = null;
			this.gapRects.clear();
			this.gapMarks.clear();
			this.cardObjects.clear();
			this.homes.clear();
		}

		private relayout(): void {
			this.drawn = null;
			this.render();
		}

		private render(): void {
			if (!this.model) return;
			if (this.drawn !== this.model.revision) this.rebuild(this.model);
			this.sync(this.model);
		}

		private label(text: string, size: number) {
			return this.add
				.text(0, 0, text, {
					fontFamily: FONT,
					fontSize: `${size}px`,
					color: INK,
					padding: {
						top: Math.ceil(size * 0.35),
						bottom: Math.ceil(size * 0.45),
						x: 2,
					},
				})
				.setOrigin(0, 0.5);
		}

		private rebuild(model: PunctuationSceneModel): void {
			this.tweens.killAll();
			this.layer?.destroy(true);
			this.gapRects.clear();
			this.gapMarks.clear();
			this.cardObjects.clear();
			this.homes.clear();
			const { width, height } = this.scale;
			const layer = this.add.container(0, 0);
			this.layer = layer;
			const g = this.add.graphics();
			g.fillStyle(0xfff8ec).fillRoundedRect(0, 0, width, height, 20);
			g.fillStyle(0xf1e4ff).fillRoundedRect(
				8,
				8,
				width - 16,
				height * 0.62,
				18,
			);
			layer.add(g);
			// Lay tokens and gaps left to right, wrapping by measured width (never mid-token).
			const size = width < 360 ? 18 : 21;
			const lineHeight = size * 2.6;
			let x = 18;
			let y = 30 + lineHeight / 2;
			const gapsAfter = new Map(model.gaps.map((gap) => [gap.after, gap.id]));
			const putGap = (id: string) => {
				if (x + TARGET > width - 14) {
					x = 18;
					y += lineHeight;
				}
				const rect = new PhaserRuntime.Geom.Rectangle(
					x,
					y - TARGET / 2,
					TARGET,
					TARGET,
				);
				this.gapRects.set(id, rect);
				const socket = this.add.graphics();
				socket
					.lineStyle(2, PURPLE, model.emphasis ? 0.9 : 0.5)
					.strokeRoundedRect(
						rect.x + 6,
						rect.y + 6,
						TARGET - 12,
						TARGET - 12,
						8,
					);
				const mark = this.label("", size + 4)
					.setOrigin(0.5)
					.setPosition(rect.centerX, rect.centerY);
				this.gapMarks.set(id, mark);
				const zone = this.add
					.zone(rect.centerX, rect.centerY, TARGET, TARGET)
					.setInteractive();
				zone.on("pointerup", () => {
					const current = this.model;
					if (!current) return;
					if (current.selected)
						bridge.emit({
							type: "place",
							card: current.selected,
							gap: id,
							via: "tap",
						});
					else if (current.placements[id])
						bridge.emit({ type: "remove", gap: id });
				});
				layer.add([socket, mark, zone]);
				x += TARGET + 4;
			};
			const opener = gapsAfter.get(-1);
			if (opener) putGap(opener);
			model.tokens.forEach((token, index) => {
				const text = this.label(token, size);
				if (x + text.width > width - 14 && x > 18) {
					x = 18;
					y += lineHeight;
				}
				text.setPosition(x, y);
				layer.add(text);
				x += text.width + 6;
				const gap = gapsAfter.get(index);
				if (gap) putGap(gap);
			});
			// Mark tray.
			const trayTop = Math.max(y + lineHeight, height * 0.66);
			const cardSize = Math.max(
				56,
				Math.min(72, (width - 40) / Math.max(1, model.cards.length) - 10),
			);
			const total = model.cards.length * (cardSize + 10) - 10;
			model.cards.forEach((card, index) => {
				const cx = (width - total) / 2 + index * (cardSize + 10) + cardSize / 2;
				const cy = trayTop + cardSize / 2;
				this.homes.set(card.id, { x: cx, y: cy });
				const face = this.add.graphics();
				face
					.fillStyle(0xffffff)
					.fillRoundedRect(
						-cardSize / 2,
						-cardSize / 2,
						cardSize,
						cardSize,
						14,
					);
				face
					.lineStyle(3, PURPLE, 0.85)
					.strokeRoundedRect(
						-cardSize / 2,
						-cardSize / 2,
						cardSize,
						cardSize,
						14,
					);
				const glyph = this.label(card.text, 30).setOrigin(0.5);
				const container = this.add
					.container(cx, cy, [face, glyph])
					.setSize(cardSize, cardSize);
				container.setInteractive({ draggable: true, useHandCursor: true });
				container.on("dragstart", () =>
					container.setData("dragged", true).setDepth(10),
				);
				container.on(
					"drag",
					(_p: Phaser.Input.Pointer, dx: number, dy: number) =>
						container.setPosition(dx, dy),
				);
				container.on("dragend", (pointer: Phaser.Input.Pointer) => {
					const gap = [...this.gapRects].find(([, rect]) =>
						rect.contains(pointer.x, pointer.y),
					)?.[0];
					if (gap)
						bridge.emit({ type: "place", card: card.id, gap, via: "drag" });
					else bridge.emit({ type: "drag_cancelled", id: card.id });
					this.sync(this.model);
				});
				container.on("pointerup", () => {
					if (container.getData("dragged")) {
						container.setData("dragged", false);
						return;
					}
					bridge.emit({ type: "select", id: card.id });
				});
				this.cardObjects.set(card.id, container);
				layer.add(container);
			});
			this.drawn = model.revision;
		}

		private sync(model: PunctuationSceneModel | null): void {
			if (!model) return;
			const placedCards = new Set(Object.values(model.placements));
			const textOf = new Map(model.cards.map((card) => [card.id, card.text]));
			for (const [gap, mark] of this.gapMarks)
				mark.setText(textOf.get(model.placements[gap] ?? "") ?? "");
			const duration = model.reducedMotion ? 0 : 140;
			for (const [id, card] of this.cardObjects) {
				const home = this.homes.get(id);
				if (!home) continue;
				card.setAlpha(placedCards.has(id) ? 0.35 : 1);
				const scale = model.selected === id ? 1.1 : 1;
				if (duration === 0) card.setPosition(home.x, home.y).setScale(scale);
				else
					this.tweens.add({
						targets: card,
						x: home.x,
						y: home.y,
						scale,
						duration,
					});
			}
		}
	};
}
