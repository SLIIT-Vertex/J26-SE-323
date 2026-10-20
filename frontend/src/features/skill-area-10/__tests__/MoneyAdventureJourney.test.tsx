import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	MoneyActivity,
	MoneyWorkedDemo,
	MoneyWorkingTable,
} from "../MoneyAdventureJourney";
import { MONEY_GAMES, MONEY_SKILLS } from "../manifest";

describe("Money Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		host = document.createElement("div");
		host.style.width = "320px";
		document.body.append(host);
		root = createRoot(host);
	});
	afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

	it("contains exactly three games and five activities", () => {
		expect(MONEY_GAMES.map((game) => game.challengeLabel)).toEqual(["අභියෝග 2ක්", "අභියෝග 2ක්", "අභියෝග 1ක්"]);
		expect(MONEY_SKILLS).toHaveLength(5);
	});

	it("keeps the rupee-cent paper table visible with accessible targets", async () => {
		await act(async () => root.render(<MoneyWorkingTable game={{ operation: "add", left_amount_in_cents: 16575, right_amount_in_cents: 24250 }} />));
		expect(host.textContent).toContain("සත 100 = රුපියල් 1");
		expect(host.querySelectorAll(".money-cell")).toHaveLength(4);
		const cell = host.querySelector('[aria-label="අවසාන රුපියල්"]') as HTMLElement;
		expect(cell).not.toBeNull();
		expect(getComputedStyle(cell).minHeight).toBe("48px");
		expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});

	it("builds amount evidence from whole-token taps", async () => {
		const onResponse = vi.fn();
		await act(async () => root.render(<MoneyActivity game={{ response_kind: "amount_construction", target_in_cents: 7600, denominations: ["coin-1", "coin-2"] }} onResponse={onResponse} />));
		const token = host.querySelector('[aria-label="රුපියල් 2 කාසිය"]') as HTMLButtonElement;
		await act(async () => token.click());
		expect(onResponse).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "amount_construction", selected_denominations: ["coin-2"], constructed_total_in_cents: 200 }), expect.objectContaining({ overshoot: false }));
	});

	it("reveals exact intermediate answers only in worked support", async () => {
		const response = {
			kind: "money_arithmetic" as const, operation: "add" as const,
			left_amount_in_cents: 16575, right_amount_in_cents: 24250,
			cent_subtotal_or_adjustment: 125, carried_or_borrowed_rupees: 1,
			exchange_used: true, working_steps: ["cents:75+50=125", "carry:1", "cents-result:25", "rupees:165+242+1=408"],
			result_in_cents: 40825, result_rupees: 408, result_cents: 25,
		};
		const example = { mode: "exact_failed_activity" as const, prompt_si: "එකතු කරන්න", game: { schema_version: "money-adventure-item-v1" as const, chapter: "money_calculation" as const, response_kind: "money_arithmetic", operation: "add", left_amount_in_cents: 16575, right_amount_in_cents: 24250 }, correct_response: response, steps_si: ["සත", "හුවමාරුව", "පිළිතුර"] };
		await act(async () => root.render(<MoneyWorkedDemo example={example} stage={4} />));
		expect(host.textContent).toContain("408.25");
		await act(async () => root.render(<MoneyWorkedDemo example={{ ...example, correct_response: null }} stage={2} />));
		expect(host.textContent).not.toContain("408.25");
	});
});
