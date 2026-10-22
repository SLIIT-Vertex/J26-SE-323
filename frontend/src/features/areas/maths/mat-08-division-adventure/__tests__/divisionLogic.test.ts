import { describe, expect, it } from "vitest";
import {
	canonicalLongDivision,
	contextualRemainderInterpretation,
	integerDivision,
	validateDivisionOperands,
	validateWorkingTrace,
	writtenDivisionResponse,
} from "../divisionLogic";

describe("division paper-working logic", () => {
	it("generates every divide, multiply, subtract and bring-down step", () => {
		const steps = canonicalLongDivision(84, 4);
		expect(steps).toEqual([
			{
				step_index: 0,
				partial_dividend: 8,
				quotient_digit: 2,
				quotient_column: 0,
				partial_product: 8,
				subtraction_result: 0,
				brought_down_digit: 4,
			},
			{
				step_index: 1,
				partial_dividend: 4,
				quotient_digit: 1,
				quotient_column: 1,
				partial_product: 4,
				subtraction_result: 0,
				brought_down_digit: null,
			},
		]);
		expect(validateWorkingTrace(84, 4, steps)).toEqual({
			valid: true,
			firstIncorrectStep: null,
		});
	});

	it("preserves a zero quotient digit and validates a remainder", () => {
		expect(
			canonicalLongDivision(408, 4).map((step) => step.quotient_digit),
		).toEqual([1, 0, 2]);
		expect(integerDivision(157, 4)).toEqual({ quotient: 39, remainder: 1 });
		expect(() => validateDivisionOperands(20, 0)).toThrow(
			"DIVISION_OPERANDS_OUT_OF_RANGE",
		);
	});

	it("builds the semantic evidence arrays from the ordered trace", () => {
		const steps = canonicalLongDivision(157, 4);
		const response = writtenDivisionResponse(157, 4, steps, 39, 1);
		expect(response.partial_dividends).toEqual([15, 37]);
		expect(response.partial_products).toEqual([12, 36]);
		expect(response.subtraction_results).toEqual([3, 1]);
		expect(response.brought_down_digits).toEqual([7]);
		expect(contextualRemainderInterpretation(39, 1)).toBe(
			"complete_groups:39;leftover:1",
		);
	});
});
