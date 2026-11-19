/**
 * Rules for the Number Factory, free of Phaser and React.
 *
 * Places are indexed by power of ten (0 = ones). The child feeds each number into the machine,
 * which drops its digits into the place columns as blocks, then pulls a lever under a column to
 * bundle ten blocks into one block of the next place. Every bundled column is one carry; the
 * output wheels give the total. The server alone decides whether the answer is correct.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

/** Sinhala place names by power of ten. */
export const PLACE_NAME_BY_POWER = [
	"එක",
	"දහය",
	"සිය",
	"දහස්",
	"දස දහස්",
] as const;
export const MAX_PLACES = PLACE_NAME_BY_POWER.length;

export type FactoryState = {
	places: number;
	/** Blocks in each place, by power of ten. */
	counts: number[];
	/** Whether each number has been fed into the machine. */
	fed: boolean[];
	/** Bundles made from each place, by power of ten. */
	bundled: number[];
};

export function digitOf(value: number, power: number): number {
	return Math.floor(value / 10 ** power) % 10;
}

/** Enough places for every number and their total, and at least hundreds/tens/ones. */
export function placesFor(addends: readonly number[]): number {
	const total = addends.reduce((sum, value) => sum + value, 0);
	return Math.min(MAX_PLACES, Math.max(3, String(total).length));
}

export function emptyFactory(addends: readonly number[]): FactoryState {
	const places = placesFor(addends);
	return {
		places,
		counts: Array.from({ length: places }, () => 0),
		fed: addends.map(() => false),
		bundled: Array.from({ length: places }, () => 0),
	};
}

export function feed(
	state: FactoryState,
	addends: readonly number[],
	index: number,
): FactoryState {
	const value = addends[index];
	if (value === undefined || state.fed[index]) return state;
	return {
		...state,
		counts: state.counts.map((count, power) => count + digitOf(value, power)),
		fed: state.fed.map((done, at) => done || at === index),
	};
}

export function allFed(state: FactoryState): boolean {
	return state.fed.every(Boolean);
}

/** Ten blocks of a place, and a next place to send the bundle to. */
export function canBundle(state: FactoryState, power: number): boolean {
	return power < state.places - 1 && (state.counts[power] ?? 0) >= 10;
}

export function bundle(state: FactoryState, power: number): FactoryState {
	if (!canBundle(state, power)) return state;
	return {
		...state,
		counts: state.counts.map((count, at) =>
			at === power ? count - 10 : at === power + 1 ? count + 1 : count,
		),
		bundled: state.bundled.map((made, at) => (at === power ? made + 1 : made)),
	};
}

/** The machine with every number fed and every full place bundled: a worked example. */
export function solveFactory(addends: readonly number[]): FactoryState {
	let state = emptyFactory(addends);
	addends.forEach((_, index) => {
		state = feed(state, addends, index);
	});
	for (let power = 0; power < state.places - 1; power++) {
		while (canBundle(state, power)) state = bundle(state, power);
	}
	return state;
}

/** The digits of a number by power of ten, padded to `places`. */
export function digitsByPower(value: number, places: number): number[] {
	return Array.from({ length: places }, (_, power) => digitOf(value, power));
}

/**
 * The machine's answer once every number is in and every place but the largest has an output
 * digit. Carries are the places the child bundled.
 */
export function factoryResponse(
	state: FactoryState,
	output: Array<number | null>,
): ConstructedResponse | null {
	if (!allFed(state)) return null;
	if (output.slice(0, state.places - 1).some((digit) => digit === null))
		return null;
	const total = output.reduce<number>(
		(sum, digit, power) => sum + (digit ?? 0) * 10 ** power,
		0,
	);
	return {
		kind: "regroup_carry",
		total,
		carry_count: state.bundled.filter((made) => made > 0).length,
		aligned: true,
	};
}
