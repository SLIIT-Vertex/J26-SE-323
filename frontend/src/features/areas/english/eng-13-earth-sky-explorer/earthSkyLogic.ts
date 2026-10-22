import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type ExplorerLink = { sequence: number; source: string; target: string };
const revisionCount = (trace: string[]) =>
	trace.filter(
		(entry) => entry.startsWith("replace:") || entry.startsWith("clear:"),
	).length;

export function bilingualResponse(
	commandToken: string,
	links: ExplorerLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "earth_sky_bilingual_links",
		command_token: commandToken,
		links: links.map((link) => ({
			sequence: link.sequence,
			english_token: link.source,
			sinhala_token: link.target,
		})),
		unlinked_english_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: revisionCount(trace),
		invalid_link_count: 0,
		tap_alternative_used: true,
	};
}

export function sceneResponse(
	commandToken: string,
	links: ExplorerLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "earth_sky_scene_mapping",
		command_token: commandToken,
		placements: links.map((link) => ({
			sequence: link.sequence,
			word_token: link.source,
			scene_token: link.target,
		})),
		unplaced_word_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: revisionCount(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
