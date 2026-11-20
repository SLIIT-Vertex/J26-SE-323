/**
 * Rules for Nimo's Parcel Day (Mass), free of React. Every weight is whole grams. The server scores
 * every answer; these only read the task and turn what the child did into the working.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const WEIGH_AREA_ID = "G5-AREA-MAT-12";
export const INSTRUMENT_SKILL_ID = "G5-MAT-MASS-INSTRUMENT-01";
export const BALANCE_SKILL_ID = "G5-MAT-MASS-BALANCE-01";
export const CONVERT_SKILL_ID = "G5-MAT-MASS-CONVERT-01";
export const ARITHMETIC_SKILL_ID = "G5-MAT-MASS-ARITHMETIC-01";
export const LOAD_SKILL_ID = "G5-MAT-MASS-PROBLEM-01";

/** The parcel cart's two kinds: cart sums (adding or unloading) and loading with room left. */
export const MISSION_SKILLS = [ARITHMETIC_SKILL_ID, LOAD_SKILL_ID] as const;

/** A random cart kind first (never the last one's), then the other as a fallback. */
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

/** The standard weights, smallest first (grams). */
export const STANDARD_MASSES = [
	5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000,
] as const;

export type Instrument =
	| "two_pan_balance"
	| "spring_balance"
	| "dial_scale"
	| "digital_scale"
	| "platform_scale";
export type Placement = "pan" | "hook" | "tray" | "platform";

export type WeighTask = {
	kind: "instrument" | "balance" | "convert" | "add" | "subtract" | "load";
	/** Cart sums: the two weights. Loading: the two boxes. */
	left: number;
	right: number;
	/** Balancing: the box's weight. */
	target: number;
	/** Changing into kilograms: the grams given. */
	source: number;
	sourceKilograms: number;
	sourceGrams: number;
	/** Loading: how much the cart can carry. */
	capacity: number;
	missionId: string;
	itemIds: string[];
	/** The weighing room: the thing to weigh and the scales in the room. */
	objectId: string;
	instruments: Instrument[];
};

const num = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

export function readTask(game: Record<string, unknown> | undefined): WeighTask {
	const responseKind = game?.response_kind;
	const kind =
		responseKind === "mass_instrument"
			? "instrument"
			: responseKind === "mass_balance"
				? "balance"
				: responseKind === "mass_conversion"
					? "convert"
					: responseKind === "mass_market_mission"
						? "load"
						: game?.operation === "subtract"
							? "subtract"
							: "add";
	const grams = (kg: unknown, g: unknown) => num(kg, 0) * 1000 + num(g, 0);
	const items = list(game?.item_masses_g).map((value) => num(value, 0));
	return {
		kind,
		left:
			kind === "load"
				? (items[0] ?? 0)
				: grams(game?.left_kilograms, game?.left_grams),
		right:
			kind === "load"
				? (items[1] ?? 0)
				: grams(game?.right_kilograms, game?.right_grams),
		target: num(game?.target_mass_g, 1000),
		source: num(game?.source_total_g, 0),
		sourceKilograms: num(game?.source_kilograms, 0),
		sourceGrams: num(game?.source_grams, 0),
		capacity: num(game?.cart_capacity_g, 0),
		missionId:
			typeof game?.mission_id === "string" ? game.mission_id : "market",
		itemIds: list(game?.item_ids).map(String),
		objectId:
			typeof game?.object_id === "string" ? game.object_id : "small-parcel",
		instruments: list(game?.instrument_types).map(
			(value) => String(value) as Instrument,
		),
	};
}

export const kilogramsOf = (g: number) => Math.floor(g / 1000);
export const gramsOf = (g: number) => g % 1000;

/** "8 kg 250 g", "16 kg" or "750 g", as a child reads it. */
export function massText(g: number): string {
	const kilograms = kilogramsOf(g);
	const rest = gramsOf(g);
	if (!kilograms) return `${rest} g`;
	return rest ? `${kilograms} kg ${rest} g` : `${kilograms} kg`;
}

/**
 * What the child did on a kg | g board, column by column:
 * - adding: `g` is the grams added up (it may pass 1000), `exchanged` whether 1000 g went over as
 *   1 kg, `kg` the kilograms the child wrote;
 * - unloading: `exchanged` whether 1 kg was opened into 1000 g first, `g` the grams left, `kg`
 *   the kilograms left.
 * Nothing here is corrected.
 */
export type Working = {
	operation: "add" | "subtract";
	g: number;
	exchanged: boolean;
	kg: number;
};

function arithmeticOf(left: number, right: number, working: Working) {
	const leftKg = kilogramsOf(left);
	const leftG = gramsOf(left);
	const rightKg = kilogramsOf(right);
	const rightG = gramsOf(right);
	const carry = working.exchanged ? 1 : 0;
	if (working.operation === "add") {
		const resultG = Math.max(0, working.g - 1000 * carry);
		return {
			subtotal: working.g,
			carry,
			resultKg: working.kg,
			resultG,
			steps: [
				`g:${leftG}+${rightG}=${working.g}`,
				`carry:${carry}`,
				`g-result:${resultG}`,
				`kg:${leftKg}+${rightKg}+${carry}=${working.kg}`,
			],
		};
	}
	const adjusted = leftG + 1000 * carry;
	return {
		subtotal: adjusted,
		carry,
		resultKg: working.kg,
		resultG: working.g,
		steps: [
			`borrow:${carry}`,
			`adjust:${leftKg}->${leftKg - carry}:${leftG}->${adjusted}`,
			`g:${adjusted}-${rightG}=${working.g}`,
			`kg:${leftKg - carry}-${rightKg}=${working.kg}`,
		],
	};
}

