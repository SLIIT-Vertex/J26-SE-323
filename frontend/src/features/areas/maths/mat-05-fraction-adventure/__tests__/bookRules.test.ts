import { describe, expect, it } from "vitest";
import {
	bookTrainingPlace,
	foldsNeeded,
	groupingResponse,
	MISSION_SKILLS,
	missionOrder,
	pageAnswer,
	pageFraction,
	partsResponse,
	readPage,
	tableResponse,
} from "../bookRules";
import { gardenColumns } from "../ColorSplashComic";

const GARDEN = readPage({
	response_kind: "fraction_quantity_table",
	total: 12,
});
const PANELS = readPage({
	response_kind: "tenths_representation",
	representation: "strip",
	requested_numerator: 4,
});
const SHAPE = readPage({
	response_kind: "fraction_shading",
	representation: "circle",
	denominator: 4,
	requested_numerator: 1,
});
const SHARE = readPage({
	response_kind: "equal_grouping",
	denominator: 4,
	total: 12,
});

describe("Picture book rules", () => {
	it("reads every kind of page and the fraction it asks for", () => {
		expect(GARDEN).toEqual({ kind: "quarter_table", total: 12 });
		expect([0, 1, 2].map((step) => pageFraction(GARDEN, step))).toEqual([
			[1, 4],
			[2, 4],
			[3, 4],
		]);
		expect(pageFraction(PANELS)).toEqual([4, 10]);
		expect(pageFraction(SHAPE)).toEqual([1, 4]);
		expect(pageAnswer(GARDEN)).toEqual([3, 6, 9]);
		expect(pageAnswer(SHARE)).toEqual([3]);
	});

	it("turns the three garden pages into the quarter table once each page has paint", () => {
		const pages = [
			new Set([0, 1, 2]),
			new Set([0, 1, 2, 3, 4, 5]),
			new Set<number>(),
		];
		expect(tableResponse(12, pages)).toBeNull();
		pages[2] = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8]);
		expect(tableResponse(12, pages)).toEqual({
			kind: "fraction_quantity_table",
			total: 12,
			quarter_values: [3, 6, 9],
		});
	});

	it("answers painted parts of tenths and shapes in index order", () => {
		expect(partsResponse(PANELS, new Set())).toBeNull();
		expect(partsResponse(PANELS, new Set([7, 1, 3, 0]))).toEqual({
			kind: "tenths_representation",
			representation: "strip",
			numerator: 4,
			denominator: 10,
			shaded_indices: [0, 1, 3, 7],
		});
		expect(partsResponse(SHAPE, new Set([2]))).toEqual({
			kind: "fraction_shading",
			representation: "circle",
			denominator: 4,
			shaded_indices: [2],
		});
	});

	it("shares stickers as one group per sticker, -1 for those still on the table", () => {
		expect(groupingResponse(SHARE, [0, 0, 0, 0])).toBeNull();
		expect(groupingResponse(SHARE, [3, 3, 2, 3])).toEqual({
			kind: "equal_grouping",
			denominator: 4,
			assignments: [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, -1],
		});
	});

	it("sends sharing and the quarter table to the stickers, shapes and tenths to folding", () => {
		expect(bookTrainingPlace(GARDEN)).toBe("sticker-party");
		expect(bookTrainingPlace(SHARE)).toBe("sticker-party");
		expect(bookTrainingPlace(PANELS)).toBe("fold-and-pop");
		expect(bookTrainingPlace(SHAPE)).toBe("fold-and-pop");
		expect(foldsNeeded(SHAPE)).toBe(2);
		expect(foldsNeeded(PANELS)).toBe(1);
	});

	it("picks a random comic first and keeps the other as a fallback", () => {
		expect(missionOrder(() => 0)).toEqual([...MISSION_SKILLS]);
		expect(missionOrder(() => 0.9)).toEqual([
			MISSION_SKILLS[1],
			MISSION_SKILLS[0],
		]);
	});

	it("never lays the garden out in rows that show a half or a quarter", () => {
		for (const total of [8, 12, 16, 20, 24]) {
			expect(total % gardenColumns(total)).not.toBe(0);
			expect(gardenColumns(total)).toBeLessThanOrEqual(7);
		}
	});
});
