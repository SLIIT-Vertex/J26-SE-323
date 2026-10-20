import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type FoodLink = { sequence: number; source: string; target: string };

export const FOOD_GLYPHS = [
	"🥚",
	"🍞",
	"🐟",
	"🥥",
	"🥯",
	"🥗",
	"🧈",
	"🌶️",
	"🏠",
	"🍟",
	"🟤",
	"🍠",
	"🍵",
	"🥛",
	"💧",
	"🧃",
	"🍌",
	"🍍",
	"🥭",
	"🍉",
	"🫒",
	"🥔",
	"🥬",
	"🍅",
	"🥕",
	"🥒",
	"🍛",
	"🍨",
	"🌹",
	"🍏",
	"🟣",
	"🌿",
] as const;

export function foodMappingResponse(
	kind: "food_vocabulary_mapping" | "food_lesson_group_sort",
	commandToken: string,
	links: FoodLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	const common = {
		command_token: commandToken,
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
	if (kind === "food_vocabulary_mapping")
		return {
			kind,
			...common,
			placements: links.map((link) => ({
				sequence: link.sequence,
				word_token: link.source,
				food_token: link.target,
			})),
			unplaced_word_tokens: sources.filter(
				(source) => !links.some((link) => link.source === source),
			),
		};
	return {
		kind,
		...common,
		placements: links.map((link) => ({
			sequence: link.sequence,
			entry_token: link.source,
			stall_token: link.target,
		})),
		unplaced_entry_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
	};
}

export function foodNameResponse(
	commandToken: string,
	foodToken: string,
	chunks: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "food_name_sequence",
		command_token: commandToken,
		food_token: foodToken,
		ordered_chunk_tokens: chunks,
		unused_chunk_tokens: [],
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("remove:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
