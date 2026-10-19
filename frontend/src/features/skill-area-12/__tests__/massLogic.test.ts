import { describe, expect, it } from "vitest";
import { balanceDifference, balanceDirection, canonicalMassArithmetic, denominationCounts, formatMass, normalizeMass, splitMass, totalGrams } from "../massLogic";

describe("mass logic", () => {
	it("uses exact integer grams and formal three-position formatting", () => {
		expect(totalGrams(3, 600)).toBe(3600);
		expect(splitMass(3600)).toEqual({ kilograms: 3, grams: 600 });
		expect(normalizeMass(2, 1750)).toEqual({ kilograms: 3, grams: 750 });
		expect(formatMass(3000)).toBe("3 kg 000 g");
	});
	it("calculates balance direction and accepts equivalent denomination counts", () => {
		expect(balanceDifference(1000, [500, 500])).toBe(0);
		expect(balanceDirection(1000, [500])).toBe("left_heavier");
		expect(balanceDirection(1000, [2000])).toBe("right_heavier");
		expect(denominationCounts([500, 500])).toEqual({ "500": 2 });
	});
	it("adds with regrouping and subtracts with borrowing", () => {
		expect(canonicalMassArithmetic("add", 8, 250, 7, 750)).toMatchObject({ result_kilograms: 16, result_grams: 0, exchange_used: true });
		expect(canonicalMassArithmetic("subtract", 14, 600, 5, 750)).toMatchObject({ result_kilograms: 8, result_grams: 850, exchange_used: true });
	});
});
