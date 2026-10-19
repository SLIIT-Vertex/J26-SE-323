import { describe, expect, it } from "vitest";
import {
	decimalReadingResponse,
	decimalToFractionResponse,
	decimalToTenths,
	firstIncorrectConversionStep,
	fractionToDecimalResponse,
	shadingResponse,
	tenthsToDecimal,
	validateSelectedTenths,
	validateTenths,
} from "../decimalLogic";

describe("decimal adventure mathematics and evidence", () => {
	it("converts every tenth from 1/10 through 9/10", () => {
		for (let n = 1; n <= 9; n += 1) {
			expect(validateTenths(n)).toBe(true);
			expect(tenthsToDecimal(n)).toBe(`0.${n}`);
			expect(decimalToTenths(`0.${n}`)).toEqual({
				numerator: n,
				denominator: 10,
			});
		}
	});
	it("builds unique reading and complete shading evidence", () => {
		expect(
			decimalReadingResponse(
				[1, 2],
				{ 1: "reading-1", 2: "reading-2" },
				["a", "b"],
				1,
			),
		).toEqual(
			expect.objectContaining({ kind: "decimal_reading_match", revisions: 1 }),
		);
		expect(
			decimalReadingResponse([1, 2], { 1: "reading-1", 2: "reading-1" }, [], 0),
		).toBeNull();
		expect(shadingResponse("rectangle", 3, [4, 2, 7], ["toggle"], 0)).toEqual(
			expect.objectContaining({
				selected_part_indices: [2, 4, 7],
				selected_count: 3,
				total_parts: 10,
			}),
		);
		expect(validateSelectedTenths([1, 1])).toBeNull();
	});
	it("enforces one decimal digit and one/two digit fraction cells", () => {
		expect(fractionToDecimalResponse(3, "3", ["tenths:3"])).toEqual(
			expect.objectContaining({ fixed_whole_digit: 0, decimal_value: "0.3" }),
		);
		expect(fractionToDecimalResponse(3, "10", [])).toBeNull();
		expect(
			decimalToFractionResponse(3, "3", "10", ["numerator", "denominator"], []),
		).toEqual(
			expect.objectContaining({
				entered_numerator: 3,
				entered_denominator: 10,
				fraction_bar_present: true,
			}),
		);
		expect(decimalToFractionResponse(3, "3", "100", [], [])).toBeNull();
	});
	it("locates the first incorrect conversion step", () => {
		expect(
			firstIncorrectConversionStep(
				{ numerator: 3, denominator: 10 },
				{ numerator: 2, denominator: 100 },
			),
		).toBe("numerator");
		expect(
			firstIncorrectConversionStep(
				{ numerator: 3, denominator: 10 },
				{ numerator: 3, denominator: 100 },
			),
		).toBe("denominator");
	});
});
