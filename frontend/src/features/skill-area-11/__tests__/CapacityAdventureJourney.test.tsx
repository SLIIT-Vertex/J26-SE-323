import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CapacityActivity, CapacityWorkedDemo, CapacityWorkingTable, GraduatedVessel } from "../CapacityAdventureJourney";
import { CAPACITY_GAMES, CAPACITY_SKILLS } from "../manifest";

describe("Capacity Adventure", () => {
	let host: HTMLDivElement; let root: Root;
	beforeEach(() => { host = document.createElement("div"); host.style.width = "320px"; document.body.append(host); root = createRoot(host); });
	afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
	it("contains exactly three games and five activities", () => {
		expect(CAPACITY_GAMES.map((game) => game.challengeLabel)).toEqual(["අභියෝග 2ක්", "අභියෝග 2ක්", "අභියෝග 1ක්"]);
		expect(CAPACITY_SKILLS).toHaveLength(5);
	});
	it("renders ten exact graduations with accessible 48px targets", async () => {
		await act(async () => root.render(<GraduatedVessel levelMl={600} activeTick={600} />));
		expect(host.querySelectorAll(".vessel-body > button")).toHaveLength(10);
		const tick = host.querySelector('[aria-label="600 මිලිලීටර් සලකුණ"]') as HTMLElement;
		expect(tick).not.toBeNull(); expect(getComputedStyle(tick).minHeight).toBe("48px");
		expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});
	it("emits composition evidence and visibly handles overflow", async () => {
		const onResponse = vi.fn();
		await act(async () => root.render(<CapacityActivity game={{ response_kind: "capacity_composition", target_ml: 1000, available_portions_ml: [500, 1000] }} onResponse={onResponse} />));
		const thousand = host.querySelector('[aria-label="1000 මිලිලීටර් කොටස වත් කරන්න"]') as HTMLButtonElement;
		await act(async () => thousand.click());
		expect(onResponse).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "capacity_composition", constructed_total_ml: 1000, overflow_ml: 0 }), expect.objectContaining({ overflow: false }));
	});
	it("keeps the full l/ml paper table visible", async () => {
		await act(async () => root.render(<CapacityWorkingTable game={{ operation: "add", left_litres: 8, left_millilitres: 250, right_litres: 4, right_millilitres: 750 }} />));
		expect(host.textContent).toContain("1000 ml = 1 l"); expect(host.querySelectorAll(".capacity-cell")).toHaveLength(4); expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});
	it("reveals exact intermediate answers only in worked support", async () => {
		const response = { kind: "capacity_arithmetic" as const, operation: "add" as const, left_litres: 8, left_millilitres: 250, right_litres: 4, right_millilitres: 750, millilitre_subtotal_or_adjustment: 1000, carried_or_borrowed_litres: 1, exchange_used: true, working_steps: ["ml:250+750=1000", "carry:1", "ml-result:0", "litres:8+4+1=13"], result_litres: 13, result_millilitres: 0 };
		const example = { mode: "exact_failed_activity" as const, prompt_si: "එකතු කරන්න", game: { schema_version: "capacity-adventure-item-v1" as const, chapter: "litre_machine" as const, response_kind: "capacity_arithmetic", operation: "add", left_litres: 8, left_millilitres: 250, right_litres: 4, right_millilitres: 750 }, correct_response: response, steps_si: ["ml", "හුවමාරුව", "l", "පිළිතුර"] };
		await act(async () => root.render(<CapacityWorkedDemo example={example} stage={4} />)); expect(host.textContent).toContain("13 l 000 ml");
		await act(async () => root.render(<CapacityWorkedDemo example={{ ...example, correct_response: null }} stage={2} />)); expect(host.textContent).not.toContain("13 l 000 ml");
	});
});
