/**
 * Rules for Nimo's Shopping Day (Money), free of React. Every amount is whole cents. The server
 * scores every answer; these only read the task and turn what the child did into the working.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const SHOP_AREA_ID = "G5-AREA-MAT-10";
export const DENOMINATION_SKILL_ID = "G5-MAT-MONEY-DENOMINATION-01";
export const COMPOSE_SKILL_ID = "G5-MAT-MONEY-COMPOSE-01";
export const ADD_SKILL_ID = "G5-MAT-MONEY-ADD-01";
export const SUBTRACT_SKILL_ID = "G5-MAT-MONEY-SUBTRACT-01";
export const SHOP_SKILL_ID = "G5-MAT-MONEY-SHOP-01";

/** Every shopping kind: a grocery list, adding two prices, and the money left after paying. */
export const MISSION_SKILLS = [
	SHOP_SKILL_ID,
	ADD_SKILL_ID,
	SUBTRACT_SKILL_ID,
] as const;

/** A random shopping kind first (never the last one's), then the rest as fallbacks. */
export function missionOrder(
	previous: string | null,
	random: () => number = Math.random,
): string[] {
	const choices = MISSION_SKILLS.filter((skill) => skill !== previous);
	const first = choices[Math.floor(random() * choices.length)] ?? SHOP_SKILL_ID;
	const rest = MISSION_SKILLS.filter(
		(skill) => skill !== first && skill !== previous,
	);
	return [
		first,
		...rest,
		...(previous && previous !== first ? [previous] : []),
	];
}

export type MoneyType = "coin" | "note";
export type Denomination = { id: string; type: MoneyType; value: number };

/** Sri Lankan coins and notes, smallest first (values in cents). */
export const DENOMINATIONS: readonly Denomination[] = [
	{ id: "coin-1", type: "coin", value: 100 },
	{ id: "coin-2", type: "coin", value: 200 },
	{ id: "coin-5", type: "coin", value: 500 },
	{ id: "coin-10", type: "coin", value: 1000 },
	{ id: "note-20", type: "note", value: 2000 },
	{ id: "note-50", type: "note", value: 5000 },
	{ id: "note-100", type: "note", value: 10000 },
	{ id: "note-500", type: "note", value: 50000 },
	{ id: "note-1000", type: "note", value: 100000 },
	{ id: "note-5000", type: "note", value: 500000 },
];
export const DENOMINATION_BY_ID = Object.fromEntries(
	DENOMINATIONS.map((row) => [row.id, row]),
) as Record<string, Denomination>;

export type Product = { id: string; name: string; price: number };

export type ShopTask = {
	kind: "recognize" | "compose" | "add" | "subtract" | "shop";
	/** Adding or subtracting: the two amounts. */
	left: number;
	right: number;
	/** Making an amount. */
	target: number;
	/** Sorting coins and notes, in the order they lie on the tray. */
	tokens: Denomination[];
	/** The grocery list. */
	products: Product[];
	wanted: Record<string, number>;
	paid: number;
	requiresChange: boolean;
	problemId: string;
};

const num = (value: unknown, fallback: number) =>
	typeof value === "number" && Number.isFinite(value) ? value : fallback;
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

export function readTask(game: Record<string, unknown> | undefined): ShopTask {
	const responseKind = game?.response_kind;
	const kind =
		responseKind === "currency_recognition"
			? "recognize"
			: responseKind === "amount_construction"
				? "compose"
				: responseKind === "shopping_calculation"
					? "shop"
					: game?.operation === "subtract"
						? "subtract"
						: "add";
	const products = list(game?.products).flatMap((row) => {
		const product = row as Record<string, unknown>;
		return typeof product.product_id === "string"
			? [
					{
						id: product.product_id,
						name: String(product.name_si ?? ""),
						price: num(product.unit_price_in_cents, 0),
					},
				]
			: [];
	});
	const selected = list(game?.selected_products).map(String);
	const quantities = list(game?.quantities).map((value) => num(value, 1));
	const wanted = Object.fromEntries(
		selected.map((id, at) => [id, quantities[at] ?? 1]),
	);
	const tokens = list(game?.tokens).flatMap((row) => {
		const id = String((row as Record<string, unknown>).denomination_id);
		const token = DENOMINATION_BY_ID[id];
		return token ? [token] : [];
	});
	const paid = num(game?.amount_paid_in_cents, 0);
	return {
		kind,
		left: num(game?.left_amount_in_cents, 0),
		right: num(game?.right_amount_in_cents, 0),
		target: num(game?.target_in_cents, 1800),
		tokens,
		products,
		wanted,
		paid,
		requiresChange: game?.requires_change === true,
		problemId:
			typeof game?.problem_id === "string" ? game.problem_id : "shop-total",
	};
}

/** "රු. 165.75", or "රු. 590" for whole rupees. */
export function moneyText(cents: number): string {
	const rupees = Math.floor(cents / 100);
	const rest = cents % 100;
	return rest === 0
		? `රු. ${rupees}`
		: `රු. ${rupees}.${String(rest).padStart(2, "0")}`;
}

export const rupeesOf = (cents: number) => Math.floor(cents / 100);
export const centsOf = (cents: number) => cents % 100;

/**
 * What the child did on a rupees-and-cents board, column by column:
 * - adding: `cents` is the cents the child added up (it may pass 100), `exchanged` whether
 *   100 cents went over as Rs. 1, `rupees` the rupees the child wrote;
 * - subtracting: `exchanged` whether Rs. 1 was opened into 100 cents first, `cents` the cents
 *   left, `rupees` the rupees left.
 * Nothing here is corrected.
 */
export type Working = {
	operation: "add" | "subtract";
	cents: number;
	exchanged: boolean;
	rupees: number;
};

