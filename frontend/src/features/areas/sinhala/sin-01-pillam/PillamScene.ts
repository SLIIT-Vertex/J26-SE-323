import type Phaser from "phaser";
import type { SceneBridge } from "../../../gamification/phaser/bridge/GameEventBridge";

/** What React asks the scene to draw. React owns the answer; the scene mirrors it. */
export type PillamSceneModel = {
	revision: string;
	chapter: string;
	mode: "match" | "build";
	cards: Array<{
		id: string;
		text: string;
		shape?: "kon" | "vak" | "aeda";
		label?: string;
	}>;
	docks: Array<{ id: string; text: string }>;
	base?: { id: string; text: string };
	placements: Record<string, string>;
	ordered: string[];
	selected: string | null;
	preview: string | null;
	emphasis: string | null;
	reducedMotion: boolean;
};
export type PillamSceneCommand = { type: "model"; model: PillamSceneModel };
export type PillamSceneEvent =
	| { type: "select"; id: string }
	| { type: "place"; source: string; destination: string; via: "drag" | "tap" }
	| { type: "toggle"; id: string; via: "drag" | "tap" }
	| { type: "drag_cancelled"; id: string };

export const SINHALA_FONT = '"Noto Sans Sinhala", "Iskoola Pota", sans-serif';
const INK = "#3b2a63";
const PURPLE = 0x6d4bb3;
const CREAM = 0xfff8ec;
const CARD = 0xffffff;
const MIN_TARGET = 56; // CSS px; the RESIZE scale keeps one game px = one CSS px.

type Zone = { id: string; rect: Phaser.Geom.Rectangle };

