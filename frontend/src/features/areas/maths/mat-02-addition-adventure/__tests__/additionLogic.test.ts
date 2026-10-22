import { describe, expect, it } from "vitest";
import {
	carryingCount,
	cumulativeTotals,
	expandedTerms,
	maximumRowIndex,
	placeColumns,
	selectedTableTotal,
	tableRowTotals,
	isValidRegrouping,
	isValidRunningTotals,
	sameCellSelection,
} from "../additionLogic";

describe("addition adventure arithmetic", () => {
	it("counts decimal exchanges rather than just columns over nine", () => {
		expect(carryingCount([999, 2])).toBe(3);
		expect(carryingCount([1234, 1111])).toBe(0);
	});

	it("keeps running totals and table cell selection deterministic", () => {
		expect(cumulativeTotals([12, 18, 30])).toEqual([12, 30, 60]);
		expect(cumulativeTotals([27, 12, 20], 82)).toEqual([109, 121, 141]);
		expect(
			selectedTableTotal(
				[
					[10, 20],
					[30, 40],
				],
				[
					[0, 1],
					[1, 1],
				],
			),
		).toBe(60);
	});

	it("derives textbook expanded form and row comparisons", () => {
		expect(expandedTerms(4205)).toEqual([4000, 200, 5]);
		const rows = [
			[281, 288, 304],
			[344, 306, 296],
			[297, 311, 310],
		];
		expect(tableRowTotals(rows)).toEqual([873, 946, 918]);
		expect(maximumRowIndex(rows)).toBe(1);
	});

	it("aligns all values to the same four place-value columns", () => {
		expect(placeColumns([4205, 37])).toEqual([
			[4, 2, 0, 5],
			[0, 0, 3, 7],
		]);
	});

	it("validates running totals, manual carries, and selected evidence cells", () => {
		expect(isValidRunningTotals([12, 18, 30], [12, 30, 60])).toBe(true);
		expect(isValidRegrouping([999, 2], 1001, 3)).toBe(true);
		expect(sameCellSelection(["r0c1", "r1c1"], ["r1c1", "r0c1"])).toBe(true);
	});
});
