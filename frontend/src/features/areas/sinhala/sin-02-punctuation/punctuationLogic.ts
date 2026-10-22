import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type PunctuationGame = {
	schema_version: "sinhala-punctuation-item-v1";
	chapter: string;
	activity_id: string;
	response_kind:
		| "sinhala_punctuation_placement"
		| "sinhala_punctuation_span"
		| "sinhala_linebreak";
	subfamily: string;
	goal_si: string;
	context_si?: string;
	tokens: Array<{ text_si: string }>;
	boundaries: Array<{ boundary_id: string; after_token_index: number }>;
	mark_cards: Array<{
		token_id: string;
		display_si: string;
		accessible_label_si: string;
	}>;
	support_emphasis?: string;
	opening_demonstration?: {
		demonstration_id: string;
		goal_si: string;
		shown_si?: string | null;
		steps_si: string[];
		advance_label_si: string;
	};
};

export const PUNCTUATION_SCHEMA = "sinhala-punctuation-response-v1" as const;

export function isPunctuationGame(value: unknown): value is PunctuationGame {
	return (
		typeof value === "object" &&
		value !== null &&
		(value as { schema_version?: unknown }).schema_version ===
			"sinhala-punctuation-item-v1"
	);
}

/** boundary id → mark card id. A gap holds one mark; a card sits in one gap. */
export type Placements = Record<string, string>;

export function place(
	placements: Placements,
	boundary: string,
	card: string,
): Placements {
	const next: Placements = {};
	for (const [gap, held] of Object.entries(placements))
		if (held !== card && gap !== boundary) next[gap] = held;
	next[boundary] = card;
	return next;
}

export function removeAt(placements: Placements, boundary: string): Placements {
	const { [boundary]: _removed, ...rest } = placements;
	return rest;
}

/** Boundaries in reading order, so the earlier placed mark is the opening one. */
export function ordered(
	game: PunctuationGame,
	placements: Placements,
): Array<[string, string]> {
	const position = new Map(
		game.boundaries.map((b) => [b.boundary_id, b.after_token_index]),
	);
	return Object.entries(placements).sort(
		([left], [right]) => (position.get(left) ?? 0) - (position.get(right) ?? 0),
	);
}

export function isComplete(
	game: PunctuationGame,
	placements: Placements,
): boolean {
	const count = Object.keys(placements).length;
	return game.response_kind === "sinhala_punctuation_span"
		? count === 2
		: count > 0;
}

/**
 * The child's placements as the server contract. For a pair the child never says which mark
 * opens: the mark at the earlier gap is sent as the opening one, so a reversed pair reaches the
 * server as a reversed pair instead of being silently corrected here.
 */
export function punctuationResponse(
	game: PunctuationGame,
	placements: Placements,
): ConstructedResponse {
	const rows = ordered(game, placements);
	if (game.response_kind === "sinhala_punctuation_span") {
		const [[start, opening], [end, closing]] = rows;
		return {
			kind: "sinhala_punctuation_span",
			schema_version: PUNCTUATION_SCHEMA,
			opening_mark_token_id: opening,
			closing_mark_token_id: closing,
			start_boundary_id: start,
			end_boundary_id: end,
		};
	}
	return {
		kind: "sinhala_punctuation_placement",
		schema_version: PUNCTUATION_SCHEMA,
		placements: rows.map(([boundary, card]) => ({
			mark_token_id: card,
			boundary_id: boundary,
		})),
	};
}

/** Text with the child's marks inserted at their gaps, for the live preview only. */
export function preview(game: PunctuationGame, placements: Placements): string {
	const cardText = new Map(
		game.mark_cards.map((c) => [c.token_id, c.display_si]),
	);
	const byIndex = new Map<number, string>();
	for (const b of game.boundaries) {
		const card = placements[b.boundary_id];
		if (card) byIndex.set(b.after_token_index, cardText.get(card) ?? "");
	}
	const opener = byIndex.get(-1) ?? "";
	return (
		opener +
		game.tokens
			.map((token, index) => {
				const mark = byIndex.get(index) ?? "";
				// Opening marks attach to the next token, closing and end marks to this one.
				return mark === "“" || mark === "("
					? `${token.text_si} ${mark}`
					: token.text_si + mark;
			})
			.join(" ")
			.replace(/ ([“(]) /gu, " $1")
	);
}
