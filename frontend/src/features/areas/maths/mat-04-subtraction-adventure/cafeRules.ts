/**
 * Rules for Nimo's Midnight Monster Café (Subtraction), free of React. The server scores every
 * answer; these only read the order and build what the child did.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const CAFE_AREA_ID = "G5-AREA-MAT-04";
export const NO_EXCHANGE_SKILL_ID = "G5-MAT-SUB-NO-REGROUP-01";
export const ONE_EXCHANGE_SKILL_ID = "G5-MAT-C07-L01-O01";
export const TWO_EXCHANGE_SKILL_ID = "G5-MAT-C07-L01-O02";
export const DIFFERENCE_SKILL_ID = "G5-MAT-SUB-DIFF-BETWEEN-01";
export const HOW_MANY_MORE_SKILL_ID = "G5-MAT-SUB-HOW-MANY-MORE-01";

/** Every café order (mission) skill. */
export const MISSION_SKILLS = [
	ONE_EXCHANGE_SKILL_ID,
	TWO_EXCHANGE_SKILL_ID,
	DIFFERENCE_SKILL_ID,
	HOW_MANY_MORE_SKILL_ID,
] as const;

/**
 * The skills to try for a new order: a random one first (never the last order's skill), then the
 * rest, in case the learner has already had every fresh order of the first.
 */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first =
		choices[Math.floor(random() * choices.length)] ?? ONE_EXCHANGE_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type Place = "thousands" | "hundreds" | "tens" | "ones";
export const PLACE_NAMES: Record<Place, string> = {
	thousands: "දහස්",
	hundreds: "සිය",
	tens: "දහය",
	ones: "එක",
};

export type Source = "first" | "second";
export type Quantity = { source: Source; label: string; value: number };
export type Snack = "cupcake" | "cookie" | "donut";

/** One café order as the server sends it. */
export type CafeOrder = {
	places: Place[];
	/** Take-away orders: what the café had and what the monsters ate. */
	minuend: number | null;
	subtrahend: number | null;
	/** Two-monster orders: the two amounts, in the server's order. */
	story: {
		relationship: "difference_between" | "how_many_more";
		quantities: [Quantity, Quantity];
	} | null;
	snack: Snack;
};

const PLACE_ORDER: Place[] = ["thousands", "hundreds", "tens", "ones"];

function isPlace(value: unknown): value is Place {
	return PLACE_ORDER.includes(value as Place);
}

export function readOrder(
	game: Record<string, unknown> | undefined,
): CafeOrder {
	const listed = Array.isArray(game?.places) ? game.places.filter(isPlace) : [];
	const width = typeof game?.width === "number" ? game.width : listed.length;
	const places = listed.length
		? listed
		: PLACE_ORDER.slice(-Math.max(1, width));
	const quantities = Array.isArray(game?.quantities)
		? game.quantities.flatMap((row): Quantity[] => {
				const item = row as Record<string, unknown>;
				const source = item.source === "second" ? "second" : "first";
				return typeof item.value === "number"
					? [{ source, label: String(item.label_si ?? ""), value: item.value }]
					: [];
			})
		: [];
	const relationship =
		game?.relationship === "how_many_more"
			? "how_many_more"
			: "difference_between";
	const story =
		quantities.length === 2 && game?.relationship
			? {
					relationship,
					quantities: [quantities[0], quantities[1]] as [Quantity, Quantity],
				}
			: null;
	const snack =
		game?.asset === "cookie" || game?.asset === "donut"
			? game.asset
			: "cupcake";
	return {
		places,
		minuend: typeof game?.minuend === "number" ? game.minuend : null,
		subtrahend: typeof game?.subtrahend === "number" ? game.subtrahend : null,
		story: story as CafeOrder["story"],
		snack,
	};
}

/** The two numbers on the board: for a two-monster order, the one the child put on top first. */
export function operands(
	order: CafeOrder,
	top: Source | null,
): { top: number; bottom: number } | null {
	if (order.story) {
		if (!top) return null;
		const [first, second] = order.story.quantities;
		const upper = top === first.source ? first : second;
		const lower = upper === first ? second : first;
		return { top: upper.value, bottom: lower.value };
	}
	if (order.minuend === null || order.subtrahend === null) return null;
	return { top: order.minuend, bottom: order.subtrahend };
}

