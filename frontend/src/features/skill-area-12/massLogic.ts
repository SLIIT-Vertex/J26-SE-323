import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type MassArithmeticResponse = Extract<ConstructedResponse, { kind: "mass_arithmetic" }>;
export const STANDARD_MASSES_G = [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000] as const;

function validInteger(value: number) {
	return Number.isSafeInteger(value) && value >= 0;
}

export function splitMass(totalG: number) {
	if (!validInteger(totalG)) throw new Error("MASS_OUT_OF_RANGE");
	return { kilograms: Math.floor(totalG / 1000), grams: totalG % 1000 };
}

export function totalGrams(kilograms: number, grams: number) {
	if (![kilograms, grams].every(validInteger)) throw new Error("MASS_OUT_OF_RANGE");
	return kilograms * 1000 + grams;
}

export function normalizeMass(kilograms: number, grams: number) {
	return splitMass(totalGrams(kilograms, grams));
}

export function formatMass(totalG: number) {
	const { kilograms, grams } = splitMass(totalG);
	return `${kilograms} kg ${String(grams).padStart(3, "0")} g`;
}

export function denominationCounts(values: number[]) {
	return values.reduce<Record<string, number>>((counts, value) => {
		counts[String(value)] = (counts[String(value)] ?? 0) + 1;
		return counts;
	}, {});
}

export function balanceDifference(targetG: number, selected: number[]) {
	return selected.reduce((sum, value) => sum + value, 0) - targetG;
}

export function balanceDirection(targetG: number, selected: number[]) {
	const difference = balanceDifference(targetG, selected);
	return difference === 0 ? "balanced" : difference < 0 ? "left_heavier" : "right_heavier";
}

export function canonicalMassArithmetic(
	operation: "add" | "subtract",
	leftKg: number,
	leftG: number,
	rightKg: number,
	rightG: number,
): MassArithmeticResponse {
	if (operation === "add") {
		const subtotal = leftG + rightG;
		const carry = Math.floor(subtotal / 1000);
		return { kind: "mass_arithmetic", operation, left_kilograms: leftKg, left_grams: leftG, right_kilograms: rightKg, right_grams: rightG, gram_subtotal_or_adjustment: subtotal, carried_or_borrowed_kilograms: carry, exchange_used: carry > 0, working_steps: [`g:${leftG}+${rightG}=${subtotal}`, `carry:${carry}`, `g-result:${subtotal % 1000}`, `kg:${leftKg}+${rightKg}+${carry}=${leftKg + rightKg + carry}`], result_kilograms: leftKg + rightKg + carry, result_grams: subtotal % 1000 };
	}
	if (totalGrams(leftKg, leftG) < totalGrams(rightKg, rightG)) throw new Error("NEGATIVE_MASS");
	const borrow = leftG < rightG ? 1 : 0;
	const adjustedKg = leftKg - borrow;
	const adjustedG = leftG + borrow * 1000;
	return { kind: "mass_arithmetic", operation, left_kilograms: leftKg, left_grams: leftG, right_kilograms: rightKg, right_grams: rightG, gram_subtotal_or_adjustment: adjustedG, carried_or_borrowed_kilograms: borrow, exchange_used: borrow > 0, working_steps: [`borrow:${borrow}`, `adjust:${leftKg}->${adjustedKg}:${leftG}->${adjustedG}`, `g:${adjustedG}-${rightG}=${adjustedG - rightG}`, `kg:${adjustedKg}-${rightKg}=${adjustedKg - rightKg}`], result_kilograms: adjustedKg - rightKg, result_grams: adjustedG - rightG };
}
