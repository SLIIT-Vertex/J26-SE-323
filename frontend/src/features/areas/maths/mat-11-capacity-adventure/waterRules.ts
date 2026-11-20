/**
 * Rules for Nimo's Water-Play Day (Capacity), free of React. Every amount is whole millilitres. The
 * server scores every answer; these only read the task and turn what the child did into the working.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const WATER_AREA_ID = "G5-AREA-MAT-11";
export const READ_SKILL_ID = "G5-MAT-CAPACITY-READ-01";
export const COMPOSE_SKILL_ID = "G5-MAT-CAPACITY-COMPOSE-01";
export const CONVERT_SKILL_ID = "G5-MAT-CAPACITY-CONVERT-01";
export const ARITHMETIC_SKILL_ID = "G5-MAT-CAPACITY-ARITHMETIC-01";
export const FILL_SKILL_ID = "G5-MAT-CAPACITY-PROBLEM-01";

/** The boat race's two kinds: tank sums (adding or taking away) and filling the channel with jugs. */
export const MISSION_SKILLS = [ARITHMETIC_SKILL_ID, FILL_SKILL_ID] as const;

/** A random race kind first (never the last one's), then the other as a fallback. */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first =
		choices[Math.floor(random() * choices.length)] ?? ARITHMETIC_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type WaterTask = {
	kind: "read" | "compose" | "convert" | "add" | "subtract" | "fill";
	/** Adding or taking away: the two amounts. */
	left: number;
	right: number;
	/** Reading: the mark to reach. Making: the balloon's amount. Filling: the amount asked for. */
	target: number;
	/** Reading: where the water starts. */
	start: number;
	/** The jugs that can be poured (making and filling). */
	jugs: number[];
	/** Changing into litres: the millilitres given. */
	source: number;
	sourceLitres: number;
	missionId: string;
};

const num = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;
const nums = (value: unknown, fallback: number[]) =>
	Array.isArray(value)
		? value.filter((item): item is number => typeof item === "number")
		: fallback;

export function readTask(game: Record<string, unknown> | undefined): WaterTask {
	const responseKind = game?.response_kind;
	const kind =
		responseKind === "vessel_reading"
			? "read"
			: responseKind === "capacity_composition"
				? "compose"
				: responseKind === "capacity_conversion"
					? "convert"
					: responseKind === "capacity_delivery"
						? "fill"
						: game?.operation === "subtract"
							? "subtract"
							: "add";
	const ml = (litres: unknown, millilitres: unknown) =>
		num(litres, 0) * 1000 + num(millilitres, 0);
	return {
		kind,
		left: ml(game?.left_litres, game?.left_millilitres),
		right: ml(game?.right_litres, game?.right_millilitres),
		target: num(
			game?.capacity_ml ?? game?.target_ml ?? game?.requested_total_ml,
			1000,
		),
		start: num(game?.start_level_ml, 100),
		jugs: nums(
			game?.available_portions_ml ?? game?.available_containers_ml,
			[100, 250, 500, 1000],
		),
		source: num(game?.source_total_ml, 0),
		sourceLitres: num(game?.source_litres, 0),
		missionId:
			typeof game?.mission_id === "string" ? game.mission_id : "delivery",
	};
}

export const litresOf = (ml: number) => Math.floor(ml / 1000);
export const restOf = (ml: number) => ml % 1000;

/** "2 l 250 ml", "2 l" or "600 ml", as a child reads it. */
export function waterText(ml: number): string {
	const litres = litresOf(ml);
	const rest = restOf(ml);
	if (!litres) return `${rest} ml`;
	return rest ? `${litres} l ${rest} ml` : `${litres} l`;
}

/**
 * What the child did on a litres-and-millilitres board, column by column:
 * - adding: `ml` is the millilitres added up (it may pass 1000), `exchanged` whether 1000 ml went
 *   over as 1 l, `litres` the litres the child wrote;
 * - taking away: `exchanged` whether 1 l was opened into 1000 ml first, `ml` the millilitres
 *   left, `litres` the litres left.
 * Nothing here is corrected.
 */
export type Working = {
	operation: "add" | "subtract";
	ml: number;
	exchanged: boolean;
	litres: number;
};

