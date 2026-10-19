export function validateTenths(value: number): boolean {
	return Number.isInteger(value) && value >= 1 && value <= 9;
}

export function tenthsToDecimal(numerator: number): string {
	if (!validateTenths(numerator)) throw new Error("TENTHS_OUT_OF_RANGE");
	return `0.${numerator}`;
}

export function decimalToTenths(value: string): {
	numerator: number;
	denominator: 10;
} {
	if (!/^0\.[1-9]$/.test(value)) throw new Error("INVALID_TENTHS_DECIMAL");
	return { numerator: Number(value[2]), denominator: 10 };
}

export function uniqueReadingMatches(
	decimalTenths: number[],
	readingIds: string[],
) {
	return (
		decimalTenths.length === readingIds.length &&
		new Set(decimalTenths).size === decimalTenths.length &&
		new Set(readingIds).size === readingIds.length
	);
}

export function validateSelectedTenths(selected: number[]): number[] | null {
	if (
		selected.some(
			(index) => !Number.isInteger(index) || index < 0 || index > 9,
		) ||
		new Set(selected).size !== selected.length
	)
		return null;
	return [...selected].sort((a, b) => a - b);
}

export function decimalReadingResponse(
	decimalTenths: number[],
	values: Record<number, string>,
	trace: string[],
	revisions: number,
) {
	if (decimalTenths.some((digit) => !values[digit])) return null;
	const ids = decimalTenths.map((digit) => values[digit]);
	if (!uniqueReadingMatches(decimalTenths, ids)) return null;
	return {
		kind: "decimal_reading_match" as const,
		matches: decimalTenths.map((decimal_tenths) => ({
			decimal_tenths,
			reading_id: values[decimal_tenths],
		})),
		interaction_trace: trace,
		revisions,
	};
}

export function shadingResponse(
	representation: "rectangle" | "circle",
	decimalTenths: number,
	selected: number[],
	trace: string[],
	revisions: number,
) {
	const valid = validateSelectedTenths(selected);
	if (!valid) return null;
	return {
		kind: "decimal_tenths_shading" as const,
		representation,
		decimal_tenths: decimalTenths,
		selected_part_indices: valid,
		selected_count: valid.length,
		total_parts: 10 as const,
		interaction_trace: trace,
		revisions,
	};
}

export function fractionToDecimalResponse(
	numerator: number,
	digit: string,
	trace: string[],
) {
	if (!/^[1-9]$/.test(digit)) return null;
	return {
		kind: "tenths_fraction_to_decimal" as const,
		numerator,
		denominator: 10 as const,
		fixed_whole_digit: 0 as const,
		entered_tenths_digit: Number(digit),
		decimal_value: `0.${digit}`,
		input_trace: trace,
	};
}

export function decimalToFractionResponse(
	decimalTenths: number,
	numerator: string,
	denominator: string,
	inputOrder: Array<"numerator" | "denominator">,
	trace: string[],
) {
	if (!/^[0-9]$/.test(numerator) || !/^[0-9]{1,2}$/.test(denominator))
		return null;
	return {
		kind: "decimal_to_tenths_fraction" as const,
		decimal_tenths: decimalTenths,
		entered_numerator: Number(numerator),
		entered_denominator: Number(denominator),
		fraction_bar_present: true as const,
		input_order: inputOrder,
		input_trace: trace,
	};
}

export function firstIncorrectConversionStep(
	expected: { numerator: number; denominator: number },
	actual: { numerator: number; denominator: number },
) {
	if (actual.numerator !== expected.numerator) return "numerator";
	if (actual.denominator !== expected.denominator) return "denominator";
	return null;
}