/** The bigger order (help games only: they nudge the child to put it on top). */
export function biggerSource(order: CafeOrder): Source | null {
	if (!order.story) return null;
	const [first, second] = order.story.quantities;
	return first.value >= second.value ? first.source : second.source;
}

export function digitsOf(value: number, width: number): number[] {
	return String(Math.max(0, value))
		.padStart(width, "0")
		.slice(-width)
		.split("")
		.map(Number);
}

/**
 * The top row after opening packs: each open takes one from a column and gives ten to the column on
 * its right. `opens` holds the column indexes (left to right) that were opened.
 */
export function workingDigits(
	top: readonly number[],
	opens: readonly number[],
): number[] {
	const working = [...top];
	for (const column of opens) {
		if (column < 0 || column >= working.length - 1) continue;
		working[column] = (working[column] ?? 0) - 1;
		working[column + 1] = (working[column + 1] ?? 0) + 10;
	}
	return working;
}

/** Whether a column can still be opened (it has a pack left to open). */
export function canOpen(
	top: readonly number[],
	opens: readonly number[],
	column: number,
): boolean {
	if (column < 0 || column >= top.length - 1 || opens.includes(column))
		return false;
	return (workingDigits(top, opens)[column] ?? 0) > 0;
}

/** The exchanges in the order the server lists them: the rightmost column first. */
export function exchangesFor(
	places: readonly Place[],
	opens: readonly number[],
): Array<{
	from_place: Exclude<Place, "ones">;
	to_place: Exclude<Place, "thousands">;
}> {
	return [...opens]
		.filter((column) => column >= 0 && column < places.length - 1)
		.sort((a, b) => b - a)
		.map((column) => ({
			from_place: places[column] as Exclude<Place, "ones">,
			to_place: places[column + 1] as Exclude<Place, "thousands">,
		}));
}

/** The scored answer: `null` until every column has a digit. */
export function cafeResponse(
	order: CafeOrder,
	top: Source | null,
	digits: ReadonlyArray<number | null>,
	opens: readonly number[],
): ConstructedResponse | null {
	if (
		digits.length !== order.places.length ||
		digits.some((digit) => digit === null)
	)
		return null;
	const result_digits = digits as number[];
	if (order.story) {
		if (!top) return null;
		return {
			kind: "difference_story",
			relationship: order.story.relationship,
			minuend_source: top,
			subtrahend_source: top === "first" ? "second" : "first",
			result_digits,
			result: Number(result_digits.join("")),
		};
	}
	return {
		kind: "column_subtraction",
		result_digits,
		exchanges: exchangesFor(order.places, opens),
	};
}

/**
 * The textbook working of `top − bottom`: which columns are opened and the answer digits. Only help
 * games use it, to show a worked example or a faint hint.
 */
export function solveColumns(
	top: number,
	bottom: number,
	width: number,
): { opens: number[]; digits: number[] } {
	const upper = digitsOf(top, width);
	const lower = digitsOf(bottom, width);
	const opens: number[] = [];
	for (let column = width - 1; column > 0; column--) {
		const working = workingDigits(upper, opens);
		if ((working[column] ?? 0) < (lower[column] ?? 0)) opens.push(column - 1);
	}
	return { opens, digits: digitsOf(top - bottom, width) };
}

/** The training place of a help round: Fluffball feeding for the plainest help, else the swap. */
export type CafePlace = "snack-swap" | "fluffball-feast";
const FLUFFBALL_HELP = new Set(["visual_guidance", "simpler_same_game"]);

export function cafeTrainingPlace(
	scaffoldType: string,
	skillId: string,
): CafePlace {
	return FLUFFBALL_HELP.has(scaffoldType) || skillId === NO_EXCHANGE_SKILL_ID
		? "fluffball-feast"
		: "snack-swap";
}
