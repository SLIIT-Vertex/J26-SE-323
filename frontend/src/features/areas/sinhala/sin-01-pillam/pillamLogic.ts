import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

/** Card and dock shapes as the server sends them. Nothing here says which one is right. */
export type SignCard = {
	token_id: string;
	display_si: string;
	accessible_label_si: string;
	in_consonant_context?: boolean;
};
export type Destination = { destination_id: string; text_si: string };
export type ComponentCard = {
	token_id: string;
	compose_si: string;
	logical_rank: number;
	visual_placement: string;
	display_si: string;
	accessible_label_si: string;
	label_si?: string;
	allograph_shape?: "kon" | "vak" | "aeda";
};
export type PillamGame = {
	schema_version: "sinhala-pillam-item-v1";
	chapter: string;
	activity_id: string;
	response_kind: "sinhala_pillam_match" | "sinhala_akshara_build";
	match_mode?: "name" | "vowel";
	subfamily: string;
	goal_si: string;
	sign_cards?: SignCard[];
	destinations?: Destination[];
	base?: { token_id: string; text_si: string; accessible_label_si: string };
	target_vowel_si?: string;
	component_cards?: ComponentCard[];
	maximum_components?: number;
	support_emphasis?: string;
	opening_demonstration?: {
		demonstration_id: string;
		goal_si: string;
		sign_display_si?: string;
		base_si?: string;
		target_vowel_si?: string;
		shown_si?: string | null;
		steps_si: string[];
		advance_label_si: string;
	};
};

export const RESPONSE_SCHEMA = "sinhala-pillam-response-v1" as const;
export const DOTTED_CIRCLE = "◌";

export function isPillamGame(value: unknown): value is PillamGame {
	return (
		typeof value === "object" &&
		value !== null &&
		(value as { schema_version?: unknown }).schema_version ===
			"sinhala-pillam-item-v1"
	);
}

/** Reviewed orthographic compositions normalisation cannot produce (two kombu, two gaeta). */
const EXPLICIT: Record<string, string> = {
	"ෙෙ": "ෛ",
	"ෘෘ": "ෲ",
};
const REVIEWED_SIGNS = new Set("ාැෑිීුූෘෙේෛොෝෞෲ".split(""));

/**
 * The learner's own construction as one shaped akshara, or null when the chosen cards make no
 * reviewed form. Cards are sorted into logical Unicode order, so placement order never matters.
 * This previews what the child built; it has no idea what the target is.
 */
export function composePreview(
	base: string,
	cards: readonly ComponentCard[],
): string | null {
	if (cards.length === 0) return null;
	if (cards.some((card) => card.allograph_shape)) return null;
	const marks = [...cards]
		.sort(
			(a, b) =>
				a.logical_rank - b.logical_rank ||
				a.compose_si.localeCompare(b.compose_si),
		)
		.map((card) => card.compose_si)
		.join("");
	const text = (base + (EXPLICIT[marks] ?? marks)).normalize("NFC");
	const sign = text.slice(base.length);
	return [...sign].length === 1 && REVIEWED_SIGNS.has(sign) ? text : null;
}

/** Display text for a standalone combining sign. The dotted circle is never submitted. */
export function standaloneSign(mark: string): string {
	return mark.startsWith(DOTTED_CIRCLE) ? mark : DOTTED_CIRCLE + mark;
}

/** Grapheme clusters via Intl.Segmenter: a pilla or ZWJ conjunct is never split into tiles. */
export function graphemes(text: string): string[] {
	const segmenter = new Intl.Segmenter("si", { granularity: "grapheme" });
	return [...segmenter.segment(text.normalize("NFC"))].map(
		(part) => part.segment,
	);
}

export type MatchPlacement = { source: string; destination: string };

/** Place a card on a dock. In name mode a dock holds one card; in vowel mode it holds many. */
export function placeMatch(
	placements: readonly MatchPlacement[],
	source: string,
	destination: string,
	mode: "name" | "vowel",
): MatchPlacement[] {
	const rest = placements.filter(
		(row) =>
			row.source !== source &&
			(mode === "vowel" || row.destination !== destination),
	);
	return [...rest, { source, destination }];
}

export function matchResponse(
	mode: "name" | "vowel",
	placements: readonly MatchPlacement[],
): ConstructedResponse {
	return {
		kind: "sinhala_pillam_match",
		schema_version: RESPONSE_SCHEMA,
		match_mode: mode,
		placements: placements.map((row) => ({
			source_token_id: row.source,
			destination_id: row.destination,
		})),
	};
}

export function buildResponse(
	baseId: string,
	ordered: readonly string[],
): ConstructedResponse {
	return {
		kind: "sinhala_akshara_build",
		schema_version: RESPONSE_SCHEMA,
		base_consonant_id: baseId,
		ordered_pilla_ids: [...ordered],
	};
}

/** Add or remove one card from the workbench, keeping the child's placement order. */
export function toggleComponent(
	ordered: readonly string[],
	tokenId: string,
	maximum: number,
	exclusive: boolean,
): string[] {
	if (ordered.includes(tokenId)) return ordered.filter((id) => id !== tokenId);
	if (exclusive) return [tokenId];
	return ordered.length >= maximum ? [...ordered] : [...ordered, tokenId];
}

export function isComplete(
	game: PillamGame,
	match: readonly MatchPlacement[],
	ordered: readonly string[],
): boolean {
	if (game.response_kind === "sinhala_pillam_match")
		return (game.sign_cards ?? []).every((card) =>
			match.some((row) => row.source === card.token_id),
		);
	return ordered.length > 0;
}

/** Papili and whole-sign items take exactly one card; compounds take several. */
export function exclusiveBuild(game: PillamGame): boolean {
	return !(game.component_cards ?? []).some((card) =>
		card.accessible_label_si.endsWith("කොටස"),
	);
}

export {
	SupportTeardownRegistry,
	type TeardownReceipt,
} from "../shared/teardown";

export const PAPILI_SHAPE_LABEL: Record<"kon" | "vak" | "aeda", string> = {
	kon: "කොන්",
	vak: "වක්",
	aeda: "ඇද",
};
