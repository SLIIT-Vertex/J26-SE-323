import { useEffect, useMemo, useRef, useState } from "react";
import {
	type BoardBridge,
	type BoardSceneArt,
	type BoardSceneConfig,
	createBoardScene,
	measure,
	THEMES,
	WIDTH,
} from "./boardScene";
import {
	type BoardCard,
	type BoardLayout,
	type BoardPicture,
	type BoardState,
	type BoardTarget,
	EMPTY_BOARD,
	placeCard,
	removeCard,
} from "./types";
import "./phaser-board.css";

/**
 * The English games' play surface: a Phaser canvas where children drag word cards onto
 * pictures, baskets, slots or markers, or tap a card and then its place. Touch, mouse and pen all
 * drag. A visually hidden list of buttons mirrors the board for screen readers and keyboards, and
 * is shown instead of the canvas if WebGL/canvas is unavailable.
 */
export function PhaserBoard({
	layout,
	cards,
	targets,
	instruction,
	onChange,
	theme = "meadow",
	background,
	scene,
	reducedMotion = false,
}: {
	layout: BoardLayout;
	cards: BoardCard[];
	targets: BoardTarget[];
	instruction: string;
	onChange(state: BoardState): void;
	theme?: keyof typeof THEMES;
	background?: BoardPicture;
	/** The illustrated banner where a guide speaks the instruction. */
	scene?: BoardSceneArt;
	reducedMotion?: boolean;
}) {
	const host = useRef<HTMLDivElement>(null);
	const mirror = useRef<HTMLDivElement>(null);
	const engine = useRef<import("phaser").Game | null>(null);
	const [state, setState] = useState<BoardState>(EMPTY_BOARD);
	const latest = useRef(state);
	const marks = useRef<ReadonlySet<string>>(new Set());
	const [selected, setSelected] = useState<string | null>(null);
	const [failed, setFailed] = useState(false);
	const changed = useRef(onChange);
	changed.current = onChange;
	const capacity = useMemo(
		() => new Map(targets.map((target) => [target.id, target.capacity ?? 1])),
		[targets],
	);
	const config: BoardSceneConfig = useMemo(
		() => ({
			layout,
			cards,
			targets,
			theme: THEMES[theme],
			background,
			reducedMotion,
			scene,
			instruction,
		}),
		[
			layout,
			cards,
			targets,
			theme,
			background,
			reducedMotion,
			scene,
			instruction,
		],
	);
	const key = JSON.stringify([
		layout,
		cards,
		targets,
		theme,
		background,
		scene,
		instruction,
	]);
	const height = useMemo(() => measure(config).height, [config]);

	const commit = (next: BoardState) => {
		latest.current = next;
		setState(next);
		setSelected(null);
		changed.current(next);
		engine.current?.events.emit("board-state");
	};
	const bridge = useRef<BoardBridge>(null as unknown as BoardBridge);
	bridge.current = {
		links: () => latest.current.links,
		marks: () => marks.current,
		place: (source, target, tap) => {
			const old = latest.current;
			const moved = old.links.some((link) => link.source === source);
			commit({
				...old,
				links: placeCard(old.links, source, target, capacity.get(target) ?? 1),
				trace: [
					...old.trace,
					`${moved ? "replace" : "place"}:${source}:${target}:${tap ? "tap" : "drag"}`,
				],
				usedTap: old.usedTap || tap,
			});
		},
		remove: (source, tap) => {
			const old = latest.current;
			commit({
				...old,
				links: removeCard(old.links, source),
				trace: [...old.trace, `remove:${source}:tray:${tap ? "tap" : "drag"}`],
				usedTap: old.usedTap || tap,
			});
		},
		invalid: () => {
			const old = latest.current;
			const next = { ...old, invalidDrops: old.invalidDrops + 1 };
			latest.current = next;
			setState(next);
			changed.current(next);
		},
		ready: () => {},
	};

	// biome-ignore lint/correctness/useExhaustiveDependencies: the key captures the board's content.
	useEffect(() => {
		const parent = host.current;
		if (!parent) return;
		let disposed = false;
		let game: import("phaser").Game | undefined;
		latest.current = EMPTY_BOARD;
		setState(EMPTY_BOARD);
		setFailed(false);
		void import("phaser")
			.then(({ default: Phaser }) => {
				if (disposed) return;
				const Scene = createBoardScene(Phaser, config, {
					links: () => bridge.current.links(),
					marks: () => bridge.current.marks(),
					place: (s, t, tap) => bridge.current.place(s, t, tap),
					remove: (s, tap) => bridge.current.remove(s, tap),
					invalid: () => bridge.current.invalid(),
					ready: () => {},
				});
				game = new Phaser.Game({
					type: Phaser.AUTO,
					parent,
					width: WIDTH,
					height,
					scene: Scene,
					transparent: false,
					scale: {
						mode: Phaser.Scale.FIT,
						autoCenter: Phaser.Scale.CENTER_HORIZONTALLY,
					},
					audio: { noAudio: true },
					banner: false,
					render: { antialias: true },
					input: { activePointers: 2 },
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
	}, [key, height, reducedMotion]);

	// The support frame tints the answer by marking the hidden list; the canvas follows it.
	useEffect(() => {
		const list = mirror.current;
		if (!list) return;
		const read = () => {
			const next = new Set(
				[
					...list.querySelectorAll<HTMLElement>(
						".support-answer-mark[data-board-id]",
					),
				].map((node) => node.dataset.boardId ?? ""),
			);
			const before = [...marks.current].join();
			marks.current = next;
			if ([...next].join() !== before)
				engine.current?.events.emit("board-marks");
		};
		read();
		const observer = new MutationObserver(read);
		observer.observe(list, {
			subtree: true,
			attributes: true,
			attributeFilter: ["class"],
		});
		return () => observer.disconnect();
	}, []);

	const placedIn = (target: string) =>
		state.links
			.filter((link) => link.target === target)
			.map((link) => cards.find((card) => card.id === link.source)?.label)
			.filter(Boolean)
			.join(" · ");

	return (
		<section className="phaser-board" data-layout={layout}>
			<p
				className={
					scene
						? "phaser-board-instruction is-spoken"
						: "phaser-board-instruction"
				}
			>
				{instruction}
			</p>
			{!failed && (
				<div
					className="phaser-board-canvas"
					ref={host}
					style={{ aspectRatio: `${WIDTH} / ${height}` }}
					aria-hidden="true"
				/>
			)}
			<div className="phaser-board-bar">
				<p role="status">
					{state.links.length}/{cards.length} placed
				</p>
				{state.links.length > 0 && (
					<button
						type="button"
						className="phaser-board-reset"
						onClick={() =>
							commit({
								...latest.current,
								links: [],
								trace: [...latest.current.trace, "replace:reset"],
							})
						}
					>
						↺ Start again
					</button>
				)}
			</div>
			<div
				className={
					failed ? "phaser-board-mirror is-visible" : "phaser-board-mirror"
				}
				ref={mirror}
			>
				<p>
					{selected
						? "Now choose its place."
						: "Choose a card, then its place."}
				</p>
				<div className="phaser-board-mirror-cards">
					{cards.map((card) => (
						<button
							type="button"
							key={card.id}
							data-board-id={card.id}
							aria-pressed={selected === card.id}
							onClick={() => setSelected(selected === card.id ? null : card.id)}
						>
							{card.label}
						</button>
					))}
				</div>
				<div className="phaser-board-mirror-targets">
					{targets.map((target, index) => (
						<button
							type="button"
							key={target.id}
							data-board-id={target.id}
							disabled={!selected}
							onClick={() =>
								selected && bridge.current.place(selected, target.id, true)
							}
						>
							{target.picture?.emoji && (
								<span aria-hidden="true">{target.picture.emoji} </span>
							)}
							{target.label ?? target.marker ?? `Place ${index + 1}`}
							<small> {placedIn(target.id) || "empty"}</small>
						</button>
					))}
				</div>
			</div>
		</section>
	);
}
