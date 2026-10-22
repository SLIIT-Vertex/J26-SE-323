import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type RiddleGame = {
	schema_version: "sinhala-riddle-item-v1";
	chapter: "clue_path" | "clue_bridge" | "word_secret_box";
	activity_id: string;
	response_kind: "sinhala_riddle_solution";
	subfamily: string;
	goal_si: string;
	riddle_lines_si: string[];
	clue_spans: Array<{ span_id: string; text_si: string }>;
	answer_cards: Array<{ card_id: string; text_si: string }>;
	evidence_limit: number;
	support_emphasis?: string;
	opening_demonstration?: {
		demonstration_id: string;
		goal_si: string;
		riddle_lines_si?: string[];
		shown_si?: string | null;
		steps_si: string[];
		advance_label_si: string;
	};
};

export const RIDDLE_SCHEMA = "sinhala-riddle-response-v1" as const;

export function isRiddleGame(value: unknown): value is RiddleGame {
	return (
		typeof value === "object" &&
		value !== null &&
		(value as { schema_version?: unknown }).schema_version ===
			"sinhala-riddle-item-v1"
	);
}

/** The child's own evidence, in selection order. Selecting again removes it. */
export function toggleSpan(
	spans: readonly string[],
	span: string,
	limit: number,
): string[] {
	if (spans.includes(span)) return spans.filter((id) => id !== span);
	return spans.length >= limit ? [...spans] : [...spans, span];
}

export type RiddleAction =
	| { type: "select_span" | "remove_span"; id: string }
	| { type: "place_card" | "swap_card"; id: string };

/** Bounded semantic history (no pointer trails): what the child did, in order. */
export function recordAction(
	history: readonly RiddleAction[],
	action: RiddleAction,
	limit = 40,
): RiddleAction[] {
	return [...history, action].slice(-limit);
}

export function riddleResponse(
	answer: string,
	spans: readonly string[],
): ConstructedResponse {
	return {
		kind: "sinhala_riddle_solution",
		schema_version: RIDDLE_SCHEMA,
		answer_card_id: answer,
		evidence_span_ids: [...spans],
	};
}
