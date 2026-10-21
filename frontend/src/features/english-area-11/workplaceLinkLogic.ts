import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type CityLink = { sequence: number; source: string; target: string };
const revisions = (trace: string[]) =>
	trace.filter(
		(entry) => entry.startsWith("replace:") || entry.startsWith("clear:"),
	).length;

export function workVocabularyResponse(
	commandToken: string,
	links: CityLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "work_vocabulary_mapping",
		command_token: commandToken,
		placements: links.map((link) => ({
			sequence: link.sequence,
			word_token: link.source,
			representation_token: link.target,
		})),
		unplaced_word_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}

export function occupationPlaceResponse(
	commandToken: string,
	links: CityLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "occupation_place_links",
		command_token: commandToken,
		links: links.map((link) => ({
			sequence: link.sequence,
			occupation_token: link.source,
			place_token: link.target,
		})),
		unlinked_occupation_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_link_count: 0,
		tap_alternative_used: true,
	};
}
