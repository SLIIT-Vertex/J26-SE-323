/**
 * Rules for Nimo's Wacky Sports Carnival (Multiplication), free of React. The server scores every
 * answer; these only read the task and build what the child did.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const CARNIVAL_AREA_ID = "G5-AREA-MAT-06";
export const TABLE_SKILL_ID = "G5-MAT-MUL-TABLE-01";
export const BY_2_3_SKILL_ID = "G5-MAT-MUL-BY-2-3-01";
export const BY_4_6_SKILL_ID = "G5-MAT-MUL-BY-4-6-01";
export const BY_7_10_SKILL_ID = "G5-MAT-MUL-BY-7-10-01";
export const STORY_SKILL_ID = "G5-MAT-MUL-STORY-01";

/** Every race kind: the three written bands and the carnival stories. */
export const MISSION_SKILLS = [
	BY_2_3_SKILL_ID,
	BY_4_6_SKILL_ID,
	BY_7_10_SKILL_ID,
	STORY_SKILL_ID,
] as const;

/**
 * The skills to try for a new race: a random one first (never the last race's), then the rest, in
 * case the learner has already had every fresh race of the first.
 */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first =
		choices[Math.floor(random() * choices.length)] ?? BY_2_3_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type StoryAsset = "lap" | "balloon" | "medal" | "flag";

/** One multiplication task, as the server sends it. */
export type CarnivalTask =
	| { kind: "written"; multiplicand: number; multiplier: number; width: number }
	| { kind: "fact"; multiplicand: number; multiplier: number }
	| { kind: "story"; groupSize: number; groupCount: number; asset: StoryAsset };

const num = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;

export function readTask(
	game: Record<string, unknown> | undefined,
): CarnivalTask {
	if (game?.response_kind === "written_multiplication") {
		const multiplicand = num(game.multiplicand, 100);
		const multiplier = num(game.multiplier, 2);
		return {
			kind: "written",
			multiplicand,
			multiplier,
			width: num(game.blank_count, String(multiplicand * multiplier).length),
		};
	}
	if (game?.response_kind === "multiplication_story") {
		const asset = ["balloon", "medal", "flag"].includes(String(game.asset))
			? (game.asset as StoryAsset)
			: "lap";
		return {
			kind: "story",
			groupSize: num(game.group_size, 2),
			groupCount: num(game.group_count, 2),
			asset,
		};
	}
	return {
		kind: "fact",
		multiplicand: num(game?.multiplicand, 2),
		multiplier: num(game?.multiplier, 2),
	};
}

/** The equal groups of a task: how many groups, and how big each one is. */
export function groupsOf(task: CarnivalTask): { count: number; size: number } {
	if (task.kind === "story")
		return { count: task.groupCount, size: task.groupSize };
	return { count: task.multiplier, size: task.multiplicand };
}

/** How many score wheels the answer needs (a story or a fact product has at most three digits). */
export function wheelCount(task: CarnivalTask): number {
	return task.kind === "written" ? task.width : 3;
}

export function numberFromDigits(digits: readonly number[]): number {
	return digits.reduce((total, digit) => total * 10 + digit, 0);
}

export function digitsOf(value: number, width: number): number[] {
	return String(Math.max(0, value))
		.padStart(width, "0")
		.slice(-width)
		.split("")
		.map(Number);
}

/** The scored answer from the score wheels. */
export function carnivalResponse(
	task: CarnivalTask,
	digits: readonly number[],
): ConstructedResponse {
	const product = numberFromDigits(digits);
	if (task.kind === "written")
		return {
			kind: "written_multiplication",
			multiplicand: task.multiplicand,
			multiplier: task.multiplier,
			result_digits: [...digits],
			product,
		};
	if (task.kind === "story")
		return {
			kind: "multiplication_story",
			group_size: task.groupSize,
			group_count: task.groupCount,
			product,
		};
	return {
		kind: "multiplication_fact",
		multiplicand: task.multiplicand,
		multiplier: task.multiplier,
		product,
	};
}

export type SeatBlock = { place: "hundreds" | "tens" | "ones"; value: number };

/** The multiplicand split into its place blocks (214 → 200, 10, 4), zeros left out. */
export function seatBlocks(multiplicand: number): SeatBlock[] {
	const places = ["hundreds", "tens", "ones"] as const;
	return digitsOf(multiplicand, 3)
		.map((digit, at) => ({
			place: places[at] ?? "ones",
			value: digit * 10 ** (2 - at),
		}))
		.filter((block) => block.value > 0);
}

/** Where a help round is played: written products in the stadium, facts and stories bowling. */
export type CarnivalPlace = "dancing-stadium" | "bowling-buddies";

export function carnivalTrainingPlace(task: CarnivalTask): CarnivalPlace {
	return task.kind === "written" ? "dancing-stadium" : "bowling-buddies";
}

/** The picture for one group of a story. */
export const STORY_EMOJI: Record<StoryAsset, string> = {
	lap: "🏁",
	balloon: "🎈",
	medal: "🏅",
	flag: "🚩",
};
