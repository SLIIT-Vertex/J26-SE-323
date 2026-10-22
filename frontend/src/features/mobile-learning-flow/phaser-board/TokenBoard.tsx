import { useMemo } from "react";
import type { ConstructedResponse } from "../api/generated";
import type { BoardSceneArt, THEMES } from "./boardScene";
import { PhaserBoard } from "./PhaserBoard";
import type {
	BoardLayout,
	BoardLink,
	BoardPicture,
	BoardTarget,
} from "./types";

type Row = Record<string, unknown>;

/**
 * The English games' boards all share one shape: rows of word cards keyed by an opaque token,
 * rows of targets keyed by another, and a response builder that turns links into the game's own
 * constructed response. This adapter lets each game declare only that.
 */
export function TokenBoard({
	sources,
	sourceKey,
	sourceLabel = (row) => String(row.text_en ?? ""),
	sourcePicture,
	targets,
	targetKey,
	target,
	layout = "grid",
	theme,
	background,
	scene,
	instruction,
	build,
	complete,
	onResponse,
}: {
	sources: Row[];
	sourceKey: string;
	sourceLabel?(row: Row): string;
	/** A small picture on each word card, when the card shows a thing. */
	sourcePicture?(row: Row): BoardPicture | undefined;
	targets: Row[];
	targetKey: string;
	/** How one target row looks: a picture, a label, a capacity. */
	target(row: Row, index: number): Omit<BoardTarget, "id">;
	layout?: BoardLayout;
	theme?: keyof typeof THEMES;
	scene?: BoardSceneArt;
	background?: BoardPicture;
	instruction: string;
	build(
		links: BoardLink[],
		sourceTokens: string[],
		trace: string[],
	): ConstructedResponse;
	/** When the board counts as answered. By default, when every card has a place. */
	complete?(links: BoardLink[], cardCount: number): boolean;
	/** Null until the board is complete, so a game never submits a half-made answer. */
	onResponse(response: ConstructedResponse | null): void;
}) {
	const cards = useMemo(
		() =>
			sources.map((row) => ({
				id: String(row[sourceKey]),
				label: sourceLabel(row),
				picture: sourcePicture?.(row),
			})),
		[sources, sourceKey, sourceLabel, sourcePicture],
	);
	const places = useMemo(
		() =>
			targets.map((row, index) => ({
				id: String(row[targetKey]),
				...target(row, index),
			})),
		[targets, targetKey, target],
	);
	const tokens = useMemo(() => cards.map((card) => card.id), [cards]);
	return (
		<PhaserBoard
			layout={layout}
			theme={theme}
			scene={scene}
			background={background}
			cards={cards}
			targets={places}
			instruction={instruction}
			onChange={(state) => {
				const done = complete
					? complete(state.links, tokens.length)
					: state.links.length === tokens.length;
				onResponse(done ? build(state.links, tokens, state.trace) : null);
			}}
		/>
	);
}
