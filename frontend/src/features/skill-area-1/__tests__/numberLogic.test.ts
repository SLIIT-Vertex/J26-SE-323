import { describe, expect, it } from "vitest";
import {
	abacusDigits,
	constructExtreme,
	expandedForm,
	reorder,
	isValidDigitConstruction,
	isValidNumberOrder,
	valueFromAbacus,
} from "../numberLogic";

describe("Number World deterministic mechanics", () => {
	it("calculates expanded form and preserves internal zeroes on the abacus", () => {
		expect(expandedForm(42_305)).toBe("40000 + 2000 + 300 + 5");
		expect(abacusDigits(40_205)).toEqual([0, 4, 0, 2, 0, 5]);
	});

	it("uses each digit once and prevents a leading zero", () => {
		expect(constructExtreme([0, 7, 2, 5], true)).toBe(7520);
		expect(constructExtreme([0, 7, 2, 5], false)).toBe(2057);
		expect(() => constructExtreme([0, 0, 0], false)).toThrow(
			"LEADING_ZERO_ONLY",
		);
	});

	it("reorders number stones without losing or duplicating values", () => {
		expect(reorder([40_105, 40_015, 40_150], 2, 0)).toEqual([
			40_150, 40_105, 40_015,
		]);
	});

	it("validates direct abacus, digit, and route constructions", () => {
		expect(valueFromAbacus([0, 4, 0, 2, 0, 5])).toBe(40_205);
		expect(isValidDigitConstruction([0, 7, 2, 5], [2, 0, 5, 7])).toBe(true);
		expect(isValidDigitConstruction([0, 7, 2, 5], [0, 2, 5, 7])).toBe(false);
		expect(
			isValidNumberOrder(
				[40_105, 40_015, 40_150],
				[40_015, 40_105, 40_150],
				true,
			),
		).toBe(true);
	});
});
