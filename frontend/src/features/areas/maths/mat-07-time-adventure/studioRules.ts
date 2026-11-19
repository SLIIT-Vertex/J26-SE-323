/**
 * Rules for Nimo's Silly Movie Studio (Time), free of React. The server scores every answer; these
 * only read the scene and build what the child did. Time runs in groups of 60 minutes.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const STUDIO_AREA_ID = "G5-AREA-MAT-07";
export const UNITS_SKILL_ID = "G5-MAT-TIME-UNITS-01";
export const CLOCK_SKILL_ID = "G5-MAT-TIME-ANALOG-01";
export const CONVERT_SKILL_ID = "G5-MAT-TIME-24H-01";
export const ELAPSED_SKILL_ID = "G5-MAT-TIME-ELAPSED-01";
export const ARITHMETIC_SKILL_ID = "G5-MAT-TIME-ARITHMETIC-01";

/** Every movie-scene kind: how long a scene took, 24-hour time and adding or taking durations. */
export const MISSION_SKILLS = [
	ELAPSED_SKILL_ID,
	CONVERT_SKILL_ID,
	ARITHMETIC_SKILL_ID,
] as const;

/** A random scene kind first (never the last scene's), then the rest as fallbacks. */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first =
		choices[Math.floor(random() * choices.length)] ?? ELAPSED_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type Clock = { hours: number; minutes: number };
export type UnitPair = [number, string];

export type StudioTask =
	| { kind: "elapsed"; start: Clock; end: Clock }
	| { kind: "convert"; hour: number; minute: number; period: "am" | "pm" }
	| { kind: "arith"; operation: "add" | "subtract"; left: Clock; right: Clock }
	| { kind: "clock"; hour: number; minute: number }
	| { kind: "units"; left: UnitPair[]; right: UnitPair[] };

const num = (value: unknown, fallback = 0) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;

const pairs = (value: unknown): UnitPair[] =>
	Array.isArray(value)
		? value.map((row) => [
				num((row as unknown[])[0]),
				String((row as unknown[])[1] ?? ""),
			])
		: [];

export function readTask(
	game: Record<string, unknown> | undefined,
): StudioTask {
	const kind = game?.response_kind;
	if (kind === "elapsed_time")
		return {
			kind: "elapsed",
			start: { hours: num(game?.start_hour), minutes: num(game?.start_minute) },
			end: { hours: num(game?.end_hour), minutes: num(game?.end_minute) },
		};
	if (kind === "time_conversion")
		return {
			kind: "convert",
			hour: num(game?.source_hour, 12),
			minute: num(game?.source_minute),
			period: game?.period === "am" ? "am" : "pm",
		};
	if (kind === "time_arithmetic")
		return {
			kind: "arith",
			operation: game?.operation === "subtract" ? "subtract" : "add",
			left: { hours: num(game?.left_hours), minutes: num(game?.left_minutes) },
			right: {
				hours: num(game?.right_hours),
				minutes: num(game?.right_minutes),
			},
		};
	if (kind === "time_unit_match")
		return {
			kind: "units",
			left: pairs(game?.left_options),
			right: pairs(game?.right_options),
		};
	return {
		kind: "clock",
		hour: num(game?.target_hour, 12),
		minute: num(game?.target_minute),
	};
}

export const toMinutes = (clock: Clock) => clock.hours * 60 + clock.minutes;

/** Minutes → hours and minutes: every 60 minutes is one hour. */
export function fromMinutes(total: number): Clock {
	const safe = Math.max(0, Math.round(total));
	return { hours: Math.floor(safe / 60), minutes: safe % 60 };
}

export const pad = (value: number) => String(value).padStart(2, "0");
export const clockText = (clock: Clock) =>
	`${pad(clock.hours)}:${pad(clock.minutes)}`;

/** A duration in words: "පැය 1 මිනිත්තු 10". */
export function durationText(clock: Clock): string {
	if (clock.hours === 0) return `මිනිත්තු ${clock.minutes}`;
	if (clock.minutes === 0) return `පැය ${clock.hours}`;
	return `පැය ${clock.hours} මිනිත්තු ${clock.minutes}`;
}

/** 12-hour time as the call sheet writes it: "1.30 ප.ව.". */
export function periodText(
	hour: number,
	minute: number,
	period: "am" | "pm",
): string {
	return `${hour}.${pad(minute)} ${period === "am" ? "පෙ.ව." : "ප.ව."}`;
}

export function to24(hour: number, period: "am" | "pm"): number {
	if (period === "am") return hour === 12 ? 0 : hour;
	return hour === 12 ? 12 : hour + 12;
}

