import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type HeritageLink = { sequence: number; source: string; target: string };

const revisions = (trace: string[]) =>
	trace.filter(
		(entry) => entry.startsWith("replace") || entry.startsWith("clear"),
	).length;

export function pastBilingualResponse(
	commandToken: string,
	links: HeritageLink[],
	sourceTokens: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "past_bilingual_links",
		command_token: commandToken,
		links: links.map((link) => ({
			sequence: link.sequence,
			english_token: link.source,
			sinhala_token: link.target,
		})),
		unlinked_english_tokens: sourceTokens.filter(
			(token) => !links.some((link) => link.source === token),
		),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_link_count: 0,
		tap_alternative_used: true,
	};
}

export function exhibitMappingResponse(
	commandToken: string,
	links: HeritageLink[],
	sourceTokens: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "heritage_exhibit_mapping",
		command_token: commandToken,
		placements: links.map((link) => ({
			sequence: link.sequence,
			word_token: link.source,
			exhibit_token: link.target,
		})),
		unplaced_word_tokens: sourceTokens.filter(
			(token) => !links.some((link) => link.source === token),
		),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