export function arithmeticResponse(
	task: WaterTask,
	working: Working,
): ConstructedResponse {
	const leftLitres = litresOf(task.left);
	const leftMl = restOf(task.left);
	const rightLitres = litresOf(task.right);
	const rightMl = restOf(task.right);
	const carry = working.exchanged ? 1 : 0;
	const shared = {
		kind: "capacity_arithmetic" as const,
		operation: working.operation,
		left_litres: leftLitres,
		left_millilitres: leftMl,
		right_litres: rightLitres,
		right_millilitres: rightMl,
		carried_or_borrowed_litres: carry,
		exchange_used: working.exchanged,
		result_litres: working.litres,
	};
	if (working.operation === "add") {
		const resultMl = Math.max(0, working.ml - 1000 * carry);
		return {
			...shared,
			millilitre_subtotal_or_adjustment: working.ml,
			working_steps: [
				`ml:${leftMl}+${rightMl}=${working.ml}`,
				`carry:${carry}`,
				`ml-result:${resultMl}`,
				`litres:${leftLitres}+${rightLitres}+${carry}=${working.litres}`,
			],
			result_millilitres: resultMl,
		};
	}
	const adjusted = leftMl + 1000 * carry;
	return {
		...shared,
		millilitre_subtotal_or_adjustment: adjusted,
		working_steps: [
			`borrow:${carry}`,
			`adjust:${leftLitres}->${leftLitres - carry}:${leftMl}->${adjusted}`,
			`ml:${adjusted}-${rightMl}=${working.ml}`,
			`litres:${leftLitres - carry}-${rightLitres}=${working.litres}`,
		],
		result_millilitres: working.ml,
	};
}

/** The right working of a tank sum (worked examples and the fountain's finished pool). */
export function solvedWorking(task: WaterTask): Working {
	if (task.kind === "subtract") {
		const exchanged = restOf(task.left) < restOf(task.right);
		return {
			operation: "subtract",
			exchanged,
			ml: restOf(task.left) + (exchanged ? 1000 : 0) - restOf(task.right),
			litres: litresOf(task.left) - (exchanged ? 1 : 0) - litresOf(task.right),
		};
	}
	const ml = restOf(task.left) + restOf(task.right);
	const exchanged = ml >= 1000;
	return {
		operation: "add",
		ml,
		exchanged,
		litres: litresOf(task.left) + litresOf(task.right) + (exchanged ? 1 : 0),
	};
}

/** The scored answer of filling with jugs: every jug poured, and what it came to. */
export function fillResponse(
	task: WaterTask,
	poured: readonly number[],
): ConstructedResponse {
	const total = poured.reduce((sum, jug) => sum + jug, 0);
	return {
		kind: "capacity_delivery",
		mission_id: task.missionId,
		requested_total_ml: task.target,
		selected_containers_ml: [...poured],
		delivered_total_ml: total,
		working_steps: [
			...poured.map((jug) => `portion:${jug}`),
			`total:${total}`,
			`convert:${total}=${litresOf(total)}:${restOf(total)}`,
		],
		result_litres: litresOf(total),
		result_millilitres: restOf(total),
		remaining_or_overflow_ml: Math.abs(task.target - total),
		contextual_answer: `delivered:${total}`,
	};
}

/** The scored answer of pouring millilitres into litre bottles. */
export function convertResponse(
	task: WaterTask,
	bottles: number,
	left: number,
): ConstructedResponse {
	return {
		kind: "capacity_conversion",
		source_litres: task.sourceLitres,
		source_millilitres: task.source - task.sourceLitres * 1000,
		source_total_ml: task.source,
		result_litres: bottles,
		result_millilitres: left,
		exchange_count: bottles,
	};
}

/** The scored answer of filling a balloon from jugs. */
export function composeResponse(
	task: WaterTask,
	poured: readonly number[],
): ConstructedResponse {
	const total = poured.reduce((sum, jug) => sum + jug, 0);
	const counts: Record<string, number> = {};
	for (const jug of [...poured].sort((a, b) => a - b))
		counts[String(jug)] = (counts[String(jug)] ?? 0) + 1;
	return {
		kind: "capacity_composition",
		target_ml: task.target,
		selected_portions_ml: [...poured],
		portion_counts: counts,
		constructed_total_ml: total,
		overflow_ml: Math.max(0, total - task.target),
	};
}

/** The scored answer of reading a jug: every level the water went through, and the mark chosen. */
export function readResponse(
	task: WaterTask,
	levels: readonly number[],
	level: number,
	mark: number,
): ConstructedResponse {
	return {
		kind: "vessel_reading",
		capacity_ml: task.target,
		selected_tick_ml: mark,
		liquid_level_ml: level,
		adjustment_actions: [...levels],
	};
}

/** Where a help round is played: litres and millilitres at the fountain, small jugs at the balloons. */
export type WaterPlace = "dancing-fountain" | "water-balloons";

export function waterTrainingPlace(task: WaterTask): WaterPlace {
	return task.kind === "read" || task.kind === "compose"
		? "water-balloons"
		: "dancing-fountain";
}
