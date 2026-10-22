import type Phaser from "phaser";
import type { SceneBridge } from "../../../gamification/phaser/bridge/GameEventBridge";

export type RiddleSceneModel = {
	revision: string;
	chapter: string;
	cards: Array<{ id: string; text: string }>;
	trail: string[];
	chest: string | null;
	selected: string | null;
	reducedMotion: boolean;
};
export type RiddleSceneCommand = { type: "model"; model: RiddleSceneModel };
export type RiddleSceneEvent =
	| { type: "select"; id: string }
	| { type: "place"; id: string; via: "drag" | "tap" }
	| { type: "drag_cancelled"; id: string };

const FONT = '"Noto Sans Sinhala", "Iskoola Pota", sans-serif';
const INK = "#3b2a63";
const PURPLE = 0x6d4bb3;

/**
 * The clue trail and the chest. Every answer card is drawn the same way; the chest stays shut
 * whatever is placed in it. It opens only when React tells it the server's result, so the scene
 * can never signal which card is right.
 */
export function createRiddleScene(
	PhaserRuntime: typeof Phaser,
	bridge: SceneBridge<RiddleSceneCommand, RiddleSceneEvent>,
): Phaser.Types.Scenes.SceneType {
	return class RiddleScene extends PhaserRuntime.Scene {
		private model: RiddleSceneModel | null = null;
		private drawn: string | null = null;
		private layer: Phaser.GameObjects.Container | null = null;
		private chestRect: Phaser.Geom.Rectangle | null = null;
		private chestLabel: Phaser.GameObjects.Text | null = null;
		private trailLabel: Phaser.GameObjects.Text | null = null;
		private cards = new Map<string, Phaser.GameObjects.Container>();
		private homes = new Map<string, { x: number; y: number }>();
		private unsubscribe: (() => void) | null = null;

		constructor() {
			super("riddle-scene");
		}

		create(): void {
			this.input.dragDistanceThreshold = 8;
			this.unsubscribe = bridge.onCommand((command) => {
				this.model = command.model;
				if (this.drawn !== command.model.revision) this.rebuild(command.model);
				this.sync(command.model);
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
			this.cards.clear();
			this.homes.clear();
		}

		private relayout(): void {
			this.drawn = null;
			if (this.model) {
				this.rebuild(this.model);
				this.sync(this.model);
			}
		}

		private text(value: string, size: number) {
			return this.add
				.text(0, 0, value, {
					fontFamily: FONT,
					fontSize: `${size}px`,
					color: INK,
					align: "center",
					padding: {
						top: Math.ceil(size * 0.35),
						bottom: Math.ceil(size * 0.45),
						x: 4,
					},
				})
				.setOrigin(0.5);
		}

		private rebuild(model: RiddleSceneModel): void {
			this.tweens.killAll();
			this.layer?.destroy(true);
			this.cards.clear();
			this.homes.clear();
			const { width, height } = this.scale;
			const layer = this.add.container(0, 0);
			this.layer = layer;
			const g = this.add.graphics();
			g.fillStyle(0xfff8ec).fillRoundedRect(0, 0, width, height, 20);
			if (model.chapter === "clue_bridge") {
				g.lineStyle(5, 0xc9b6ea).lineBetween(
					16,
					height * 0.3,
					width - 16,
					height * 0.3,
				);
				for (let x = 24; x < width - 16; x += 34)
					g.lineBetween(x, height * 0.3, x + 17, height * 0.22);
			} else if (model.chapter === "word_secret_box") {
				g.fillStyle(0xe3f4dc)
					.fillCircle(width * 0.1, height * 0.95, 26)
					.fillCircle(width * 0.92, height * 0.94, 22);
			} else {
				g.fillStyle(0xf1e4ff);
				for (let x = 20; x < width - 20; x += 30)
					g.fillCircle(x, height * 0.3, 5);
			}
			// The chest: a code-built box with a slot.
			const chestW = Math.min(170, width * 0.5);
			const chestH = 92;
			const cx = width / 2 - chestW / 2;
			const cy = height * 0.04;
			g.fillStyle(0xb7895c).fillRoundedRect(
				cx,
				cy + 18,
				chestW,
				chestH - 18,
				12,
			);
			g.fillStyle(0x8a6240).fillRoundedRect(cx - 4, cy, chestW + 8, 30, 10);
			g.fillStyle(0xf4d06f).fillRect(width / 2 - 9, cy + 22, 18, 22);
			g.fillStyle(0xfff8ec).fillRoundedRect(
				cx + 14,
				cy + 50,
				chestW - 28,
				34,
				8,
			);
			this.chestRect = new PhaserRuntime.Geom.Rectangle(
				cx - 10,
				cy - 10,
				chestW + 20,
				chestH + 20,
			);
			const zone = this.add
				.zone(width / 2, cy + chestH / 2, chestW + 20, chestH + 20)
				.setInteractive();
			zone.on("pointerup", () => {
				if (this.model?.selected)
					bridge.emit({ type: "place", id: this.model.selected, via: "tap" });
			});
			this.chestLabel = this.text("", 17).setPosition(width / 2, cy + 67);
			this.trailLabel = this.text("", 13)
				.setPosition(width / 2, cy + chestH + 22)
				.setWordWrapWidth(width - 30);
			layer.add([g, zone, this.chestLabel, this.trailLabel]);
			// Equal answer cards: same size, colour and spacing.
			const columns = 2;
			const gap = 12;
			const cardW = Math.max(120, (width - 32 - gap) / columns);
			const cardH = 56;
			const top = Math.max(height * 0.42, cy + chestH + 48);
			model.cards.forEach((card, index) => {
				const x = 16 + (index % columns) * (cardW + gap) + cardW / 2;
				const y = top + Math.floor(index / columns) * (cardH + gap) + cardH / 2;
				this.homes.set(card.id, { x, y });
				const face = this.add.graphics();
				face
					.fillStyle(0xffffff)
					.fillRoundedRect(-cardW / 2, -cardH / 2, cardW, cardH, 14);
				face
					.lineStyle(3, PURPLE, 0.8)
					.strokeRoundedRect(-cardW / 2, -cardH / 2, cardW, cardH, 14);
				const label = this.text(card.text, 19);
				label.setScale(Math.min(1, (cardW - 12) / label.width));
				const container = this.add
					.container(x, y, [face, label])
					.setSize(cardW, cardH);
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
					if (this.chestRect?.contains(pointer.x, pointer.y))
						bridge.emit({ type: "place", id: card.id, via: "drag" });
					else bridge.emit({ type: "drag_cancelled", id: card.id });
					if (this.model) this.sync(this.model);
				});
				container.on("pointerup", () => {
					if (container.getData("dragged")) {
						container.setData("dragged", false);
						return;
					}
					bridge.emit({ type: "select", id: card.id });
				});
				this.cards.set(card.id, container);
				layer.add(container);
			});
			this.drawn = model.revision;
		}

		private sync(model: RiddleSceneModel): void {
			const textOf = new Map(model.cards.map((card) => [card.id, card.text]));
			this.chestLabel?.setText(
				model.chest ? (textOf.get(model.chest) ?? "") : "",
			);
			this.trailLabel?.setText(
				model.trail.length ? `ඉඟි ${model.trail.length}ක් තෝරා ඇත` : "",
			);
			const duration = model.reducedMotion ? 0 : 140;
			for (const [id, card] of this.cards) {
				const home = this.homes.get(id);
				if (!home) continue;
				// Same alpha for every unplaced card; only the child's own selection is marked.
				card.setAlpha(model.chest === id ? 0.35 : 1);
				const scale = model.selected === id ? 1.05 : 1;
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
