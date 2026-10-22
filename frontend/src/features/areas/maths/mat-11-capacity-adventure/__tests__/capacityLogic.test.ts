import { describe, expect, it } from "vitest";
import {
	canonicalCapacityArithmetic,
	formatCapacity,
	normalizeCapacity,
	portionCounts,
	splitCapacity,
	totalMillilitres,
} from "../capacityLogic";

describe("capacity logic", () => {
	it("uses exact integer millilitres and three-position formatting", () => {
		expect(totalMillilitres(3, 600)).toBe(3600);
		expect(splitCapacity(3600)).toEqual({ litres: 3, millilitres: 600 });
		expect(normalizeCapacity(2, 1750)).toEqual({ litres: 3, millilitres: 750 });
		expect(formatCapacity(3000)).toBe("3 l 000 ml");
	});
	it("counts equivalent one-litre compositions", () => {
		expect(portionCounts([500, 500])).toEqual({ "500": 2 });
		expect(
			[100, 100, 100, 100, 100, 100, 100, 100, 100, 100].reduce(
				(a, b) => a + b,
			),
		).toBe(1000);
	});
	it("adds with regrouping and subtracts with borrowing", () => {
		expect(canonicalCapacityArithmetic("add", 8, 250, 4, 750)).toMatchObject({
			result_litres: 13,
			result_millilitres: 0,
			exchange_used: true,
		});
		expect(
			canonicalCapacityArithmetic("subtract", 14, 600, 5, 750),
		).toMatchObject({
			result_litres: 8,
			result_millilitres: 850,
			exchange_used: true,
		});
	});
});
