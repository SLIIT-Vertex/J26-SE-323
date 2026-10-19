import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type CapacityArithmeticResponse = Extract<ConstructedResponse, { kind: "capacity_arithmetic" }>;
export const CAPACITY_PORTIONS = [100, 200, 250, 500, 1000] as const;

export function splitCapacity(totalMl: number) {
	if (!Number.isSafeInteger(totalMl) || totalMl < 0) throw new Error("CAPACITY_OUT_OF_RANGE");
	return { litres: Math.floor(totalMl / 1000), millilitres: totalMl % 1000 };
}

export function totalMillilitres(litres: number, millilitres: number) {
	if (![litres, millilitres].every((value) => Number.isSafeInteger(value) && value >= 0)) throw new Error("CAPACITY_OUT_OF_RANGE");
	return litres * 1000 + millilitres;
}

export function normalizeCapacity(litres: number, millilitres: number) {
	return splitCapacity(totalMillilitres(litres, millilitres));
}

export function formatCapacity(totalMl: number) {
	const { litres, millilitres } = splitCapacity(totalMl);
	return `${litres} l ${String(millilitres).padStart(3, "0")} ml`;
}

export function portionCounts(values: number[]) {
	return values.reduce<Record<string, number>>((counts, value) => {
		counts[String(value)] = (counts[String(value)] ?? 0) + 1;
		return counts;
	}, {});
}

export function canonicalCapacityArithmetic(
	operation: "add" | "subtract",
	leftLitres: number,
	leftMl: number,
	rightLitres: number,
	rightMl: number,
): CapacityArithmeticResponse {
	if (operation === "add") {
		const subtotal = leftMl + rightMl;
		const carry = Math.floor(subtotal / 1000);
		return { kind: "capacity_arithmetic", operation, left_litres: leftLitres, left_millilitres: leftMl, right_litres: rightLitres, right_millilitres: rightMl, millilitre_subtotal_or_adjustment: subtotal, carried_or_borrowed_litres: carry, exchange_used: carry > 0, working_steps: [`ml:${leftMl}+${rightMl}=${subtotal}`, `carry:${carry}`, `ml-result:${subtotal % 1000}`, `litres:${leftLitres}+${rightLitres}+${carry}=${leftLitres + rightLitres + carry}`], result_litres: leftLitres + rightLitres + carry, result_millilitres: subtotal % 1000 };
	}
	if (totalMillilitres(leftLitres, leftMl) < totalMillilitres(rightLitres, rightMl)) throw new Error("NEGATIVE_CAPACITY");
	const borrow = leftMl < rightMl ? 1 : 0;
	const adjustedLitres = leftLitres - borrow;
	const adjustedMl = leftMl + borrow * 1000;
	return { kind: "capacity_arithmetic", operation, left_litres: leftLitres, left_millilitres: leftMl, right_litres: rightLitres, right_millilitres: rightMl, millilitre_subtotal_or_adjustment: adjustedMl, carried_or_borrowed_litres: borrow, exchange_used: borrow > 0, working_steps: [`borrow:${borrow}`, `adjust:${leftLitres}->${adjustedLitres}:${leftMl}->${adjustedMl}`, `ml:${adjustedMl}-${rightMl}=${adjustedMl - rightMl}`, `litres:${adjustedLitres}-${rightLitres}=${adjustedLitres - rightLitres}`], result_litres: adjustedLitres - rightLitres, result_millilitres: adjustedMl - rightMl };
}
