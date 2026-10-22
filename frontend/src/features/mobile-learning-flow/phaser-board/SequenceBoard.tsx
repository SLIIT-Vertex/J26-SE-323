import { useMemo } from "react";
import type { ConstructedResponse } from "../api/generated";
import type { BoardSceneArt, THEMES } from "./boardScene";
import { PhaserBoard } from "./PhaserBoard";
import { type BoardPicture, slotOrder } from "./types";

type Row = Record<string, unknown>;

/**
 * Build a name, question or reply by dragging word tiles into an ordered row of slots. The
 * response gets the tiles in slot order; it stays null until every slot is filled.
 */
export function SequenceBoard({
	chunks,
	chunkKey,
	chunkLabel = (row) => String(row.text_en ?? ""),
	slotCount,
	picture,
	theme,
	scene,
	instruction,
	build,
	onResponse,
}: {
	chunks: Row[];
	chunkKey: string;
	chunkLabel?(row: Row): string;
	slotCount?: number;
	/** What is being named, shown above the slots. */
	picture?: BoardPicture;
	theme?: keyof typeof THEMES;
	scene?: BoardSceneArt;
	instruction: string;
	build(
		ordered: string[],
		allTokens: string[],
		trace: string[],
	): ConstructedResponse;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const cards = useMemo(
		() =>
			chunks.map((row) => ({
				id: String(row[chunkKey]),
				label: chunkLabel(row),
			})),
		[chunks, chunkKey, chunkLabel],
	);
	const count = slotCount ?? cards.length;
	const slots = useMemo(
		() =>
			Array.from({ length: count }, (_, index) => ({
				id: `slot-${index + 1}`,
				label: `${index + 1}`,
			})),
		[count],
	);
	const tokens = useMemo(() => cards.map((card) => card.id), [cards]);
	return (
		<PhaserBoard
			layout="slots"
			theme={theme}
			scene={scene}
			background={picture}
			cards={cards}
			targets={slots}
			instruction={instruction}
			onChange={(state) => {
				const ordered = slotOrder(state.links, slots);
				const full = ordered.every((token) => token !== null);
				onResponse(
					full ? build(ordered as string[], tokens, state.trace) : null,
				);
			}}
		/>
	);
}