/** A scene class bound to one bridge. Every object is rebuilt when the revision changes. */
export function createPillamScene(
	PhaserRuntime: typeof Phaser,
	bridge: SceneBridge<PillamSceneCommand, PillamSceneEvent>,
): Phaser.Types.Scenes.SceneType {
	return class PillamScene extends PhaserRuntime.Scene {
		private model: PillamSceneModel | null = null;
		private drawn: string | null = null;
		private layer: Phaser.GameObjects.Container | null = null;
		private zones: Zone[] = [];
		private homes = new Map<string, { x: number; y: number }>();
		private cardObjects = new Map<string, Phaser.GameObjects.Container>();
		private unsubscribe: (() => void) | null = null;

		constructor() {
			super("pillam-scene");
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
			this.cardObjects.clear();
			this.homes.clear();
			this.zones = [];
		}

		private relayout(): void {
			this.drawn = null;
			this.render();
		}

		private render(): void {
			const model = this.model;
			if (!model) return;
			// A new revision is a new item: neutral state, nothing carried over.
			if (this.drawn !== model.revision) this.rebuild(model);
			else this.position(model, true);
		}

		private rebuild(model: PillamSceneModel): void {
			this.tweens.killAll();
			this.layer?.destroy(true);
			this.cardObjects.clear();
			this.homes.clear();
			this.zones = [];
			const { width, height } = this.scale;
			const layer = this.add.container(0, 0);
			this.layer = layer;
			this.drawBackdrop(layer, model.chapter, width, height);
			const top = Math.round(height * 0.42);
			if (model.mode === "match") this.drawDocks(layer, model, width, top);
			else this.drawWorkbench(layer, model, width, top);
			this.drawTray(layer, model, width, height, top);
			this.drawn = model.revision;
			this.position(model, false);
		}

		private drawBackdrop(
			layer: Phaser.GameObjects.Container,
			chapter: string,
			w: number,
			h: number,
		) {
			const g = this.add.graphics();
			g.fillStyle(CREAM).fillRoundedRect(0, 0, w, h, 20);
			if (chapter === "pillam_friends") {
				// Rails and a small bridge for the matching chapter.
				g.lineStyle(4, 0xc9b6ea).lineBetween(12, h * 0.45, w - 12, h * 0.45);
				g.lineBetween(12, h * 0.45 + 10, w - 12, h * 0.45 + 10);
				for (let x = 24; x < w - 12; x += 28)
					g.lineBetween(x, h * 0.45 - 4, x, h * 0.45 + 14);
			} else if (chapter === "akshara_workshop") {
				g.fillStyle(0xf1e4ff).fillRoundedRect(
					10,
					h * 0.08,
					w - 20,
					h * 0.32,
					18,
				);
				g.fillStyle(0xd8c3f5).fillRect(24, h * 0.4, w - 48, 8);
			} else {
				g.fillStyle(0xe3f4dc);
				for (const [x, r] of [
					[0.12, 22],
					[0.88, 26],
					[0.5, 18],
				] as const)
					g.fillCircle(w * x, h * 0.94, r);
				g.fillStyle(0xf1e4ff).fillRoundedRect(
					10,
					h * 0.08,
					w - 20,
					h * 0.32,
					18,
				);
			}
			layer.add(g);
		}

		private text(value: string, size: number, color = INK) {
			// Padding keeps above/below Sinhala marks inside the measured box.
			return this.add
				.text(0, 0, value, {
					fontFamily: SINHALA_FONT,
					fontSize: `${size}px`,
					color,
					align: "center",
					padding: {
						top: Math.ceil(size * 0.35),
						bottom: Math.ceil(size * 0.45),
						x: 4,
					},
				})
				.setOrigin(0.5);
		}

		private drawDocks(
			layer: Phaser.GameObjects.Container,
			model: PillamSceneModel,
			w: number,
			top: number,
		) {
			const count = Math.max(1, model.docks.length);
			const gap = 10;
			const dockW = Math.max(
				MIN_TARGET,
				Math.min(150, (w - 24 - gap * (count - 1)) / count),
			);
			const dockH = Math.max(MIN_TARGET, top * 0.55);
			const startX = (w - (dockW * count + gap * (count - 1))) / 2;
			model.docks.forEach((dock, index) => {
				const x = startX + index * (dockW + gap);
				const y = top * 0.18;
				const frame = this.add.graphics();
				frame.fillStyle(0xffffff).fillRoundedRect(x, y, dockW, dockH, 14);
				frame
					.lineStyle(3, PURPLE, 0.55)
					.strokeRoundedRect(x, y, dockW, dockH, 14);
				const label = this.text(
					dock.text,
					dockW < 90 ? 15 : 17,
				).setWordWrapWidth(dockW - 10);
				// A single long name has no space to wrap at: shrink it to fit, never clip a mark.
				const fit = Math.min(
					1,
					(dockW - 10) / label.width,
					(dockH * 0.55) / label.height,
				);
				label
					.setScale(fit)
					.setPosition(x + dockW / 2, y + (label.height * fit) / 2 + 6);
				const zone = this.add
					.zone(x + dockW / 2, y + dockH / 2, dockW, dockH)
					.setInteractive();
				zone.on("pointerup", () => {
					if (this.model?.selected)
						bridge.emit({
							type: "place",
							source: this.model.selected,
							destination: dock.id,
							via: "tap",
						});
				});
				this.zones.push({
					id: dock.id,
					rect: new PhaserRuntime.Geom.Rectangle(x, y, dockW, dockH),
				});
				layer.add([frame, label, zone]);
			});
		}

		private drawWorkbench(
			layer: Phaser.GameObjects.Container,
			model: PillamSceneModel,
			w: number,
			top: number,
		) {
			const size = Math.min(110, top * 0.6);
			const x = w / 2 - size / 2;
			const y = top * 0.16;
			const bench = this.add.graphics();
			bench.fillStyle(0xffffff).fillRoundedRect(x - 30, y, size + 60, size, 18);
			bench
				.lineStyle(3, PURPLE, 0.6)
				.strokeRoundedRect(x - 30, y, size + 60, size, 18);
			const zone = this.add
				.zone(w / 2, y + size / 2, size + 60, size)
				.setInteractive();
			zone.on("pointerup", () => {
				if (this.model?.selected)
					bridge.emit({ type: "toggle", id: this.model.selected, via: "tap" });
			});
			this.zones.push({
				id: "workbench",
				rect: new PhaserRuntime.Geom.Rectangle(x - 30, y, size + 60, size),
			});
			const shown = this.text(
				model.preview ?? model.base?.text ?? "",
				Math.round(size * 0.5),
			).setPosition(w / 2, y + size / 2);
			shown.setName("preview");
			layer.add([bench, zone, shown]);
			const papili = model.cards.find(
				(card) => card.id === model.ordered[0],
			)?.shape;
			if (papili)
				layer.add(this.papiliShape(papili, w / 2, y + size * 0.86, 0.9));
		}

		private papiliShape(
			shape: "kon" | "vak" | "aeda",
			x: number,
			y: number,
			scale: number,
		) {
			const g = this.add.graphics({ x, y });
			g.lineStyle(4 * scale, INK_NUMBER);
			if (shape === "kon") {
				g.lineBetween(-8 * scale, -8 * scale, -8 * scale, 6 * scale);
				g.lineBetween(-8 * scale, 6 * scale, 10 * scale, 6 * scale);
				g.lineBetween(10 * scale, 6 * scale, 10 * scale, -4 * scale);
			} else if (shape === "vak") {
				g.beginPath();
				g.arc(0, 0, 9 * scale, 0, Math.PI, false);
				g.strokePath();
			} else {
				g.beginPath();
				g.arc(0, -4 * scale, 7 * scale, Math.PI, Math.PI * 2.4, false);
				g.strokePath();
				g.lineBetween(-7 * scale, -4 * scale, 6 * scale, 10 * scale);
			}
			return g;
		}

		private drawTray(
			layer: Phaser.GameObjects.Container,
			model: PillamSceneModel,
			w: number,
			h: number,
			top: number,
		) {
			const count = Math.max(1, model.cards.length);
			const columns = Math.min(count, w < 360 ? 3 : 4);
			const gap = 12;
			const cardW = Math.max(
				MIN_TARGET,
				Math.min(96, (w - 24 - gap * (columns - 1)) / columns),
			);
			const cardH = Math.max(
				MIN_TARGET,
				Math.min(88, (h - top - 30) / Math.ceil(count / columns) - gap),
			);
			const startX = (w - (cardW * columns + gap * (columns - 1))) / 2;
			model.cards.forEach((card, index) => {
				const col = index % columns;
				const row = Math.floor(index / columns);
				const x = startX + col * (cardW + gap) + cardW / 2;
				const y = top + 26 + row * (cardH + gap) + cardH / 2;
				this.homes.set(card.id, { x, y });
				const face = this.add.graphics();
				face
					.fillStyle(CARD)
					.fillRoundedRect(-cardW / 2, -cardH / 2, cardW, cardH, 14);
				face
					.lineStyle(3, PURPLE, 0.8)
					.strokeRoundedRect(-cardW / 2, -cardH / 2, cardW, cardH, 14);
				const parts: Phaser.GameObjects.GameObject[] = [face];
				if (card.shape) {
					parts.push(this.papiliShape(card.shape, 0, -10, 1));
					if (card.label) {
						const caption = this.text(card.label, 12).setWordWrapWidth(
							cardW - 8,
						);
						const fit = Math.min(
							1,
							(cardW - 8) / caption.width,
							(cardH * 0.4) / caption.height,
						);
						parts.push(
							caption
								.setScale(fit)
								.setPosition(0, cardH / 2 - (caption.height * fit) / 2 - 2),
						);
					}
				} else {
					parts.push(
						this.text(card.text, Math.round(Math.min(cardW, cardH) * 0.42)),
					);
				}
				const container = this.add.container(x, y, parts).setSize(cardW, cardH);
				container.setInteractive({ draggable: true, useHandCursor: true });
				container.setData("dragged", false);
				container.on("dragstart", () => {
					container.setData("dragged", true);
					container.setDepth(10);
				});
				container.on(
					"drag",
					(_p: Phaser.Input.Pointer, dx: number, dy: number) =>
						container.setPosition(dx, dy),
				);
				container.on("dragend", (pointer: Phaser.Input.Pointer) =>
					this.drop(card.id, pointer),
				);
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
		}

		private drop(id: string, pointer: Phaser.Input.Pointer) {
			const zone = this.zones.find((row) =>
				row.rect.contains(pointer.x, pointer.y),
			);
			const model = this.model;
			if (!zone || !model) {
				// Cancelled or missed: back to its place, no penalty.
				bridge.emit({ type: "drag_cancelled", id });
				this.position(model, true);
				return;
			}
			if (model.mode === "match")
				bridge.emit({
					type: "place",
					source: id,
					destination: zone.id,
					via: "drag",
				});
			else bridge.emit({ type: "toggle", id, via: "drag" });
		}

		private position(model: PillamSceneModel | null, animate: boolean) {
			if (!model) return;
			const duration = animate && !model.reducedMotion ? 160 : 0;
			const perDock = new Map<string, number>();
			for (const [id, card] of this.cardObjects) {
				const home = this.homes.get(id);
				if (!home) continue;
				let target = home;
				let scale = model.selected === id ? 1.08 : 1;
				const dock = model.placements[id];
				const zone = dock
					? this.zones.find((row) => row.id === dock)
					: undefined;
				if (zone) {
					const n = perDock.get(dock) ?? 0;
					perDock.set(dock, n + 1);
					target = {
						x: zone.rect.centerX + (n % 2 ? 16 : -16) * Math.min(n, 1),
						y: zone.rect.bottom - 34 - n * 6,
					};
					scale = 0.72;
				} else if (model.ordered.includes(id)) {
					scale = 0.8;
					card.setAlpha(0.45);
				} else {
					card.setAlpha(1);
				}
				if (model.emphasis === "enlarge_current_sign" && model.mode === "match")
					scale *= 1.18;
				card.setDepth(model.selected === id ? 5 : 1);
				if (duration === 0)
					card.setPosition(target.x, target.y).setScale(scale);
				else
					this.tweens.add({
						targets: card,
						x: target.x,
						y: target.y,
						scale,
						duration,
						ease: "Sine.easeOut",
					});
			}
			const preview = this.layer?.getByName(
				"preview",
			) as Phaser.GameObjects.Text | null;
			if (preview && model.mode === "build")
				preview.setText(model.preview ?? model.base?.text ?? "");
		}
	};
}

const INK_NUMBER = 0x3b2a63;
