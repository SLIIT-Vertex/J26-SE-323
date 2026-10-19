import type { DirectionId } from "./manifest";

export type CompassPosition =
	| "top"
	| "top_right"
	| "right"
	| "bottom_right"
	| "bottom"
	| "bottom_left"
	| "left"
	| "top_left";

export type PlaceStatement = {
	statement_id: string;
	place_id: string;
	template_si: string;
};

export function compassResponse(
	kind: "main_direction_compass" | "secondary_direction_compass",
	positions: CompassPosition[],
	values: Partial<Record<CompassPosition, DirectionId>>,
	selectionOrder: string[],
	anchors: DirectionId[] = [],
) {
	if (positions.some((position) => !values[position])) return null;
	const response = {
		kind,
		selections: positions.map((position) => ({
			position,
			direction: values[position] as DirectionId,
		})),
		selection_order: [...selectionOrder],
	};
	return kind === "secondary_direction_compass"
		? { ...response, anchor_directions_seen: anchors }
		: response;
}

export function sceneResponse(
	sceneId: string,
	statements: PlaceStatement[],
	values: Record<string, DirectionId | "">,
	selectionOrder: string[],
	revisions: number,
) {
	if (statements.some((statement) => !values[statement.statement_id]))
		return null;
	return {
		kind: "place_direction_scene" as const,
		scene_id: sceneId,
		selections: statements.map((statement) => ({
			statement_id: statement.statement_id,
			place_id: statement.place_id,
			selected_direction: values[statement.statement_id] as DirectionId,
		})),
		selection_order: [...selectionOrder],
		revisions,
	};
}
