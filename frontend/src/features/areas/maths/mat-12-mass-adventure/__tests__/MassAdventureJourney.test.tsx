import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BalanceScale, MassActivity, MassWorkedDemo, MassWorkingTable } from "../MassAdventureJourney";
import { MASS_GAMES, MASS_SKILLS } from "../manifest";

describe("Mass Adventure", () => {
	let host: HTMLDivElement; let root: Root;
	beforeEach(() => { host = document.createElement("div"); host.style.width = "320px"; document.body.append(host); root = createRoot(host); });
	afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
	it("contains exactly three games and five activities", () => {
		expect(MASS_GAMES.map((game) => game.challengeLabel)).toEqual(["අභියෝග 2ක්", "අභියෝග 2ක්", "අභියෝග 1ක්"]);
		expect(MASS_SKILLS).toHaveLength(5);
	});
	it("renders a dynamic balance with complete labelled pans", async () => {
		await act(async () => root.render(<BalanceScale targetMassG={1000} selectedMassesG={[500]} />));
		expect(host.textContent).toContain("වම් පැත්ත බර වැඩියි");
		expect(host.querySelector(".balance-beam")?.getAttribute("style")).not.toContain("rotate(0deg)");
		await act(async () => root.render(<BalanceScale targetMassG={1000} selectedMassesG={[500, 500]} />));
		expect(host.textContent).toContain("තරාදිය සමබරයි");
		expect(host.querySelector(".right-pan")?.getAttribute("aria-label")).toContain("සම්මත බර තැටිය");
	});
	it("shows the five scale photographs for the correct-scale activity", async () => {
		await act(async () => root.render(
			<MassActivity
				game={{
					response_kind: "mass_instrument",
					object_id: "small-parcel",
					instrument_types: ["two_pan_balance", "spring_balance", "dial_scale", "digital_scale", "platform_scale"],
				}}
				onResponse={() => undefined}
			/>,
		));
		expect([...host.querySelectorAll(".instrument-icon")].map((node) => node.getAttribute("src"))).toEqual([
			"/curriculum/game/G5-AREA-MAT-12/01-two-pan-balance.png",
			"/curriculum/game/G5-AREA-MAT-12/02-spring-balance.png",
			"/curriculum/game/G5-AREA-MAT-12/03-dial-scale.png",
			"/curriculum/game/G5-AREA-MAT-12/04-digital-scale.png",
			"/curriculum/game/G5-AREA-MAT-12/05-electronic-platform-scale.png",
		]);
		expect(host.textContent).toContain("තැටි දෙකේ තරාදිය");
		expect(host.textContent).toContain("ඉලෙක්ට්‍රොනික වේදිකා තරාදිය");
	});
	it("adds and removes standard masses while emitting complete evidence", async () => {
		const onResponse = vi.fn();
		await act(async () => root.render(<MassActivity game={{ response_kind: "mass_balance", target_mass_g: 1000, available_masses_g: [500] }} onResponse={onResponse} />));
		const mass = host.querySelector('[aria-label="500 ග්‍රෑම් තැටියට දමන්න"]') as HTMLButtonElement;
		await act(async () => mass.click());
		await act(async () => mass.click());
		expect(onResponse).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "mass_balance", selected_total_g: 1000, balanced: true }), expect.anything());
		const remove = [...host.querySelectorAll("button")].find((node) => node.textContent?.includes("අවසන් බර ඉවත් කරන්න")) as HTMLButtonElement;
		await act(async () => remove.click());
		expect(onResponse).toHaveBeenLastCalledWith(expect.objectContaining({ selected_total_g: 500, balanced: false }), expect.objectContaining({ correction: true }));
	});
	it("keeps the paper kg/g table visible with 48px fill cells", async () => {
		await act(async () => root.render(<MassWorkingTable game={{ operation: "add", left_kilograms: 8, left_grams: 250, right_kilograms: 7, right_grams: 750 }} />));
		expect(host.textContent).toContain("1000 g = 1 kg"); expect(host.querySelectorAll(".mass-cell")).toHaveLength(4);
		expect(getComputedStyle(host.querySelector(".mass-cell") as HTMLElement).minHeight).toBe("48px");
		expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});
	it("reveals exact answers only in earned worked support", async () => {
		const response = { kind: "mass_arithmetic" as const, operation: "add" as const, left_kilograms: 8, left_grams: 250, right_kilograms: 7, right_grams: 750, gram_subtotal_or_adjustment: 1000, carried_or_borrowed_kilograms: 1, exchange_used: true, working_steps: ["g:250+750=1000", "carry:1", "g-result:0", "kg:8+7+1=16"], result_kilograms: 16, result_grams: 0 };
		const example = { mode: "exact_failed_activity" as const, prompt_si: "එකතු කරන්න", game: { schema_version: "mass-adventure-item-v1" as const, chapter: "kilogram_machine" as const, response_kind: "mass_arithmetic", operation: "add", left_kilograms: 8, left_grams: 250, right_kilograms: 7, right_grams: 750 }, correct_response: response, steps_si: ["g", "හුවමාරුව", "kg", "පිළිතුර"] };
		await act(async () => root.render(<MassWorkedDemo example={example} stage={4} />)); expect(host.textContent).toContain("16 kg 000 g");
		await act(async () => root.render(<MassWorkedDemo example={{ ...example, correct_response: null }} stage={2} />)); expect(host.textContent).not.toContain("16 kg 000 g");
	});
});
