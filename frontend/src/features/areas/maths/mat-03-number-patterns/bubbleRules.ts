/**
 * Rules for Nimo's Bubble Trouble (Number Patterns), free of Phaser and React. The server scores
 * every answer; these only read the pattern and build what the child chose.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const PATTERN_AREA_ID = "G5-AREA-MAT-03";
export const PLUS_TWO_SKILL_ID = "G5-MAT-PAT-DIFF-ASC-01";
export const MINUS_TWO_SKILL_ID = "G5-MAT-PAT-DIFF-DESC-01";
export const TIMES_TWO_SKILL_ID = "G5-MAT-PAT-RATIO-2-01";
export const TIMES_FIVE_SKILL_ID = "G5-MAT-PAT-RATIO-5-01";

/** Every pattern can be a Bubble Rush mission. */
export const MISSION_SKILLS = [
	PLUS_TWO_SKILL_ID,
	MINUS_TWO_SKILL_ID,
	TIMES_TWO_SKILL_ID,
	TIMES_FIVE_SKILL_ID,
] as const;

/** A random mission pattern, never the same one twice in a row. */
export function pickMissionSkill(
	previous: string | null,
	random: () => number = Math.random,
): string {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	return choices[Math.floor(random() * choices.length)] ?? PLUS_TWO_SKILL_ID;
}

/**
 * The patterns to try for a new race: a random one first, then the rest (the last race's pattern
 * at the very end), in case the learner has already had every fresh race of the first.
 */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const first = pickMissionSkill(previous, random);
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type Operation = "add" | "subtract" | "multiply";
export type Rule = { operation: Operation; step: number };

/** The octopus's rule bubbles at the start of every race. */
export const GATE_RULES: readonly Rule[] = [
	{ operation: "add", step: 2 },
	{ operation: "subtract", step: 2 },
	{ operation: "multiply", step: 2 },
	{ operation: "multiply", step: 5 },
];

/** Jellyfish magic shells. */
export const SHELL_MULTIPLIERS = [2, 3, 4, 5] as const;

const SIGN: Record<Operation, string> = {
	add: "+",
	subtract: "−",
	multiply: "×",
};

export function ruleLabel(rule: Rule): string {
	return `${SIGN[rule.operation]}${rule.step}`;
}

export function sameRule(left: Rule | null, right: Rule | null): boolean {
	return (
		left !== null &&
		right !== null &&
		left.operation === right.operation &&
		left.step === right.step
	);
}

export function applyRule(rule: Rule, value: number): number {
	if (rule.operation === "multiply") return value * rule.step;
	return rule.operation === "add" ? value + rule.step : value - rule.step;
}

/** One pattern as the server sends it: the terms (`null` for a blank) and the blanks' places. */
export type PatternBoard = {
	terms: Array<number | null>;
	blanks: number[];
	operation: Operation;
};

export function readPattern(
	game: Record<string, unknown> | undefined,
): PatternBoard {
	const raw = Array.isArray(game?.visible_terms) ? game.visible_terms : [];
	const terms = raw.map((value) => (typeof value === "number" ? value : null));
	const listed = Array.isArray(game?.missing_indices)
		? game.missing_indices.filter(
				(value): value is number => typeof value === "number",
			)
		: [];
	const blanks = listed.length
		? listed
		: terms.flatMap((value, index) => (value === null ? [index] : []));
	const operation =
		game?.operation === "subtract" || game?.operation === "multiply"
			? game.operation
			: "add";
	return { terms, blanks, operation };
}

/** The known terms before the first blank (what the child reads to find the rule). */
export function knownTerms(board: PatternBoard): number[] {
	const first = board.blanks[0] ?? board.terms.length;
	return board.terms
		.slice(0, first)
		.filter((value): value is number => value !== null);
}

/**
 * The numbered rings at a junction. They are the same moves for every pattern (+2, −2, ×2, ×5 and
 * "add the last jump again"), so which rings appear never tells the answer. Biggest on top.
 */
export function ringChoices(previous: number, before: number | null): number[] {
	const gap = before === null ? 0 : previous - before;
	const candidates = [
		previous + 2,
		previous - 2,
		previous * 2,
		previous * 5,
		...(gap === 0 ? [] : [previous + gap]),
	];
	return [...new Set(candidates)]
		.filter((value) => value >= 0 && value <= 1000 && value !== previous)
		.sort((a, b) => b - a);
}

/**
 * The response the server scores: the chosen rule and the numbers the child put in the blanks.
 * `null` until every blank has a number.
 */
export function patternResponse(
	rule: Rule | null,
	picks: readonly number[],
	blanks: number,
): ConstructedResponse | null {
	if (!rule || picks.length !== blanks || blanks === 0) return null;
	const completed_terms = [...picks];
	if (rule.operation === "multiply")
		return {
			kind: "constant_ratio_pattern",
			multiplier: rule.step,
			completed_terms,
		};
	return {
		kind: "constant_difference_pattern",
		operation: rule.operation,
		difference: rule.step,
		completed_terms,
	};
}

/**
 * The pattern's rule read from its known terms. Only help games use it: a worked example shows
 * the finished pattern, and a help stage hints at the next number.
 */
export function patternRule(board: PatternBoard): Rule | null {
	const known = knownTerms(board);
	const [first, second] = known;
	if (first === undefined || second === undefined) return null;
	if (board.operation === "multiply" && first !== 0 && second % first === 0)
		return { operation: "multiply", step: second / first };
	const step = second - first;
	if (step > 0) return { operation: "add", step };
	if (step < 0) return { operation: "subtract", step: -step };
	return null;
}

/** The blanks filled in with the pattern's rule (for worked examples and hints). */
export function solvePattern(board: PatternBoard): number[] {
	const rule = patternRule(board);
	if (!rule) return [];
	const filled = [...board.terms];
	for (let index = 0; index < filled.length; index++) {
		const before = filled[index - 1];
		if (filled[index] === null && before !== undefined && before !== null)
			filled[index] = applyRule(rule, before);
	}
	return board.blanks.map((index) => filled[index] ?? 0);
}
