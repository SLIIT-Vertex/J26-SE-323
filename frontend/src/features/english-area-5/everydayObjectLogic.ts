import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type ObjectLink = { sequence: number; source: string; target: string };

export function objectMappingResponse(
	kind: "object_vocabulary_mapping" | "lesson_place_sort",
	commandToken: string,
	links: ObjectLink[],
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
	if (kind === "object_vocabulary_mapping")
		return {
			kind,
			...common,
			placements: links.map((link) => ({
				sequence: link.sequence,
				word_token: link.source,
				object_token: link.target,
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
			zone_token: link.target,
		})),
		unplaced_entry_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
	};
}

export function objectNameResponse(
	commandToken: string,
	objectToken: string,
	chunks: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "object_name_sequence",
		command_token: commandToken,
		object_token: objectToken,
		ordered_chunk_tokens: chunks,
		unused_chunk_tokens: [],
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("remove:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
