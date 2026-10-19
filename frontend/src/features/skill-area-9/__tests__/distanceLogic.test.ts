import { describe, expect, it } from "vitest";
import {
	canonicalDistanceArithmetic,
	formatMetres,
	normalizeDistance,
	splitMetres,
} from "../distanceLogic";
describe("distance logic", () => {
	it("splits metres and preserves formal three-place metres", () => {
		expect(splitMetres(4075)).toEqual({ kilometres: 4, metres: 75 });
		expect(formatMetres(75)).toBe("075");
	});
	it("normalizes every 1000 metres to one kilometre", () =>
		expect(normalizeDistance(3, 1125)).toEqual({ kilometres: 4, metres: 125 }));
	it("builds an exact regrouping addition trace", () => {
		const row = canonicalDistanceArithmetic("add", 3, 650, 2, 475);
		expect(row).toMatchObject({
			carried_or_borrowed_kilometres: 1,
			result_kilometres: 6,
			result_metres: 125,
		});
		expect(row.working_steps).toContain("regroup:1");
	});
	it("builds an exact borrowing subtraction trace", () => {
		const row = canonicalDistanceArithmetic("subtract", 8, 125, 3, 460);
		expect(row).toMatchObject({
			carried_or_borrowed_kilometres: 1,
			result_kilometres: 4,
			result_metres: 665,
		});
		expect(row.working_steps).toContain("metres:1125-460=665");
	});
});
