/**
 * Rules for Nimo's Sky Adventure, kept free of Phaser and React so they can be tested directly.
 *
 * The warehouse lock builds a `regroup_carry` response: the child sets one digit per place and
 * marks every place that received a carry. The server alone decides whether it is correct.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const SKY_AREA_ID = "G5-AREA-MAT-02";
/** The city mission: three deliveries added with carrying. */
export const CITY_SKILL_ID = "G5-MAT-C06-L01-O03";

/** Lock columns from the largest place to the smallest, as the backend lists them. */
export const PLACES = ["දහස්", "සිය", "දහය", "එක"] as const;
export const ONES = PLACES.length - 1;
export const CRATE_LABELS = ["A", "B", "C"] as const;

export type Digit = number | null;

export type LockState = {
	/** One digit per place, `null` while the child has not set it. */
	digits: Digit[];
	/** Carries received by each place (0, 1 or 2 with three addends); the ones place has none. */
	carries: number[];
};

export function emptyLock(): LockState {
	return { digits: PLACES.map(() => null), carries: PLACES.map(() => 0) };
}

/** Turn a digit wheel up or down; an unset wheel starts at 0 going up and 9 going down. */
export function stepDigit(digit: Digit, delta: 1 | -1): number {
	if (digit === null) return delta > 0 ? 0 : 9;
	return (digit + delta + 10) % 10;
}

/** Tap a carry spark: none → +1 → +2 → none. */
export function cycleCarry(carry: number): number {
	return (carry + 1) % 3;
}

export function setDigit(
	lock: LockState,
	place: number,
	digit: number,
): LockState {
	return {
		...lock,
		digits: lock.digits.map((value, at) => (at === place ? digit : value)),
	};
}

export function setCarry(
	lock: LockState,
	place: number,
	carry: number,
): LockState {
	if (place === ONES) return lock;
	return {
		...lock,
		carries: lock.carries.map((value, at) => (at === place ? carry : value)),
	};
}

export type LockAction =
	| { type: "digit"; place: number; delta: 1 | -1 }
	| { type: "carry"; place: number };

/** One tap on the lock: turn a digit wheel or a carry spark. */
export function applyLockAction(
	lock: LockState,
	action: LockAction,
): LockState {
	if (action.type === "carry") {
		return setCarry(
			lock,
			action.place,
			cycleCarry(lock.carries[action.place] ?? 0),
		);
	}
	return setDigit(
		lock,
		action.place,
		stepDigit(lock.digits[action.place] ?? null, action.delta),
	);
}

/** The response is ready once every place but the largest has a digit. */
export function lockResponse(lock: LockState): ConstructedResponse | null {
	if (lock.digits.slice(1).some((digit) => digit === null)) return null;
	const total = Number(lock.digits.map((digit) => digit ?? 0).join(""));
	return {
		kind: "regroup_carry",
		total,
		carry_count: lock.carries.filter((carry) => carry > 0).length,
		aligned: true,
	};
}

/** Reads the deliveries from a server manifest; anything malformed yields an empty list. */
export function readAddends(
	game: Record<string, unknown> | undefined | null,
): number[] {
	const addends = game?.addends;
	if (!Array.isArray(addends)) return [];
	return addends.filter(
		(value): value is number =>
			Number.isInteger(value) && value >= 0 && value <= 99_999,
	);
}

export function equationText(addends: readonly number[]): string {
	return `${addends.join(" + ")} = ?`;
}