export function arithmeticResponse(
	task: ShopTask,
	working: Working,
): ConstructedResponse {
	const leftRupees = rupeesOf(task.left);
	const leftCents = centsOf(task.left);
	const rightRupees = rupeesOf(task.right);
	const rightCents = centsOf(task.right);
	const carry = working.exchanged ? 1 : 0;
	if (working.operation === "add") {
		const resultCents = Math.max(0, working.cents - 100 * carry);
		return {
			kind: "money_arithmetic",
			operation: "add",
			left_amount_in_cents: task.left,
			right_amount_in_cents: task.right,
			cent_subtotal_or_adjustment: working.cents,
			carried_or_borrowed_rupees: carry,
			exchange_used: working.exchanged,
			working_steps: [
				`cents:${leftCents}+${rightCents}=${working.cents}`,
				`carry:${carry}`,
				`cents-result:${resultCents}`,
				`rupees:${leftRupees}+${rightRupees}+${carry}=${working.rupees}`,
			],
			result_in_cents: working.rupees * 100 + resultCents,
			result_rupees: working.rupees,
			result_cents: resultCents,
		};
	}
	const adjusted = leftCents + 100 * carry;
	return {
		kind: "money_arithmetic",
		operation: "subtract",
		left_amount_in_cents: task.left,
		right_amount_in_cents: task.right,
		cent_subtotal_or_adjustment: adjusted,
		carried_or_borrowed_rupees: carry,
		exchange_used: working.exchanged,
		working_steps: [
			`borrow:${carry}`,
			`adjust:${leftRupees}->${leftRupees - carry}:${leftCents}->${adjusted}`,
			`cents:${adjusted}-${rightCents}=${working.cents}`,
			`rupees:${leftRupees - carry}-${rightRupees}=${working.rupees}`,
		],
		result_in_cents: working.rupees * 100 + working.cents,
		result_rupees: working.rupees,
		result_cents: working.cents,
	};
}

/** The right working of a sum (worked examples and the cash box's finished drawer). */
export function solvedWorking(task: ShopTask): Working {
	if (task.kind === "subtract") {
		const exchanged = centsOf(task.left) < centsOf(task.right);
		return {
			operation: "subtract",
			exchanged,
			cents: centsOf(task.left) + (exchanged ? 100 : 0) - centsOf(task.right),
			rupees: rupeesOf(task.left) - (exchanged ? 1 : 0) - rupeesOf(task.right),
		};
	}
	const cents = centsOf(task.left) + centsOf(task.right);
	const exchanged = cents >= 100;
	return {
		operation: "add",
		cents,
		exchanged,
		rupees: rupeesOf(task.left) + rupeesOf(task.right) + (exchanged ? 1 : 0),
	};
}

/**
 * The scored answer of a shopping trip: what is in the basket (in the shop's order), each line's
 * total and the bill total the child worked out, and the change (none when Nimo pays exactly).
 */
export function shopResponse(
	task: ShopTask,
	basket: Record<string, number>,
	lines: Record<string, number>,
	total: number,
	change: number,
): ConstructedResponse {
	const chosen = task.products.filter(
		(product) => (basket[product.id] ?? 0) > 0,
	);
	const lineTotals = chosen.map((product) => lines[product.id] ?? 0);
	const paid = task.paid;
	const changeGiven = task.requiresChange ? change : 0;
	return {
		kind: "shopping_calculation",
		problem_id: task.problemId,
		selected_products: chosen.map((product) => product.id),
		quantities: chosen.map((product) => basket[product.id] ?? 0),
		unit_prices_in_cents: chosen.map((product) => product.price),
		line_totals_in_cents: lineTotals,
		working_steps: [
			...chosen.map(
				(product, at) =>
					`line:${product.id}:${product.price}x${basket[product.id] ?? 0}=${lineTotals[at] ?? 0}`,
			),
			`total:${lineTotals.join("+")}=${total}`,
			`change:${paid}-${total}=${changeGiven}`,
		],
		total_in_cents: total,
		amount_paid_in_cents: paid,
		change_in_cents: changeGiven,
		contextual_answer: `pay:${total}:change:${changeGiven}`,
	};
}

/** The scored answer of making an amount from coins and notes. */
export function composeResponse(
	task: ShopTask,
	selected: readonly string[],
): ConstructedResponse {
	const counts: Record<string, number> = {};
	for (const id of [...selected].sort()) counts[id] = (counts[id] ?? 0) + 1;
	return {
		kind: "amount_construction",
		target_in_cents: task.target,
		selected_denominations: [...selected],
		denomination_counts: counts,
		constructed_total_in_cents: selected.reduce(
			(sum, id) => sum + (DENOMINATION_BY_ID[id]?.value ?? 0),
			0,
		),
	};
}

/** The scored answer of sorting: each token in the order it went in, and the side it went to. */
export function recognitionResponse(
	placed: readonly { id: string; side: MoneyType }[],
): ConstructedResponse {
	return {
		kind: "currency_recognition",
		denomination_id: "all",
		currency_type: "mixed",
		value_in_cents: 0,
		ordered_position: 10,
		placements: placed.map((token, at) => ({
			denomination_id: token.id,
			currency_type: token.side,
			value_in_cents: DENOMINATION_BY_ID[token.id]?.value ?? 0,
			ordered_position: at,
		})),
	};
}

/** Where a help round is played: sums and shopping at the cash box, coins at the coin box. */
export type ShopPlace = "cash-box" | "coin-box";

export function shopTrainingPlace(task: ShopTask): ShopPlace {
	return task.kind === "recognize" || task.kind === "compose"
		? "coin-box"
		: "cash-box";
}