export function arithmeticResponse(
	task: WeighTask,
	working: Working,
): ConstructedResponse {
	const work = arithmeticOf(task.left, task.right, working);
	return {
		kind: "mass_arithmetic",
		operation: working.operation,
		left_kilograms: kilogramsOf(task.left),
		left_grams: gramsOf(task.left),
		right_kilograms: kilogramsOf(task.right),
		right_grams: gramsOf(task.right),
		gram_subtotal_or_adjustment: work.subtotal,
		carried_or_borrowed_kilograms: work.carry,
		exchange_used: working.exchanged,
		working_steps: work.steps,
		result_kilograms: work.resultKg,
		result_grams: work.resultG,
	};
}

/** The right working of a two-weight sum (worked examples and the balance's finished pans). */
export function solvedWorking(
	task: Pick<WeighTask, "kind" | "left" | "right">,
): Working {
	if (task.kind === "subtract") {
		const exchanged = gramsOf(task.left) < gramsOf(task.right);
		return {
			operation: "subtract",
			exchanged,
			g: gramsOf(task.left) + (exchanged ? 1000 : 0) - gramsOf(task.right),
			kg:
				kilogramsOf(task.left) - (exchanged ? 1 : 0) - kilogramsOf(task.right),
		};
	}
	const g = gramsOf(task.left) + gramsOf(task.right);
	const exchanged = g >= 1000;
	return {
		operation: "add",
		g,
		exchanged,
		kg: kilogramsOf(task.left) + kilogramsOf(task.right) + (exchanged ? 1 : 0),
	};
}

/** The fewest standard weights that make `grams` (biggest first). */
export function weightsFor(grams: number): number[] {
	const picks: number[] = [];
	let rest = Math.max(0, grams);
	for (const mass of [...STANDARD_MASSES].reverse())
		while (mass <= rest) {
			picks.push(mass);
			rest -= mass;
		}
	return picks;
}

/**
 * The scored answer of loading the cart: the two boxes' sum worked on the kg | g board, the
 * standard weights that balance that total, and the room the child says is left.
 */
export function loadResponse(
	task: WeighTask,
	working: Working,
	room: number,
	/** The weights that balanced the load (the balance help); else the fewest that make the total. */
	weights?: readonly number[],
): ConstructedResponse {
	const work = arithmeticOf(task.left, task.right, working);
	const total = work.resultKg * 1000 + work.resultG;
	return {
		kind: "mass_market_mission",
		mission_id: task.missionId,
		selected_items: [...task.itemIds],
		item_masses_g: [task.left, task.right],
		selected_standard_masses_g: weights ? [...weights] : weightsFor(total),
		operation: "add",
		working_steps: work.steps,
		total_mass_g: total,
		result_kilograms: work.resultKg,
		result_grams: work.resultG,
		remaining_capacity_g: room,
		contextual_answer: `load:${total}:remaining:${room}`,
	};
}

/** The scored answer of balancing a box with standard weights. */
export function balanceResponse(
	task: WeighTask,
	weights: readonly number[],
): ConstructedResponse {
	const total = weights.reduce((sum, mass) => sum + mass, 0);
	const counts: Record<string, number> = {};
	for (const mass of [...weights].sort((a, b) => a - b))
		counts[String(mass)] = (counts[String(mass)] ?? 0) + 1;
	return {
		kind: "mass_balance",
		target_mass_g: task.target,
		selected_mass_denominations_g: [...weights],
		denomination_counts: counts,
		selected_total_g: total,
		balance_difference_g: total - task.target,
		balanced: total === task.target,
	};
}

/** The scored answer of changing grams into kilograms and grams. */
export function convertResponse(
	task: WeighTask,
	kilograms: number,
	grams: number,
): ConstructedResponse {
	return {
		kind: "mass_conversion",
		source_kilograms: task.sourceKilograms,
		source_grams: task.sourceGrams,
		source_total_g: task.source,
		result_kilograms: kilograms,
		result_grams: grams,
		exchange_count: kilograms,
	};
}

/** The scored answer of the weighing room: the scale chosen and the spot the thing was put on. */
export function instrumentResponse(
	task: WeighTask,
	tries: readonly { instrument: Instrument; placement: Placement }[],
): ConstructedResponse {
	const last = tries.at(-1) ?? {
		instrument: "digital_scale",
		placement: "platform",
	};
	return {
		kind: "mass_instrument",
		object_id: task.objectId,
		instrument_type: last.instrument,
		placement: last.placement,
		interaction_trace: tries.map(
			(step) => `place:${task.objectId}:${step.instrument}:${step.placement}`,
		),
	};
}

/** Where a help round is played: weights and sums at the balance, scales in the weighing room. */
export type WeighPlace = "balance-scale" | "weighing-room";

export function weighTrainingPlace(task: WeighTask): WeighPlace {
	return task.kind === "instrument" ? "weighing-room" : "balance-scale";
}
