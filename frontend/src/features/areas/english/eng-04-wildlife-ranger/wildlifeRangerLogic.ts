import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type WildlifeLink = { sequence: number; source: string; target: string };

export function wildlifeMappingResponse(
	kind:
		| "animal_vocabulary_mapping"
		| "lesson_heading_sort"
		| "animal_part_labeling",
	commandToken: string,
	links: WildlifeLink[],
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
	if (kind === "animal_part_labeling")
		return {
			kind,
			...common,
			labels: links.map((link) => ({
				sequence: link.sequence,
				entry_token: link.source,
				target_token: link.target,
			})),
			unfilled_part_tokens: sources.filter(
				(source) => !links.some((link) => link.source === source),
			),
		};
	return {
		kind,
		...common,
		placements: links.map((link) => ({
			sequence: link.sequence,
			entry_token: link.source,
			target_token: link.target,
		})),
		unplaced_entry_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
	};
}
