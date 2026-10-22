import { describe, expect, it } from "vitest";
import {
	arithmeticResponse,
	emojiResponse,
	evaluateRoman,
	intToRoman,
	matchResponse,
	romanToInt,
} from "../romanLogic";

describe("Roman numeral domain logic", () => {
	it("round-trips every canonical value from 1 to 20", () => {
		for (let value = 1; value <= 20; value += 1) {
			expect(romanToInt(intToRoman(value))).toBe(value);
		}
	});

	it.each(["iiii", "viv", "vx", "iix"])("rejects %s", (roman) => {
		expect(() => romanToInt(roman)).toThrow("NONCANONICAL");
	});

	it("builds complete matching, counting and arithmetic evidence", () => {
		expect(
			matchResponse("r", [4], { 4: "iv" }, ["match:4:iv"], 0)?.matches,
		).toEqual([{ arabic_value: 4, selected_roman: "iv" }]);
		expect(
			emojiResponse("g", "star", 3, [0, 1, 2], ["i", "i", "i"], [], 0)
				?.counted_indices,
		).toHaveLength(3);
		expect(
			arithmeticResponse("p", "v", "add", "iv", ["i", "x"], [], 0)?.final_value,
		).toBe(9);
		expect(evaluateRoman("x", "subtract", "v")).toBe(5);
	});
});
