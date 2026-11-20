/**
 * Rules for Nimo's Galactic Sleepover (Division), free of React. The server scores every answer;
 * these only read the task and turn what the child did into the long-division working.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const SPACE_AREA_ID = "G5-AREA-MAT-08";
export const SHARE_SKILL_ID = "G5-MAT-DIV-SHARE-01";
export const PLAN_SKILL_ID = "G5-MAT-DIV-PLAN-01";
export const WRITTEN_SKILL_ID = "G5-MAT-DIV-WRITTEN-01";
export const REMAINDER_SKILL_ID = "G5-MAT-DIV-REMAINDER-01";
export const STORY_SKILL_ID = "G5-MAT-DIV-STORY-01";

/** Every UFO-boarding kind: long division, with a remainder, and space stories. */
export const MISSION_SKILLS = [
	WRITTEN_SKILL_ID,
	REMAINDER_SKILL_ID,
	STORY_SKILL_ID,
] as const;

/** A random boarding kind first (never the last one's), then the rest as fallbacks. */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first =
		choices[Math.floor(random() * choices.length)] ?? WRITTEN_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type SpaceTask = {
	kind: "share" | "written" | "story";
	dividend: number;
	divisor: number;
	/** Only the first long-division step is asked (the planning skill). */
	traceLimit: number | null;
	storyId: string;
};

const num = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;

export function readTask(game: Record<string, unknown> | undefined): SpaceTask {
	const kind =
		game?.response_kind === "equal_sharing"
			? "share"
			: game?.response_kind === "division_story"
				? "story"
				: "written";
	return {
		kind,
		dividend: num(game?.dividend, 12),
		divisor: Math.max(1, num(game?.divisor, 3)),
		traceLimit: typeof game?.trace_limit === "number" ? game.trace_limit : null,
		storyId: typeof game?.story_id === "string" ? game.story_id : "ufo_groups",
	};
}

export const digitsOf = (value: number) =>
	String(Math.max(0, value)).split("").map(Number);

export type Step = {
	step_index: number;
	partial_dividend: number;
	quotient_digit: number;
	quotient_column: number;
	partial_product: number;
	subtraction_result: number;
	brought_down_digit: number | null;
};

/**
 * The long-division working of what the child did: for each place of the dividend (left to right)
 * the child put `perShip[column]` of that place's bundles in every UFO. The leftover bundles of a
 * place join the next place's (the bring-down). Leading places where nothing was boarded are folded
 * into the next one, as written long division does. Nothing here is corrected.
 */
export function boardingSteps(
	dividend: number,
	divisor: number,
	perShip: readonly number[],
): Step[] {
	const digits = digitsOf(dividend);
	const steps: Step[] = [];
	let current = 0;
	let started = false;
	digits.forEach((digit, column) => {
		current = current * 10 + digit;
		const quotient = perShip[column] ?? 0;
		if (!started && quotient === 0 && column < digits.length - 1) return;
		started = true;
		const product = quotient * divisor;
		const left = current - product;
		steps.push({
			step_index: steps.length,
			partial_dividend: current,
			quotient_digit: quotient,
			quotient_column: column,
			partial_product: product,
			subtraction_result: left,
			brought_down_digit:
				column + 1 < digits.length ? (digits[column + 1] ?? 0) : null,
		});
		current = left;
	});
	return steps;
}

/** The number each UFO gets, read from the per-place digits (0, 3, 1 → 31). */
export const perShipNumber = (perShip: readonly number[]) =>
	perShip.reduce((total, digit) => total * 10 + digit, 0);

function written(task: SpaceTask, perShip: readonly number[]) {
	const all = boardingSteps(task.dividend, task.divisor, perShip);
	const steps = task.traceLimit ? all.slice(0, task.traceLimit) : all;
	const last = steps.at(-1);
	const partOnly = task.traceLimit !== null && task.traceLimit < all.length;
	return {
		dividend: task.dividend,
		divisor: task.divisor,
		working_steps: steps,
		quotient_digits: steps.map((step) => step.quotient_digit),
		partial_dividends: steps.map((step) => step.partial_dividend),
		partial_products: steps.map((step) => step.partial_product),
		subtraction_results: steps.map((step) => step.subtraction_result),
		brought_down_digits: steps.flatMap((step) =>
			step.brought_down_digit === null ? [] : [step.brought_down_digit],
		),
		final_quotient: partOnly
			? (last?.quotient_digit ?? 0)
			: perShipNumber(perShip),
		final_remainder: last?.subtraction_result ?? task.dividend,
	};
}

/** The scored answer of a boarding (UFO boarding or the star splitter). */
export function boardingResponse(
	task: SpaceTask,
	perShip: readonly number[],
): ConstructedResponse {
	const working = written(task, perShip);
	if (task.kind === "story") {
		const quotient = perShipNumber(perShip);
		const remainder = task.dividend - quotient * task.divisor;
		return {
			kind: "division_story",
			problem_id: task.storyId,
			dividend: task.dividend,
			divisor: task.divisor,
			written_working: working,
			quotient,
			remainder,
			contextual_interpretation: `complete_groups:${quotient};leftover:${remainder}`,
		};
	}
	return { kind: "written_division", ...working };
}

/** The scored answer of sharing into beds: each bed's count, and those left with Nimo. */
export function sharingResponse(
	task: SpaceTask,
	beds: readonly number[],
	withNimo: number,
): ConstructedResponse {
	const total = beds.reduce((sum, count) => sum + count, 0);
	const equal = beds.every((count) => count === beds[0]);
	return {
		kind: "equal_sharing",
		dividend: task.dividend,
		divisor: task.divisor,
		group_quantities: [...beds],
		quotient: equal ? (beds[0] ?? 0) : Math.floor(total / task.divisor),
		remainder: withNimo,
	};
}

/** Where a help round is played: sharing into 2 at bedtime, long division at the star splitter. */
export type SpacePlace = "star-splitter" | "alien-bedtime";

export function spaceTrainingPlace(task: SpaceTask): SpacePlace {
	return task.kind === "share" ? "alien-bedtime" : "star-splitter";
}

export const PLACE_NAMES = ["එක", "දහය", "සිය"] as const;
/** The place name of a column of an n-digit number (left to right). */
export const placeName = (column: number, width: number) =>
	PLACE_NAMES[width - 1 - column] ?? "";