/** The answer a duration task wants (help games only: worked examples and faint hints). */
export function durationAnswer(task: StudioTask): Clock | null {
	if (task.kind === "elapsed")
		return fromMinutes(toMinutes(task.end) - toMinutes(task.start));
	if (task.kind === "arith")
		return fromMinutes(
			task.operation === "add"
				? toMinutes(task.left) + toMinutes(task.right)
				: toMinutes(task.left) - toMinutes(task.right),
		);
	return null;
}

/** A duration answer. Minutes over 59 are always written as hours, as the server expects. */
export function durationResponse(
	task: StudioTask,
	total: number,
	exchanged: boolean,
): ConstructedResponse | null {
	const { hours, minutes } = fromMinutes(total);
	if (task.kind === "elapsed")
		return { kind: "elapsed_time", hours: Math.min(hours, 23), minutes };
	if (task.kind === "arith")
		return {
			kind: "time_arithmetic",
			hours: Math.min(hours, 23),
			minutes,
			regrouped: exchanged,
		};
	return null;
}

export function clockResponse(
	hour: number,
	minute: number,
): ConstructedResponse {
	return { kind: "analog_clock", hour, minute };
}

export function conversionResponse(
	hour24: number,
	minute: number,
): ConstructedResponse {
	return { kind: "time_conversion", hour24, minute };
}

export function unitsResponse(matches: readonly number[]): ConstructedResponse {
	return { kind: "time_unit_match", matches: [...matches] };
}

export const UNIT_NAMES: Record<string, string> = {
	seconds: "තත්පර",
	minutes: "මිනිත්තු",
	hours: "පැය",
	days: "දින",
	weeks: "සති",
	months: "මාස",
	years: "අවුරුදු",
	ordinary_years: "සාමාන්‍ය අවුරුදු",
	leap_years: "අධික අවුරුදු",
};

export const unitText = ([count, unit]: UnitPair) =>
	`${UNIT_NAMES[unit] ?? unit} ${count}`;

/** Where a help round is played: durations in the editing room, clocks and units at the puppets. */
export type StudioPlace = "fast-forward" | "puppet-show";

export function studioTrainingPlace(task: StudioTask): StudioPlace {
	return task.kind === "elapsed" || task.kind === "arith"
		? "fast-forward"
		: "puppet-show";
}

// ---- The film: a scene's length as pieces (an hour reel, 10- and 5-minute strips) ----

export type Piece = 60 | 10 | 5;

export const filmMinutes = (pieces: readonly Piece[]) =>
	pieces.reduce((sum, piece) => sum + piece, 0);

/** Hour reels first, then 10s, then 5s: the tidy way a length is laid out. */
export function sortFilm(pieces: readonly Piece[]): Piece[] {
	return [...pieces].sort((a, b) => b - a);
}

/** A length laid out as pieces (2 h 25 → 60, 60, 10, 10, 5). */
export function layFilm(minutes: number): Piece[] {
	const pieces: Piece[] = [];
	let rest = Math.max(0, minutes);
	while (rest >= 60) {
		pieces.push(60);
		rest -= 60;
	}
	while (rest >= 10) {
		pieces.push(10);
		rest -= 10;
	}
	while (rest >= 5) {
		pieces.push(5);
		rest -= 5;
	}
	return pieces;
}

/**
 * Add a piece. When the minute strips reach 60 minutes they snap together into one hour reel
 * (60 minutes = 1 hour); `merged` says whether that happened.
 */
export function addPiece(
	pieces: readonly Piece[],
	piece: Piece,
): { pieces: Piece[]; merged: boolean } {
	const next = [...pieces, piece];
	const minuteStrips = next.filter((part) => part !== 60);
	if (filmMinutes(minuteStrips) < 60) return { pieces: next, merged: false };
	let taken = 0;
	const left: Piece[] = [];
	for (const part of sortFilm(minuteStrips)) {
		if (taken + part <= 60 && taken < 60) taken += part;
		else left.push(part);
	}
	return {
		pieces: sortFilm([...next.filter((part) => part === 60), 60, ...left]),
		merged: true,
	};
}

/** Snip one hour reel into six 10-minute strips (1 hour = 60 minutes). */
export function snipHour(pieces: readonly Piece[]): Piece[] {
	const at = pieces.indexOf(60);
	if (at === -1) return [...pieces];
	return sortFilm([
		...pieces.slice(0, at),
		...pieces.slice(at + 1),
		10,
		10,
		10,
		10,
		10,
		10,
	]);
}

/** Snip one 10-minute strip into two 5-minute strips. */
export function snipTen(pieces: readonly Piece[]): Piece[] {
	const at = pieces.indexOf(10);
	if (at === -1) return [...pieces];
	return sortFilm([...pieces.slice(0, at), ...pieces.slice(at + 1), 5, 5]);
}
