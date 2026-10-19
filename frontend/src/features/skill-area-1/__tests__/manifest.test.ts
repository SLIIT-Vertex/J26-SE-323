import { describe, expect, it } from "vitest";
import { NUMBER_WORLD_GAMES } from "../manifest";

describe("Number World games", () => {
	it("combines the textbook examples into three games", () => {
		expect(NUMBER_WORLD_GAMES).toHaveLength(3);
		expect(NUMBER_WORLD_GAMES.map((game) => game.skillIds)).toEqual([
			[
				"G5-MAT-NUM-POSITION-01",
				"G5-MAT-NUM-REPRESENTED-01",
				"G5-MAT-NUM-ABACUS-01",
			],
			["G5-MAT-NUM-EXPAND-01", "G5-MAT-NUM-100000-01"],
			[
				"G5-MAT-NUM-EXTREME-01",
				"G5-MAT-NUM-LEADING-ZERO-01",
				"G5-MAT-NUM-ORDER-01",
			],
		]);
	});
});
