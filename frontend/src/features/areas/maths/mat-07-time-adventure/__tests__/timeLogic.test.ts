import { describe, expect, it } from "vitest";
import { addTime, elapsedTime, from24Hour, normalizeTime, subtractTime, to24Hour } from "../timeLogic";

describe("time adventure logic", () => {
	it("normalises sixty minutes as an hour", () => expect(normalizeTime(3, 80)).toEqual({ hours: 4, minutes: 20 }));
	it("converts midday and midnight correctly", () => {
		expect(to24Hour(12, "am")).toBe(0);
		expect(to24Hour(12, "pm")).toBe(12);
		expect(from24Hour(0)).toEqual({ hour: 12, period: "am" });
	});
	it("calculates elapsed, addition, and regrouped subtraction", () => {
		expect(elapsedTime({ hours: 8, minutes: 10 }, { hours: 11, minutes: 40 })).toEqual({ hours: 3, minutes: 30 });
		expect(addTime({ hours: 3, minutes: 45 }, { hours: 2, minutes: 35 })).toEqual({ hours: 6, minutes: 20 });
		expect(subtractTime({ hours: 6, minutes: 20 }, { hours: 2, minutes: 45 })).toEqual({ hours: 3, minutes: 35 });
	});
});
