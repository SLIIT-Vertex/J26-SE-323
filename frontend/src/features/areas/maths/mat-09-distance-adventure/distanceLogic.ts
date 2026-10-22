import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
export type DistanceArithmeticResponse = Extract<
	ConstructedResponse,
	{ kind: "distance_arithmetic" }
>;
export function splitMetres(total: number) {
	if (!Number.isSafeInteger(total) || total < 0)
		throw new Error("DISTANCE_OUT_OF_RANGE");
	return { kilometres: Math.floor(total / 1000), metres: total % 1000 };
}
export function normalizeDistance(kilometres: number, metres: number) {
	if (![kilometres, metres].every((v) => Number.isSafeInteger(v) && v >= 0))
		throw new Error("DISTANCE_OUT_OF_RANGE");
	return {
		kilometres: kilometres + Math.floor(metres / 1000),
		metres: metres % 1000,
	};
}
export const formatMetres = (metres: number) => {
	if (!Number.isSafeInteger(metres) || metres < 0 || metres > 999)
		throw new Error("METRES_OUT_OF_RANGE");
	return String(metres).padStart(3, "0");
};
export function canonicalDistanceArithmetic(
	operation: "add" | "subtract",
	leftKilometres: number,
	leftMetres: number,
	rightKilometres: number,
	rightMetres: number,
): DistanceArithmeticResponse {
	if (operation === "add") {
		const subtotal = leftMetres + rightMetres;
		const carry = Math.floor(subtotal / 1000);
		const resultKilometres = leftKilometres + rightKilometres + carry;
		const resultMetres = subtotal % 1000;
		return {
			kind: "distance_arithmetic",
			operation,
			left_kilometres: leftKilometres,
			left_metres: leftMetres,
			right_kilometres: rightKilometres,
			right_metres: rightMetres,
			metre_subtotal_or_adjustment: subtotal,
			exchange_or_regrouping_used: carry > 0,
			carried_or_borrowed_kilometres: carry,
			result_kilometres: resultKilometres,
			result_metres: resultMetres,
			working_steps: [
				`metres:${leftMetres}+${rightMetres}=${subtotal}`,
				`regroup:${carry}`,
				`kilometres:${leftKilometres}+${rightKilometres}+${carry}=${resultKilometres}`,
			],
		};
	}
	if (leftKilometres * 1000 + leftMetres < rightKilometres * 1000 + rightMetres)
		throw new Error("NEGATIVE_DISTANCE");
	const borrow = leftMetres < rightMetres ? 1 : 0;
	const adjustedKilometres = leftKilometres - borrow;
	const adjustedMetres = leftMetres + borrow * 1000;
	const resultMetres = adjustedMetres - rightMetres;
	const resultKilometres = adjustedKilometres - rightKilometres;
	return {
		kind: "distance_arithmetic",
		operation,
		left_kilometres: leftKilometres,
		left_metres: leftMetres,
		right_kilometres: rightKilometres,
		right_metres: rightMetres,
		metre_subtotal_or_adjustment: resultMetres,
		exchange_or_regrouping_used: borrow > 0,
		carried_or_borrowed_kilometres: borrow,
		result_kilometres: resultKilometres,
		result_metres: resultMetres,
		working_steps: [
			`borrow:${borrow}`,
			`metres:${adjustedMetres}-${rightMetres}=${resultMetres}`,
			`kilometres:${adjustedKilometres}-${rightKilometres}=${resultKilometres}`,
		],
	};
}
