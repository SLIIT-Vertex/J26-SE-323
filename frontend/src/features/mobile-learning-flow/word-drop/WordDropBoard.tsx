import { createContext, useContext, useEffect, useRef, useState } from "react";
import "./word-drop.css";
import { PlantPicture } from "./PlantPicture";

export const WordDropMotionContext = createContext(false);

export type WordCard = { id: string; label: string; emoji?: string };
export type WordTarget = {
	id: string;
	label: string;
	emoji?: string;
	visual?: string;
	count?: number;
	hint?: string;
};
export type WordLink = { source: string; target: string; sequence: number };
export type WordDropState = {
	links: WordLink[];
	trace: string[];
	usedTap: boolean;
	invalidDrops: number;
};
export function placeWord(
	links: WordLink[],
	source: string,
	target: string,
	single: boolean,
) {
	return [
		...links.filter(
			(link) => link.source !== source && (!single || link.target !== target),
		),
		{ source, target, sequence: 0 },
	].map((link, index) => ({ ...link, sequence: index + 1 }));
}

/** Pointer dragging and keyboard/tap controls share the same state and opaque tokens. */
export function WordDropBoard({
	cards,
	targets,
	onChange,
	instruction,
	single = true,
	theme = "garden",
	diagram,
	reducedMotion,
}: {
	cards: WordCard[];
	targets: WordTarget[];
	onChange(state: WordDropState): void;
	instruction: string;
	single?: boolean;
	theme?: "garden" | "market";
	diagram?: boolean | "tree";
	reducedMotion?: boolean;
}) {
	const motionSetting = useContext(WordDropMotionContext);
	const calm = reducedMotion ?? motionSetting;
	const host = useRef<HTMLDivElement>(null);
	const engine = useRef<import("phaser").Game | null>(null);
	const current = useRef({ cards, targets, onChange, single });
	current.current = { cards, targets, onChange, single };
	const [state, setState] = useState<WordDropState>({
		links: [],
		trace: [],
		usedTap: false,
		invalidDrops: 0,
	});
	const latest = useRef(state);
	latest.current = state;
	const [selected, setSelected] = useState<string | null>(null);
	const [ready, setReady] = useState(false);
	const [failed, setFailed] = useState(false);
	const cols = cards.length > 4 ? 3 : 2;
	const top = Math.ceil(cards.length / cols) * 92 + 24;
	const height =
		top + (diagram ? 480 : Math.ceil(targets.length / 2) * 168) + 20;
	const key = JSON.stringify({ cards, targets, diagram, height, theme });
	const commit = useRef<
		(source: string, target: string | null, tap: boolean) => void
	>(() => {});
	commit.current = (source, target, tap) => {
		const old = latest.current;
		const replaced = old.links.some(
			(link) => link.source === source || (single && link.target === target),
		);
		const links = target
			? placeWord(old.links, source, target, single)
			: old.links
					.filter((link) => link.source !== source)
					.map((link, index) => ({ ...link, sequence: index + 1 }));
		const next = {
			...old,
			links,
			trace: [
				...old.trace,
				`${target ? (replaced ? "replace" : "place") : "remove"}:${source}:${target ?? "tray"}:${tap ? "tap" : "drag"}`,
			],
			usedTap: old.usedTap || tap,
		};
		latest.current = next;
		setState(next);
		setSelected(null);
		current.current.onChange(next);
	};
	useEffect(() => {
		const parent = host.current;
		if (!parent) return;
		const config = JSON.parse(key) as {
			cards: WordCard[];
			targets: WordTarget[];
			diagram?: boolean | "tree";
			height: number;
			theme: string;
		};
		const { diagram, height, theme } = config;
		const cols = config.cards.length > 4 ? 3 : 2;
		const top = Math.ceil(config.cards.length / cols) * 92 + 24;
		let disposed = false;
		let game: import("phaser").Game | undefined;
		setReady(false);
		setFailed(false);
		void import("phaser")
			.then(({ default: Phaser }) => {
				if (disposed) return;
				class DropScene extends Phaser.Scene {
					create() {
						const { cards: words, targets: bins } = config;
						this.cameras.main.setBackgroundColor(
							theme === "market" ? "#fff3da" : "#eaf7eb",
						);
						const textStyle = {
							fontFamily: 'Nunito, "Apple Color Emoji", sans-serif',
							fontSize: "23px",
							fontStyle: "bold",
							color: "#214b4b",
							align: "center" as const,
							wordWrap: { width: 194 },
						};
						const positions = new Map<
							string,
							{ x: number; y: number; w: number; h: number }
						>();
						const home = new Map<string, { x: number; y: number }>();
						const pieces = new Map<
							string,
							import("phaser").GameObjects.Container
						>();
						const outlines = new Map<
							string,
							import("phaser").GameObjects.Rectangle
						>();
						const labels = new Map<string, import("phaser").GameObjects.Text>();
						if (diagram) drawPlant(this, top, diagram === "tree");
						const diagramYs = new Map(
							[...bins]
								.sort(
									(a, b) =>
										plantPoint(a.visual ?? "", top).y -
										plantPoint(b.visual ?? "", top).y,
								)
								.map((bin, index) => [
									bin.id,
									top + 54 + (index * 360) / Math.max(1, bins.length - 1),
								]),
						);
						bins.forEach((bin, index) => {
							const point = diagram ? plantPoint(bin.visual ?? "", top) : null;
							const x = point ? 362 : 122 + (index % 2) * 236;
							const y = point
								? (diagramYs.get(bin.id) ?? point.y)
								: top + Math.floor(index / 2) * 168 + 78;
							const w = point ? 204 : 220,
								h = point ? 66 : 152;
							positions.set(bin.id, { x, y, w, h });
							if (point)
								this.add
									.graphics()
									.lineStyle(3, 0x9c81bd)
									.lineBetween(point.x, point.y, x - w / 2, y)
									.fillStyle(0x7c4bad)
									.fillCircle(point.x, point.y, 5);
							const box = this.add
								.rectangle(x, y, w, h, 0xfffdf7)
								.setStrokeStyle(3, 0xc5b0d8)
								.setInteractive({ dropZone: true });
							box.setData("target", bin.id);
							outlines.set(bin.id, box);
							if (
								theme === "market" &&
								!bin.label.startsWith("Picture") &&
								!bin.label.startsWith("Word")
							) {
								const weave = this.add.graphics();
								weave
									.fillStyle(0xf5d599)
									.fillRoundedRect(x - 102, y - 12, 204, 78, 14);
								weave.lineStyle(2, 0xd4a35c);
								for (let dx = -80; dx <= 80; dx += 20)
									weave.lineBetween(x + dx, y - 10, x + dx, y + 64);
								for (let dy = 6; dy <= 60; dy += 18)
									weave.lineBetween(x - 100, y + dy, x + 100, y + dy);
							}
							if (!point) {
								if (bin.visual)
									drawPart(this, bin.visual, x, y - 36, bin.count ?? 1);
								else
									this.add
										.text(x, y - 40, bin.emoji ?? "🧺", {
											fontFamily: '"Apple Color Emoji", sans-serif',
											fontSize: "42px",
										})
										.setOrigin(0.5);
								this.add
									.text(x, y + 7, bin.label, { ...textStyle, fontSize: "22px" })
									.setOrigin(0.5);
							}
							const label = this.add
								.text(x, point ? y : y + 48, bin.hint ?? "Drop a word", {
									...textStyle,
									fontSize: point ? "21px" : "18px",
									color: "#75618b",
									wordWrap: { width: w - 16 },
								})
								.setOrigin(0.5);
							labels.set(bin.id, label);
						});
						words.forEach((word, index) => {
							const w = 480 / cols - 14,
								x = ((index % cols) + 0.5) * (480 / cols),
								y = Math.floor(index / cols) * 92 + 46;
							home.set(word.id, { x, y });
							const bg = this.add
								.rectangle(0, 0, w, 78, 0xffffff)
								.setStrokeStyle(3, 0x8c62b6);
							const label = this.add
								.text(
									0,
									0,
									`${word.emoji ? `${word.emoji} ` : ""}${word.label}`,
									{
										...textStyle,
										fontSize: cols === 3 ? "21px" : "23px",
										wordWrap: { width: w - 12 },
									},
								)
								.setOrigin(0.5);
							const piece = this.add
								.container(x, y, [bg, label])
								.setSize(w, 78)
								.setInteractive({ useHandCursor: true });
							piece.setData("source", word.id);
							this.input.setDraggable(piece);
							pieces.set(word.id, piece);
						});
						const repaint = () => {
							const links = latest.current.links;
							for (const [id, piece] of pieces) {
								const assigned = links.some((link) => link.source === id);
								piece.setAlpha(assigned ? 0.52 : 1);
								const origin = home.get(id);
								if (origin) piece.setPosition(origin.x, origin.y);
								piece.setDepth(2);
							}
							for (const bin of bins) {
								const assigned = links
									.filter((link) => link.target === bin.id)
									.map(
										(link) =>
											words.find((word) => word.id === link.source)?.label,
									)
									.filter(Boolean);
								labels
									.get(bin.id)
									?.setText(
										assigned.length
											? assigned.join(" · ")
											: (bin.hint ?? "Drop a word"),
									);
								outlines
									.get(bin.id)
									?.setStrokeStyle(3, assigned.length ? 0x8c62b6 : 0xc5b0d8);
							}
						};
						this.input.on(
							"dragstart",
							(
								_pointer: unknown,
								piece: import("phaser").GameObjects.Container,
							) => {
								piece.setDepth(10).setAlpha(1);
							},
						);
						this.input.on(
							"drag",
							(
								_pointer: unknown,
								piece: import("phaser").GameObjects.Container,
								x: number,
								y: number,
							) => {
								piece.setPosition(x, y);
							},
						);
						this.input.on(
							"dragenter",
							(
								_p: unknown,
								_c: unknown,
								zone: import("phaser").GameObjects.Rectangle,
							) => zone.setFillStyle(0xeee3ff),
						);
						this.input.on(
							"dragleave",
							(
								_p: unknown,
								_c: unknown,
								zone: import("phaser").GameObjects.Rectangle,
							) => zone.setFillStyle(0xfffdf7),
						);
						this.input.on(
							"drop",
							(
								_pointer: unknown,
								piece: import("phaser").GameObjects.Container,
								zone: import("phaser").GameObjects.Rectangle,
							) => {
								zone.setFillStyle(0xfffdf7);
								commit.current(
									String(piece.getData("source")),
									String(zone.getData("target")),
									false,
								);
								const noMotion =
									calm ||
									window.matchMedia("(prefers-reduced-motion: reduce)").matches;
								if (!noMotion)
									this.tweens.add({
										targets: zone,
										alpha: { from: 0.6, to: 1 },
										duration: 180,
									});
							},
						);
						this.input.on(
							"dragend",
							(
								_pointer: unknown,
								_piece: import("phaser").GameObjects.Container,
								dropped: boolean,
							) => {
								if (!dropped) {
									const next = {
										...latest.current,
										invalidDrops: latest.current.invalidDrops + 1,
									};
									latest.current = next;
									setState(next);
									current.current.onChange(next);
								}
								repaint();
							},
						);
						this.game.events.on("word-state", repaint);
						this.events.once("shutdown", () =>
							this.game.events.off("word-state", repaint),
						);
						repaint();
						setReady(true);
					}
				}
				game = new Phaser.Game({
					type: Phaser.AUTO,
					parent,
					width: 480,
					height,
					scene: DropScene,
					scale: {
						mode: Phaser.Scale.FIT,
						autoCenter: Phaser.Scale.CENTER_BOTH,
					},
					audio: { noAudio: true },
					render: { antialias: true },
					fps: { target: 30 },
				});
				engine.current = game;
			})
			.catch(() => {
				if (!disposed) setFailed(true);
			});
		return () => {
			disposed = true;
			engine.current = null;
			game?.destroy(true);
		};
	}, [key, calm]);
	useEffect(() => {
		engine.current?.events.emit("word-state", state);
	}, [state]);
	return (
		<section className={`word-drop word-drop--${theme}`}>
			<p className="word-drop-instruction">{instruction}</p>
			<p className="word-drop-progress" role="status">
				{state.links.length}/{cards.length} words placed · Drag a card again to
				change its place.
			</p>
			{!failed && (
				<div
					className="word-drop-canvas"
					style={{
						aspectRatio: `480 / ${height}`,
						maxWidth: `min(480px, calc(72dvh * 480 / ${height}))`,
					}}
					ref={host}
					aria-hidden="true"
				/>
			)}
			<details className="word-drop-tap" open={!ready || failed || undefined}>
				<summary>Tap instead of dragging</summary>
				<p>
					{selected
						? "Now tap a picture or basket."
						: "Tap a word, then its picture or basket."}
				</p>
				<div className="chunk-rail plant-word-rail plant-form-rail">
					{cards.map((card) => (
						<button
							type="button"
							key={card.id}
							aria-pressed={selected === card.id}
							className={selected === card.id ? "selected" : ""}
							onClick={() => setSelected(card.id)}
						>
							{card.emoji && <span aria-hidden="true">{card.emoji} </span>}
							{card.label}
						</button>
					))}
				</div>
				<div className="word-drop-targets">
					{targets.map((target) => (
						<button
							type="button"
							className="food-target plant-target pair-slot"
							key={target.id}
							disabled={!selected}
							onClick={() =>
								selected && commit.current(selected, target.id, true)
							}
						>
							{target.visual ? (
								<PlantPicture visual={target.visual} count={target.count} />
							) : (
								<span className="word-drop-emoji" aria-hidden="true">
									{target.emoji ?? "🧺"}
								</span>
							)}
							<strong>{target.label}</strong>
							<span>
								{state.links
									.filter((link) => link.target === target.id)
									.map(
										(link) =>
											cards.find((card) => card.id === link.source)?.label,
									)
									.join(" · ") ||
									target.hint ||
									"Drop a word"}
							</span>
						</button>
					))}
				</div>
			</details>
			{state.links.length > 0 && (
				<button
					type="button"
					className="word-drop-reset"
					onClick={() => {
						const next = {
							...latest.current,
							links: [],
							trace: [...latest.current.trace, "replace:reset"],
						};
						latest.current = next;
						setState(next);
						current.current.onChange(next);
					}}
				>
					↺ Start again
				</button>
			)}
		</section>
	);
}

