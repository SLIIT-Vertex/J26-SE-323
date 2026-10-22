export const ROMANS: Record<number, string> = {
	1: "i",
	2: "ii",
	3: "iii",
	4: "iv",
	5: "v",
	6: "vi",
	7: "vii",
	8: "viii",
	9: "ix",
	10: "x",
	11: "xi",
	12: "xii",
	13: "xiii",
	14: "xiv",
	15: "xv",
	16: "xvi",
	17: "xvii",
	18: "xviii",
	19: "xix",
	20: "xx",
};
export function intToRoman(value: number) {
	if (!Number.isInteger(value) || !ROMANS[value])
		throw new Error("ROMAN_VALUE_OUT_OF_RANGE");
	return ROMANS[value];
}
export function romanToInt(value: string) {
	const normalized = value.toLowerCase(),
		entry = Object.entries(ROMANS).find(([, roman]) => roman === normalized);
	if (!entry) throw new Error("NONCANONICAL_ROMAN_NUMERAL");
	return Number(entry[0]);
}
export function evaluateRoman(
	left: string,
	operation: "add" | "subtract",
	right: string,
) {
	const result =
		operation === "add"
			? romanToInt(left) + romanToInt(right)
			: romanToInt(left) - romanToInt(right);
	if (!ROMANS[result]) throw new Error("ROMAN_RESULT_OUT_OF_RANGE");
	return result;
}
export function matchResponse(
	roundId: string,
	values: number[],
	matches: Record<number, string>,
	trace: string[],
	revisions: number,
) {
	if (values.some((value) => !matches[value])) return null;
	return {
		kind: "roman_numeral_match" as const,
		round_id: roundId,
		matches: values.map((arabic_value) => ({
			arabic_value,
			selected_roman: matches[arabic_value],
		})),
		interaction_trace: trace,
		revisions,
	};
}
export function emojiResponse(
	groupId: string,
	emojiId: string,
	quantity: number,
	counted: number[],
	symbols: string[],
	trace: string[],
	revisions: number,
) {
	if (
		!counted.length ||
		!symbols.length ||
		symbols.some((symbol) => !["i", "v", "x"].includes(symbol))
	)
		return null;
	return {
		kind: "emoji_quantity_to_roman" as const,
		group_id: groupId,
		emoji_id: emojiId,
		quantity,
		counted_indices: counted,
		constructed_symbols: symbols as Array<"i" | "v" | "x">,
		final_roman: symbols.join(""),
		interaction_trace: trace,
		revisions,
	};
}
export function arithmeticResponse(
	problemId: string,
	left: string,
	operation: "add" | "subtract",
	right: string,
	symbols: string[],
	trace: string[],
	revisions: number,
) {
	if (
		!symbols.length ||
		symbols.some((symbol) => !["i", "v", "x"].includes(symbol))
	)
		return null;
	let leftValue: number | null = null,
		rightValue: number | null = null;
	try {
		leftValue = romanToInt(left);
		rightValue = romanToInt(right);
	} catch {
		return null;
	}
	const final = symbols.join("");
	let finalValue = 0;
	try {
		finalValue = romanToInt(final);
	} catch {
		finalValue = symbols.reduce(
			(sum, s) => sum + (s === "i" ? 1 : s === "v" ? 5 : 10),
			0,
		);
	}
	return {
		kind: "roman_arithmetic" as const,
		problem_id: problemId,
		left_roman: left,
		operation,
		right_roman: right,
		left_value_work: leftValue,
		right_value_work: rightValue,
		constructed_result_symbols: symbols as Array<"i" | "v" | "x">,
		final_roman: final,
		final_value: finalValue,
		interaction_trace: trace,
		revisions,
	};
}
