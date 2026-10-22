import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type MoneyArithmeticResponse = Extract<
	ConstructedResponse,
	{ kind: "money_arithmetic" }
>;
export type ShoppingResponse = Extract<
	ConstructedResponse,
	{ kind: "shopping_calculation" }
>;

export const DENOMINATIONS = [
	{ id: "coin-1", type: "coin", cents: 100, label: "රුපියල් 1" },
	{ id: "coin-2", type: "coin", cents: 200, label: "රුපියල් 2" },
	{ id: "coin-5", type: "coin", cents: 500, label: "රුපියල් 5" },
	{ id: "coin-10", type: "coin", cents: 1000, label: "රුපියල් 10" },
	{ id: "note-20", type: "note", cents: 2000, label: "රුපියල් 20" },
	{ id: "note-50", type: "note", cents: 5000, label: "රුපියල් 50" },
	{ id: "note-100", type: "note", cents: 10000, label: "රුපියල් 100" },
	{ id: "note-500", type: "note", cents: 50000, label: "රුපියල් 500" },
	{ id: "note-1000", type: "note", cents: 100000, label: "රුපියල් 1000" },
	{ id: "note-5000", type: "note", cents: 500000, label: "රුපියල් 5000" },
] as const;

export function splitMoney(totalInCents: number) {
	if (!Number.isSafeInteger(totalInCents) || totalInCents < 0)
		throw new Error("MONEY_OUT_OF_RANGE");
	return { rupees: Math.floor(totalInCents / 100), cents: totalInCents % 100 };
}

export function normalizeMoney(rupees: number, cents: number) {
	if (![rupees, cents].every((value) => Number.isSafeInteger(value) && value >= 0))
		throw new Error("MONEY_OUT_OF_RANGE");
	return {
		rupees: rupees + Math.floor(cents / 100),
		cents: cents % 100,
	};
}

export function formatMoney(totalInCents: number) {
	const { rupees, cents } = splitMoney(totalInCents);
	return `${rupees}.${String(cents).padStart(2, "0")}`;
}

export function denominationTotal(ids: string[]) {
	return ids.reduce((total, id) => {
		const denomination = DENOMINATIONS.find((item) => item.id === id);
		if (!denomination) throw new Error("UNKNOWN_DENOMINATION");
		return total + denomination.cents;
	}, 0);
}

export function denominationCounts(ids: string[]) {
	return ids.reduce<Record<string, number>>((counts, id) => {
		counts[id] = (counts[id] ?? 0) + 1;
		return counts;
	}, {});
}

export function canonicalMoneyArithmetic(
	operation: "add" | "subtract",
	left: number,
	right: number,
): MoneyArithmeticResponse {
	const first = splitMoney(left);
	const second = splitMoney(right);
	if (operation === "add") {
		const subtotal = first.cents + second.cents;
		const carry = Math.floor(subtotal / 100);
		const resultRupees = first.rupees + second.rupees + carry;
		const resultCents = subtotal % 100;
		return {
			kind: "money_arithmetic",
			operation,
			left_amount_in_cents: left,
			right_amount_in_cents: right,
			cent_subtotal_or_adjustment: subtotal,
			carried_or_borrowed_rupees: carry,
			exchange_used: carry > 0,
			working_steps: [
				`cents:${first.cents}+${second.cents}=${subtotal}`,
				`carry:${carry}`,
				`cents-result:${resultCents}`,
				`rupees:${first.rupees}+${second.rupees}+${carry}=${resultRupees}`,
			],
			result_in_cents: resultRupees * 100 + resultCents,
			result_rupees: resultRupees,
			result_cents: resultCents,
		};
	}
	if (left < right) throw new Error("NEGATIVE_MONEY");
	const borrow = first.cents < second.cents ? 1 : 0;
	const adjustedRupees = first.rupees - borrow;
	const adjustedCents = first.cents + borrow * 100;
	const resultCents = adjustedCents - second.cents;
	const resultRupees = adjustedRupees - second.rupees;
	return {
		kind: "money_arithmetic",
		operation,
		left_amount_in_cents: left,
		right_amount_in_cents: right,
		cent_subtotal_or_adjustment: adjustedCents,
		carried_or_borrowed_rupees: borrow,
		exchange_used: borrow > 0,
		working_steps: [
			`borrow:${borrow}`,
			`adjust:${first.rupees}->${adjustedRupees}:${first.cents}->${adjustedCents}`,
			`cents:${adjustedCents}-${second.cents}=${resultCents}`,
			`rupees:${adjustedRupees}-${second.rupees}=${resultRupees}`,
		],
		result_in_cents: resultRupees * 100 + resultCents,
		result_rupees: resultRupees,
		result_cents: resultCents,
	};
}

export function calculateLineTotals(prices: number[], quantities: number[]) {
	if (prices.length !== quantities.length)
		throw new Error("SHOPPING_LENGTH_MISMATCH");
	return prices.map((price, index) => {
		const quantity = quantities[index];
		if (![price, quantity].every((value) => Number.isSafeInteger(value) && value >= 0))
			throw new Error("SHOPPING_VALUE_OUT_OF_RANGE");
		return price * quantity;
	});
}
