import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

type Placement = { sequence: number; sourceId: string; destinationId: string };

export function mappingResponse(
	kind: "semantic_label_mapping" | "category_exemplar_mapping",
	commandToken: string,
	placements: Placement[],
	allSourceIds: string[],
	trace: string[],
	invalidDropCount = 0,
): ConstructedResponse {
	const common = {
		command_token: commandToken,
		interaction_trace: trace,
		revisions: Math.max(
			0,
			trace.filter((event) => event.startsWith("replace:")).length,
		),
		invalid_drop_count: invalidDropCount,
		tap_alternative_used: true,
	};
	if (kind === "semantic_label_mapping")
		return {
			kind,
			...common,
			placements: placements.map((row) => ({
				sequence: row.sequence,
				label_id: row.sourceId,
				destination_id: row.destinationId,
			})),
			unplaced_label_ids: allSourceIds.filter(
				(id) => !placements.some((row) => row.sourceId === id),
			),
		};
	return {
		kind,
		...common,
		mappings: placements.map((row) => ({
			sequence: row.sequence,
			category_id: row.destinationId,
			exemplar_id: row.sourceId,
		})),
	};
}

export function groupingResponse(
	commandToken: string,
	groups: Record<string, string[]>,
	allMemberIds: string[],
	trace: string[],
): ConstructedResponse {
	const assigned = Object.values(groups).flat();
	return {
		kind: "semantic_grouping",
		command_token: commandToken,
		groups: Object.entries(groups).map(([group_id, ordered_member_ids]) => ({
			group_id,
			ordered_member_ids,
		})),
		unassigned_member_ids: allMemberIds.filter((id) => !assigned.includes(id)),
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
