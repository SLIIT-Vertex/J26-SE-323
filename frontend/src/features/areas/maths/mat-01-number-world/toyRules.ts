/**
 * Rules for Nimo's Wacky Toybox (Numbers), free of Phaser and React. Every response is checked by
 * the server; these only build what the child made.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const TOY_AREA_ID = "G5-AREA-MAT-01";
export const PARADE_SKILL_ID = "G5-MAT-NUM-ORDER-01";
export const ABACUS_SKILL_ID = "G5-MAT-NUM-ABACUS-01";
export const POSITION_SKILL_ID = "G5-MAT-NUM-POSITION-01";
export const REPRESENTED_SKILL_ID = "G5-MAT-NUM-REPRESENTED-01";

/** The four parade toys, in badge order. */
export const TOYS = ["robot", "dino", "train", "teddy"] as const;
export type Toy = (typeof TOYS)[number];

/** Sinhala place names by power of ten (0 = ones … 5 = hundred-thousands). */
export const PLACE_NAMES = ["එක", "දහය", "සිය", "දහස්", "දස දහස්", "ලක්ෂ"] as const;
/** Place names as costume tags ("ones place" …). */
export const PLACE_TAGS = [
	"එකස්ථානය",
	"දහස්ථානය",
	"සියස්ථානය",
	"දහසස්ථානය",
	"දසදහසස්ථානය",
] as const;

// ---- The parade (ordering) ----

/** Which toy stands in each parade slot (`null` while empty). */
export type ParadeLine = Array<number | null>;

export function emptyLine(count: number): ParadeLine {
	return Array.from({ length: count }, () => null);
}

/**
 * Put a toy in a slot. A toy already in the line moves; a toy already in that slot swaps places
 * with it (or goes back backstage if the moving toy came from backstage).
 */
export function placeToy(
	line: ParadeLine,
	toy: number,
	slot: number,
): ParadeLine {
	if (slot < 0 || slot >= line.length) return line;
	const next = [...line];
	const from = next.indexOf(toy);
	const occupant = next[slot] ?? null;
	if (from !== -1) next[from] = occupant;
	next[slot] = toy;
	return next;
}

/** Send a toy back backstage. */
export function removeToy(line: ParadeLine, toy: number): ParadeLine {
	return line.map((value) => (value === toy ? null : value));
}

export function paradeResponse(
	line: ParadeLine,
	values: readonly number[],
): ConstructedResponse | null {
	if (line.length === 0 || line.some((toy) => toy === null)) return null;
	return {
		kind: "number_order",
		order: line.map((toy) => values[toy as number] as number),
	};
}

// ---- The bead toy (abacus) ----

export const RODS = 6;

/** Beads per rod, from the hundred-thousands rod to the ones rod. */
export function emptyRods(): number[] {
	return Array.from({ length: RODS }, () => 0);
}

export function stepRod(
	rods: readonly number[],
	rod: number,
	delta: 1 | -1,
): number[] {
	return rods.map((beads, at) =>
		at === rod ? Math.min(9, Math.max(0, beads + delta)) : beads,
	);
}

export function numberFromRods(rods: readonly number[]): number {
	return rods.reduce((total, beads) => total * 10 + beads, 0);
}

export function rodsFromNumber(value: number): number[] {
	return String(Math.max(0, Math.min(999_999, Math.trunc(value))))
		.padStart(RODS, "0")
		.split("")
		.map(Number);
}

/** Power of ten of a rod (rod 0 = hundred-thousands). */
export function rodPower(rod: number): number {
	return RODS - 1 - rod;
}

export function beadResponse(rods: readonly number[]): ConstructedResponse {
	return { kind: "bead_placement", rods: [...rods] };
}

// ---- The costume shop (place and value of a digit) ----

export type CostumeQuestion = "position" | "represented";

export function costumeQuestion(skillId: string): CostumeQuestion {
	return skillId === REPRESENTED_SKILL_ID ? "represented" : "position";
}

/** The places a costume rack offers for a number: one per digit, ones first. */
export function costumePlaces(number: number): number[] {
	return Array.from(
		{ length: String(Math.trunc(Math.abs(number))).length },
		(_, power) => power,
	);
}

/** The place of a digit that appears once in the number (the help hint; never sent). */
export function placeOfDigit(number: number, digit: number): number | null {
	const text = String(number);
	const at = text.indexOf(String(digit));
	if (at === -1 || text.lastIndexOf(String(digit)) !== at) return null;
	return text.length - 1 - at;
}

export function costumeValue(digit: number, power: number): number {
	return digit * 10 ** power;
}

export function costumeResponse(
	question: CostumeQuestion,
	digit: number,
	power: number | null,
): ConstructedResponse | null {
	if (power === null) return null;
	return question === "position"
		? { kind: "drag_to_slot", selected_place: power }
		: { kind: "drag_to_slot", represented_value: costumeValue(digit, power) };
}

// ---- Reading the server's item ----

type Game = Record<string, unknown> | null | undefined;

const isWhole = (value: unknown): value is number =>
	typeof value === "number" &&
	Number.isInteger(value) &&
	value >= 0 &&
	value <= 999_999;

export function readParade(game: Game): {
	values: number[];
	ascending: boolean;
} {
	const values = Array.isArray(game?.values) ? game.values.filter(isWhole) : [];
	return { values, ascending: game?.ascending !== false };
}

export function readNumber(game: Game): number {
	return isWhole(game?.number) ? game.number : 0;
}

export function readDigit(game: Game): number {
	return isWhole(game?.digit) && game.digit <= 9 ? game.digit : 0;
}

/** "3 721" with a thin gap, as Sinhala schoolbooks print big numbers. */
export function spaced(value: number): string {
	return value.toLocaleString("en-US").replace(/,/g, " ");
}
