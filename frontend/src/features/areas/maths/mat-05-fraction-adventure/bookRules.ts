/**
 * Rules for Nimo's Magic Picture Book (Fractions), free of React. The server scores every answer;
 * these only read the page and build what the child did.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const BOOK_AREA_ID = "G5-AREA-MAT-05";
export const HALF_SHAPE_SKILL_ID = "G5-MAT-FRC-HALF-WHOLE-01";
export const HALF_GROUP_SKILL_ID = "G5-MAT-C03-L01-O01";
export const QUARTER_SHAPE_SKILL_ID = "G5-MAT-FRC-QUARTER-WHOLE-01";
export const QUARTER_GROUP_SKILL_ID = "G5-MAT-C03-L01-O02";
export const QUARTER_TABLE_SKILL_ID = "G5-MAT-FRC-QUARTER-TABLE-01";
export const TENTHS_SKILL_ID = "G5-MAT-FRC-TENTHS-BUILD-01";

/** The comic missions: the quarter garden and the tenth panels. */
export const MISSION_SKILLS = [
	QUARTER_TABLE_SKILL_ID,
	TENTHS_SKILL_ID,
] as const;

/** A random comic first, then the other, in case every fresh page of the first was used. */
export function missionOrder(random: () => number = Math.random): string[] {
	const first = random() < 0.5 ? 0 : 1;
	return [MISSION_SKILLS[first], MISSION_SKILLS[1 - first]];
}

/** One page of the book, as the server sends it. */
export type BookPage =
	| { kind: "quarter_table"; total: number }
	| { kind: "tenths"; representation: "strip" | "circle"; numerator: number }
	| {
			kind: "shading";
			representation: "circle" | "rectangle";
			denominator: 2 | 4;
			numerator: number;
	  }
	| { kind: "grouping"; denominator: 2 | 4; total: number };

const number = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;

export function readPage(game: Record<string, unknown> | undefined): BookPage {
	const kind = game?.response_kind;
	if (kind === "fraction_quantity_table")
		return { kind: "quarter_table", total: number(game?.total, 12) };
	if (kind === "equal_grouping")
		return {
			kind: "grouping",
			denominator: game?.denominator === 2 ? 2 : 4,
			total: number(game?.total, 8),
		};
	if (kind === "fraction_shading")
		return {
			kind: "shading",
			representation:
				game?.representation === "circle" ? "circle" : "rectangle",
			denominator: game?.denominator === 2 ? 2 : 4,
			numerator: number(game?.requested_numerator, 1),
		};
	return {
		kind: "tenths",
		representation: game?.representation === "circle" ? "circle" : "strip",
		numerator: number(game?.requested_numerator, 1),
	};
}

/** The fraction a page asks for (the quarter table asks three: 1/4, 2/4 and 3/4). */
export function pageFraction(page: BookPage, step = 0): [number, number] {
	if (page.kind === "quarter_table") return [step + 1, 4];
	if (page.kind === "tenths") return [page.numerator, 10];
	if (page.kind === "shading") return [page.numerator, page.denominator];
	return [1, page.denominator];
}

/** Painted quarter-garden pages → the quarter table (`null` until every page has paint). */
export function tableResponse(
	total: number,
	painted: ReadonlyArray<ReadonlySet<number>>,
): ConstructedResponse | null {
	if (painted.length !== 3 || painted.some((page) => page.size === 0))
		return null;
	return {
		kind: "fraction_quantity_table",
		total,
		quarter_values: painted.map((page) => page.size) as [
			number,
			number,
			number,
		],
	};
}

/** Painted parts of a shape or a tenths picture (`null` before any paint). */
export function partsResponse(
	page: BookPage,
	painted: ReadonlySet<number>,
): ConstructedResponse | null {
	if (painted.size === 0) return null;
	const shaded_indices = [...painted].sort((a, b) => a - b);
	if (page.kind === "tenths")
		return {
			kind: "tenths_representation",
			representation: page.representation,
			numerator: shaded_indices.length,
			denominator: 10,
			shaded_indices,
		};
	if (page.kind === "shading")
		return {
			kind: "fraction_shading",
			representation: page.representation,
			denominator: page.denominator,
			shaded_indices,
		};
	return null;
}

/** Stickers in each envelope → one group number per sticker (-1 for a sticker still on the table). */
export function groupingResponse(
	page: BookPage,
	envelopes: readonly number[],
): ConstructedResponse | null {
	if (page.kind !== "grouping" || envelopes.every((count) => count === 0))
		return null;
	const assignments = envelopes.flatMap((count, group) =>
		Array.from({ length: count }, () => group),
	);
	while (assignments.length < page.total) assignments.push(-1);
	return {
		kind: "equal_grouping",
		denominator: page.denominator,
		assignments: assignments.slice(0, page.total),
	};
}

/** The textbook answer of a page (help games only: worked examples and faint hints). */
export function pageAnswer(page: BookPage): number[] {
	if (page.kind === "quarter_table") {
		const quarter = Math.floor(page.total / 4);
		return [quarter, quarter * 2, quarter * 3];
	}
	if (page.kind === "grouping")
		return [Math.floor(page.total / page.denominator)];
	return [page.numerator];
}

/** Where a help round is played: sharing and the quarter table at the sticker party, else folding. */
export type BookPlace = "sticker-party" | "fold-and-pop";

export function bookTrainingPlace(page: BookPage): BookPlace {
	return page.kind === "grouping" || page.kind === "quarter_table"
		? "sticker-party"
		: "fold-and-pop";
}

/** How many parts a sheet shows: halves, quarters or tenths. */
export function partCount(page: BookPage): number {
	if (page.kind === "tenths") return 10;
	if (page.kind === "shading") return page.denominator;
	return 4;
}

/** Folds needed before the parts appear: one for halves, two for quarters, one accordion for tenths. */
export function foldsNeeded(page: BookPage): number {
	return page.kind === "shading" && page.denominator === 4 ? 2 : 1;
}
