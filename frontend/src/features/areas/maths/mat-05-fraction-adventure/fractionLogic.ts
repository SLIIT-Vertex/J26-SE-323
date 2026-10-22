import type { ConstructedResponsePayload } from "../mobile-learning-flow/api/generated";

export function shadingResponse(
	representation: "circle" | "rectangle",
	denominator: 2 | 4,
	selected: number[],
): ConstructedResponsePayload {
	return {
		kind: "fraction_shading",
		representation,
		denominator,
		shaded_indices: [...new Set(selected)].sort((a, b) => a - b),
	};
}
export function groupingResponse(
	denominator: 2 | 4,
	assignments: number[],
): ConstructedResponsePayload {
	return { kind: "equal_grouping", denominator, assignments: [...assignments] };
}
export function quarterTableResponse(
	total: number,
	values: [number, number, number],
): ConstructedResponsePayload {
	return { kind: "fraction_quantity_table", total, quarter_values: values };
}
export function tenthsResponse(
	representation: "circle" | "strip",
	numerator: number,
	shaded: number[],
): ConstructedResponsePayload {
	return {
		kind: "tenths_representation",
		representation,
		numerator,
		denominator: 10,
		shaded_indices: [...new Set(shaded)].sort((a, b) => a - b),
	};
}
