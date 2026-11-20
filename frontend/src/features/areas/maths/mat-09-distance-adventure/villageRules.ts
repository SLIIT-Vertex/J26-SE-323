/**
 * Rules for Nimo's Village Walk (Length and distance), free of React. The server scores every
 * answer; these only read the task and turn what the child did into the distance working.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const VILLAGE_AREA_ID = "G5-AREA-MAT-09";
export const RELATION_SKILL_ID = "G5-MAT-LENGTH-RELATION-01";
export const CONVERT_SKILL_ID = "G5-MAT-LENGTH-CONVERT-01";
export const ADD_SKILL_ID = "G5-MAT-LENGTH-ADD-01";
export const SUBTRACT_SKILL_ID = "G5-MAT-LENGTH-SUBTRACT-01";
export const STORY_SKILL_ID = "G5-MAT-LENGTH-PROBLEM-01";

/** Every road-to-the-market kind: joining roads, the distance still to go, and village stories. */
export const MISSION_SKILLS = [
	ADD_SKILL_ID,
	SUBTRACT_SKILL_ID,
	STORY_SKILL_ID,
] as const;

/** A random road kind first (never the last one's), then the rest as fallbacks. */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first = choices[Math.floor(random() * choices.length)] ?? ADD_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type Operation = "add" | "subtract";
export type Distance = { km: number; m: number };

export type VillageTask = {
	kind: "relation" | "convert" | "arithmetic" | "story";
	/** The operation the item asks for (a story's child still chooses it). */
	operation: Operation;
	left: Distance;
	right: Distance;
	/** The metres to build (conversion). */
	total: number;
	storyId: string;
};

const num = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;

export function readTask(
	game: Record<string, unknown> | undefined,
): VillageTask {
	const responseKind = game?.response_kind;
	const kind =
		responseKind === "unit_relationship"
			? "relation"
			: responseKind === "distance_conversion"
				? "convert"
				: responseKind === "distance_story"
					? "story"
					: "arithmetic";
	return {
		kind,
		operation: game?.operation === "subtract" ? "subtract" : "add",
		left: { km: num(game?.left_kilometres, 0), m: num(game?.left_metres, 0) },
		right: {
			km: num(game?.right_kilometres, 0),
			m: num(game?.right_metres, 0),
		},
		total: num(game?.source_value, 2200),
		storyId:
			typeof game?.problem_id === "string" ? game.problem_id : "route_distance",
	};
}

/** "3 km 650 m" */
export const distanceText = ({ km, m }: Distance) => `${km} km ${m} m`;

/**
 * What the child did on a distance board, column by column:
 * - adding: `metres` is the metres total the child made (it may pass 1000), `exchanged` is
 *   whether 1000 m was carried over as 1 km, `km` the kilometres the child wrote;
 * - subtracting: `exchanged` is whether 1 km was opened into 1000 m first, `metres` the metres
 *   left, `km` the kilometres left.
 * Nothing here is corrected.
 */
export type Working = {
	operation: Operation;
	metres: number;
	exchanged: boolean;
	km: number;
};

/** The metres that end up in the answer. */
export const resultMetres = (working: Working) =>
	working.operation === "add" && working.exchanged
		? working.metres - 1000
		: working.metres;

function arithmetic(task: VillageTask, working: Working) {
	const { left, right } = task;
	const carry = working.exchanged ? 1 : 0;
	const steps =
		working.operation === "add"
			? [
					`metres:${left.m}+${right.m}=${working.metres}`,
					`regroup:${carry}`,
					`kilometres:${left.km}+${right.km}+${carry}=${working.km}`,
				]
			: [
					`borrow:${carry}`,
					`metres:${left.m + 1000 * carry}-${right.m}=${working.metres}`,
					`kilometres:${left.km - carry}-${right.km}=${working.km}`,
				];
	return {
		kind: "distance_arithmetic" as const,
		left_kilometres: left.km,
		left_metres: left.m,
		right_kilometres: right.km,
		right_metres: right.m,
		operation: working.operation,
		metre_subtotal_or_adjustment: working.metres,
		exchange_or_regrouping_used: working.exchanged,
		carried_or_borrowed_kilometres: carry,
		result_kilometres: working.km,
		result_metres: resultMetres(working),
		working_steps: steps,
	};
}

/** The scored answer of a road sum (the market board or the toy road). */
export function roadResponse(
	task: VillageTask,
	working: Working,
): ConstructedResponse {
	const work = arithmetic(task, working);
	if (task.kind !== "story") return work;
	return {
		kind: "distance_story",
		problem_id: task.storyId,
		operation: working.operation,
		working_steps: work,
		result_kilometres: work.result_kilometres,
		result_metres: work.result_metres,
		contextual_answer: `${working.operation === "add" ? "journey_total" : "distance_remaining"}:${work.result_kilometres}:${work.result_metres}`,
	};
}

/** The scored answer of measuring with Tikki: the tape's centimetres and the joined metres. */
export function relationResponse(
	tapeCentimetres: number,
	joinedMetres: number,
): ConstructedResponse {
	return {
		kind: "unit_relationship",
		left_unit: "km",
		right_unit: "m",
		conversion_factor: joinedMetres,
		placements: ["1 km", `${joinedMetres} m`, "1 m", `${tapeCentimetres} cm`],
	};
}

/** The scored answer of building a distance from 1 km pieces and metre pieces. */
export function conversionResponse(
	task: VillageTask,
	kilometrePieces: number,
	metres: number,
): ConstructedResponse {
	return {
		kind: "distance_conversion",
		source_value: task.total,
		source_unit: "m",
		kilometres: kilometrePieces,
		metres,
		total_metres: kilometrePieces * 1000 + metres,
		formal_metres: String(metres).padStart(3, "0"),
	};
}

/** Where a help round is played: units in Tikki's garden, road sums on the toy road. */
export type VillagePlace = "toy-road" | "tikki-garden";

export function villageTrainingPlace(task: VillageTask): VillagePlace {
	return task.kind === "relation" || task.kind === "convert"
		? "tikki-garden"
		: "toy-road";
}

/** The right working of a road sum (worked examples and the toy road's finished road). */
export function solvedWorking(
	task: VillageTask,
	operation = task.operation,
): Working {
	const { left, right } = task;
	if (operation === "add") {
		const metres = left.m + right.m;
		const exchanged = metres >= 1000;
		return {
			operation,
			metres,
			exchanged,
			km: left.km + right.km + (exchanged ? 1 : 0),
		};
	}
	const exchanged = left.m < right.m;
	return {
		operation,
		exchanged,
		metres: left.m + (exchanged ? 1000 : 0) - right.m,
		km: left.km - (exchanged ? 1 : 0) - right.km,
	};
}

/** Metre pieces of a metre count: hundreds, tens and ones (hundreds may pass 9). */
export const metrePieces = (metres: number) => ({
	hundreds: Math.floor(metres / 100),
	tens: Math.floor((metres % 100) / 10),
	ones: metres % 10,
});
