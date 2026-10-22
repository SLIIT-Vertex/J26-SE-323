import { describe, expect, it } from "vitest";
import {
	calculateLineTotals,
	canonicalMoneyArithmetic,
	denominationTotal,
	formatMoney,
	normalizeMoney,
} from "../moneyLogic";

describe("money logic", () => {
	it("formats exact integer cents with two positions", () => {
		expect(formatMoney(16500)).toBe("165.00");
		expect(formatMoney(16505)).toBe("165.05");
		expect(normalizeMoney(165, 125)).toEqual({ rupees: 166, cents: 25 });
	});
	it("supports more than one denomination construction", () => {
		expect(denominationTotal(["note-50", "note-20", "coin-5", "coin-1"])).toBe(7600);
		expect(denominationTotal(Array.from({ length: 76 }, () => "coin-1"))).toBe(7600);
	});
	it("adds with and without carrying", () => {
		expect(canonicalMoneyArithmetic("add", 16520, 24230).exchange_used).toBe(false);
		expect(canonicalMoneyArithmetic("add", 16575, 24250)).toMatchObject({
			cent_subtotal_or_adjustment: 125,
			carried_or_borrowed_rupees: 1,
			result_in_cents: 40825,
		});
	});
	it("subtracts with and without borrowing", () => {
		expect(canonicalMoneyArithmetic("subtract", 50075, 16525).exchange_used).toBe(false);
		expect(canonicalMoneyArithmetic("subtract", 50000, 16575)).toMatchObject({
			carried_or_borrowed_rupees: 1,
			result_in_cents: 33425,
		});
	});
	it("uses integer arithmetic for price times quantity", () => {
		expect(calculateLineTotals([16500, 26000], [2, 1])).toEqual([33000, 26000]);
	});
});
