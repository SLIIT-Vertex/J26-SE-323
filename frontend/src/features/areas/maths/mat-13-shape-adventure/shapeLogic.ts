export type ShapeRow = {
	solid_id: string;
	faces: number;
	vertices: number;
	edges: number;
};
export type Orientation = "horizontal" | "vertical";

export const SHAPE_PROPERTIES: Record<string, Omit<ShapeRow, "solid_id">> = {
	cube: { faces: 6, vertices: 8, edges: 12 },
	cuboid: { faces: 6, vertices: 8, edges: 12 },
	cylinder: { faces: 2, vertices: 0, edges: 2 },
	triangular_pyramid: { faces: 4, vertices: 4, edges: 6 },
};

export function shapeTableResponse(
	rowIds: string[],
	values: Record<string, number | null>,
) {
	const rows = rowIds.map((solid_id) => ({
		solid_id,
		faces: values[`${solid_id}:faces`],
		vertices: values[`${solid_id}:vertices`],
		edges: values[`${solid_id}:edges`],
	}));
	if (rows.some((row) => Object.values(row).some((value) => value == null)))
		return null;
	return {
		kind: "shape_property_table" as const,
		rows: rows as ShapeRow[],
		filled_cells: rowIds.flatMap((id) =>
			["faces", "vertices", "edges"].map((field) => `${id}:${field}`),
		),
	};
}

export function orientationResponse(
	exampleIds: string[],
	values: Record<string, Orientation | "">,
) {
	if (exampleIds.some((id) => !values[id])) return null;
	return {
		kind: "orientation_identification" as const,
		selections: exampleIds.map((example_id) => ({
			example_id,
			orientation: values[example_id] as Orientation,
		})),
	};
}

export function netMatchResponse(
	solidIds: string[],
	matches: Record<string, string>,
	trace: string[],
) {
	if (solidIds.some((id) => !matches[id])) return null;
	return {
		kind: "solid_net_match" as const,
		matches: solidIds.map((solid_id) => ({
			solid_id,
			net_id: matches[solid_id],
		})),
		interaction_trace: trace,
	};
}
