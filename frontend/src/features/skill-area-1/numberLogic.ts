export function expandedForm(value: number): string {
	if (!Number.isSafeInteger(value) || value < 0 || value > 100_000)
		throw new Error("NUMBER_OUT_OF_RANGE");
	const digits = String(value).split("").map(Number);
	return (
		digits
			.map((digit, index) => digit * 10 ** (digits.length - index - 1))
			.filter(Boolean)
			.join(" + ") || "0"
	);
}

export function abacusDigits(value: number): number[] {
	if (!Number.isSafeInteger(value) || value < 0 || value > 999_999)
		throw new Error("NUMBER_OUT_OF_RANGE");
	return String(value).padStart(6, "0").split("").map(Number);
}

export function constructExtreme(digits: number[], greatest: boolean): number {
	const ordered = [...digits].sort((a, b) => (greatest ? b - a : a - b));
	if (!greatest && ordered[0] === 0) {
		const index = ordered.findIndex((value) => value !== 0);
		if (index < 0) throw new Error("LEADING_ZERO_ONLY");
		[ordered[0], ordered[index]] = [ordered[index], ordered[0]];
	}
	return Number(ordered.join(""));
}

export function reorder<T>(values: T[], from: number, to: number): T[] {
	const result = [...values];
	const [item] = result.splice(from, 1);
	result.splice(to, 0, item);
	return result;
}

export function valueFromAbacus(rods: number[]): number {
	if (
		rods.length !== 6 ||
		rods.some((value) => !Number.isInteger(value) || value < 0 || value > 9)
	)
		throw new Error("INVALID_RODS");
	return Number(rods.join(""));
}

export function isValidDigitConstruction(
	supplied: number[],
	arranged: number[],
): boolean {
	return (
		arranged.length === supplied.length &&
		arranged[0] !== 0 &&
		[...arranged].sort().join() === [...supplied].sort().join()
	);
}

export function isValidNumberOrder(
	supplied: number[],
	arranged: number[],
	ascending: boolean,
): boolean {
	const expected = [...supplied].sort((a, b) => (ascending ? a - b : b - a));
	return (
		arranged.length === expected.length &&
		arranged.every((value, index) => value === expected[index])
	);
}