type Scene = import("phaser").Scene;
function drawPart(
	scene: Scene,
	visual: string,
	x: number,
	y: number,
	count: number,
) {
	const key = visual.replace(/^plant-/, "").replace(/-slot$/, "");
	const g = scene.add.graphics();
	for (let i = 0; i < count; i++) {
		const cx = x + (i - (count - 1) / 2) * 42;
		if (/root/.test(key)) {
			g.lineStyle(4, 0x9b683c).lineBetween(cx, y - 20, cx, y + 23);
			for (const side of [-1, 1])
				for (let j = 0; j < 3; j++)
					g.lineBetween(
						cx,
						y - 10 + j * 12,
						cx + side * (14 + j * 4),
						y + 10 + j * 8,
					);
		} else if (/stem|trunk|branch/.test(key)) {
			g.lineStyle(
				/stem/.test(key) ? 7 : 10,
				/stem/.test(key) ? 0x4d9048 : 0x976544,
			).lineBetween(cx, y + 24, cx, y - 24);
			if (/branch/.test(key))
				g.lineBetween(cx, y, cx + 18, y - 16).lineBetween(
					cx,
					y + 10,
					cx - 17,
					y - 5,
				);
		} else if (/petal/.test(key)) {
			g.fillStyle(0xf28db7).fillEllipse(cx, y, 21, 38);
		} else if (/leaf|leaves/.test(key)) {
			g.fillStyle(0x55984e).fillEllipse(cx, y, 24, 40);
			g.lineStyle(2, 0x286334).lineBetween(cx, y - 15, cx, y + 20);
		} else if (/bud/.test(key)) {
			g.lineStyle(3, 0x55984e).lineBetween(cx, y + 5, cx, y + 24);
			g.fillStyle(0xdb6496).fillEllipse(cx, y - 4, 22, 30);
			g.fillStyle(0x75a658).fillTriangle(
				cx - 12,
				y + 4,
				cx,
				y + 14,
				cx + 12,
				y + 4,
			);
		} else
			scene.add
				.text(
					cx,
					y,
					/bud/.test(key)
						? "🌷"
						: /flower/.test(key)
							? "🌸"
							: /fruit/.test(key)
								? "🥭"
								: "🍃",
					{
						fontFamily: '"Apple Color Emoji", sans-serif',
						fontSize: count > 1 ? "35px" : "47px",
					},
				)
				.setOrigin(0.5);
	}
}
function plantPoint(visual: string, top: number) {
	const key = visual.replace(/-slot$/, "");
	const positions: Record<string, { x: number; y: number }> = {
		roots: { x: 140, y: top + 418 },
		stem: { x: 140, y: top + 332 },
		trunk: { x: 140, y: top + 332 },
		branches: { x: 174, y: top + 272 },
		leaves: { x: 80, y: top + 220 },
		bud: { x: 170, y: top + 114 },
		flowers: { x: 110, y: top + 55 },
		petals: { x: 94, y: top + 45 },
		fruit: { x: 182, y: top + 184 },
		fruits: { x: 182, y: top + 184 },
	};
	return positions[key] ?? { x: 140, y: top + 55 };
}
function drawPlant(scene: Scene, top: number, tree: boolean) {
	const g = scene.add.graphics();
	g.fillStyle(0xd2b18c).fillRoundedRect(12, top + 375, 224, 92, 12);
	if (tree) g.fillStyle(0xa3c67b).fillCircle(140, top + 160, 100);
	g.lineStyle(tree ? 24 : 10, tree ? 0x976544 : 0x5d8e48).lineBetween(
		140,
		top + 374,
		140,
		top + 78,
	);
	g.lineStyle(6, tree ? 0x976544 : 0x5d8e48)
		.lineBetween(140, top + 290, 185, top + 250)
		.lineBetween(140, top + 240, 93, top + 218)
		.lineBetween(140, top + 185, 170, top + 114)
		.lineBetween(140, top + 130, 110, top + 55);
	g.lineStyle(5, 0x976544);
	for (const dx of [-50, -25, 0, 25, 50])
		g.lineBetween(140, top + 374, 140 + dx, top + 440);
	scene.add.text(80, top + 220, "🍃", { fontSize: "46px" }).setOrigin(0.5);
	scene.add.text(110, top + 55, "🌸", { fontSize: "56px" }).setOrigin(0.5);
	scene.add.text(170, top + 114, "🌷", { fontSize: "38px" }).setOrigin(0.5);
	scene.add.text(182, top + 184, "🥭", { fontSize: "42px" }).setOrigin(0.5);
}
