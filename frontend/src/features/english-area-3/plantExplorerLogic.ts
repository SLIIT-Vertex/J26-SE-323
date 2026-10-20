import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type Link = { sequence: number; source: string; target: string };

export function plantMappingResponse(
	kind: "plant_vocabulary_mapping" | "plant_part_labeling",
	commandToken: string,
	links: Link[],
	allSources: string[],
	trace: string[],
): ConstructedResponse {
	const common = {
		command_token: commandToken,
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
	if (kind === "plant_vocabulary_mapping")
		return {
			kind,
			...common,
			placements: links.map((link) => ({
				sequence: link.sequence,
				word_token: link.source,
				target_token: link.target,
			})),
			unplaced_word_tokens: allSources.filter(
				(source) => !links.some((link) => link.source === source),
			),
		};
	return {
		kind,
		...common,
		labels: links.map((link) => ({
			sequence: link.sequence,
			part_token: link.target,
			label_token: link.source,
		})),
		unfilled_part_tokens: allSources.filter(
			(source) => !links.some((link) => link.source === source),
		),
	};
}

export function numberPairResponse(
	commandToken: string,
	pairs: Array<{
		concept_token: string;
		singular_form_token: string;
		plural_form_token: string;
	}>,
	trace: string[],
): ConstructedResponse {
	return {
		kind: "singular_plural_pairing",
		command_token: commandToken,
		pairs,
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
