import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type BloomLink = { sequence: number; source: string; target: string };

export function flowerMappingResponse(
	commandToken: string,
	links: BloomLink[],
	wordTokens: string[],
	trace: string[],
	detailSheetOpenCount: number,
): ConstructedResponse {
	return {
		kind: "flower_vocabulary_mapping",
		command_token: commandToken,
		placements: links.map((link) => ({ sequence: link.sequence, word_token: link.source, flower_token: link.target })),
		unplaced_word_tokens: wordTokens.filter((token) => !links.some((link) => link.source === token)),
		interaction_trace: trace,
		revisions: trace.filter((entry) => entry.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
		detail_sheet_open_count: detailSheetOpenCount,
	};
}
