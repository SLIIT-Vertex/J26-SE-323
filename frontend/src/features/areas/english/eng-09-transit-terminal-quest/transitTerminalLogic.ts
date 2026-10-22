import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type TicketLink = { sequence: number; source: string; target: string };

export const VEHICLE_MARKS = ["🚆", "🚲", "🚁", "✈️", "🚌", "🚗"] as const;

export function transportMappingResponse(
	commandToken: string,
	links: TicketLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "transport_vocabulary_mapping",
		command_token: commandToken,
		placements: links.map((link) => ({
			sequence: link.sequence,
			word_token: link.source,
			vehicle_token: link.target,
		})),
		unplaced_word_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
