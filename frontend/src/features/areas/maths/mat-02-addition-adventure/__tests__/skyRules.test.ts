import { describe, expect, it } from "vitest";
import {
	cycleCarry,
	emptyLock,
	equationText,
	lockResponse,
	ONES,
	readAddends,
	setCarry,
	setDigit,
	stepDigit,
} from "../skyRules";

describe("Sky Adventure lock rules", () => {
	it("turns digit wheels and carry sparks around", () => {
		expect(stepDigit(null, 1)).toBe(0);
		expect(stepDigit(null, -1)).toBe(9);
		expect(stepDigit(9, 1)).toBe(0);
		expect(stepDigit(0, -1)).toBe(9);
		expect([0, 1, 2].map(cycleCarry)).toEqual([1, 2, 0]);
	});

	it("is not ready until every place but the largest has a digit", () => {
		let lock = emptyLock();
		lock = setDigit(lock, 1, 4);
		lock = setDigit(lock, 2, 0);
		expect(lockResponse(lock)).toBeNull();
		lock = setDigit(lock, ONES, 8);
		expect(lockResponse(lock)).toEqual({
			kind: "regroup_carry",
			total: 408,
			carry_count: 0,
			aligned: true,
		});
	});

	it("builds 382 + 728 + 298 = 1408 with three carried places", () => {
		let lock = emptyLock();
		[1, 4, 0, 8].forEach((digit, place) => {
			lock = setDigit(lock, place, digit);
		});
		lock = setCarry(lock, 0, 1);
		lock = setCarry(lock, 1, 2);
		lock = setCarry(lock, 2, 1);
		expect(lockResponse(lock)).toEqual({
			kind: "regroup_carry",
			total: 1408,
			carry_count: 3,
			aligned: true,
		});
	});

	it("never puts a carry on the ones place", () => {
		expect(setCarry(emptyLock(), ONES, 1).carries).toEqual([0, 0, 0, 0]);
	});

	it("reads only whole, non-negative deliveries", () => {
		expect(readAddends({ addends: [382, 728, 298] })).toEqual([382, 728, 298]);
		expect(readAddends({ addends: [1.5, -2, "3", 40] })).toEqual([40]);
		expect(readAddends({})).toEqual([]);
		expect(readAddends(null)).toEqual([]);
		expect(equationText([382, 728, 298])).toBe("382 + 728 + 298 = ?");
	});
});
