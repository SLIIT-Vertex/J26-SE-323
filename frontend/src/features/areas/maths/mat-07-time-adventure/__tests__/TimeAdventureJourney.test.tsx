import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnalogueClock, TimeActivity, TimeWorkedDemo } from "../TimeAdventureJourney";
import { TIME_GAMES, TIME_SKILLS } from "../manifest";

describe("Time Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	const onResponse = vi.fn();
	beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); onResponse.mockReset(); });
	afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

	it("contains exactly three games and five easy-to-hard activities", () => {
		expect(TIME_GAMES.map((game) => game.challengeCount)).toEqual([2, 1, 2]);
		expect(TIME_SKILLS).toHaveLength(5);
	});

	it("renders twelve clock numbers and accessible 48px controls", async () => {
		await act(async () => root.render(<><AnalogueClock hour={10} minute={35} /><TimeActivity game={{ response_kind: "analog_clock", target_hour: 10, target_minute: 35 }} onResponse={onResponse} /></>));
		expect(host.querySelectorAll(".clock-number")).toHaveLength(24);
		const plus = host.querySelector<HTMLButtonElement>('button[aria-label="පැය එකතු කරන්න"]');
		expect(plus).not.toBeNull();
		expect(getComputedStyle(plus as HTMLButtonElement).minWidth).toBe("48px");
		await act(async () => plus?.click());
		expect(onResponse).toHaveBeenLastCalledWith({ kind: "analog_clock", hour: 2, minute: 0 });
	});

	it("updates the selected relationship without exposing an answer key", async () => {
		await act(async () => root.render(<TimeActivity game={{ response_kind: "time_unit_match", left_options: [[60, "seconds"], [24, "hours"]], right_options: [[1, "days"], [1, "minutes"]] }} onResponse={onResponse} />));
		const select = host.querySelector<HTMLSelectElement>("select");
		expect(select?.getAttribute("aria-label")).toContain("සම්බන්ධතාව");
		await act(async () => { if (select) { select.value = "0"; select.dispatchEvent(new Event("change", { bubbles: true })); } });
		expect(onResponse).toHaveBeenLastCalledWith({ kind: "time_unit_match", matches: [0, -1] });
	});

	it("reveals the exact answer only in worked visual support", async () => {
		const example = { game: { response_kind: "elapsed_time", start_hour: 8, start_minute: 10, end_hour: 10, end_minute: 40 }, correct_response: { kind: "elapsed_time", hours: 2, minutes: 30 } };
		await act(async () => root.render(<TimeWorkedDemo example={example} stage={2} />));
		expect(host.textContent).toContain("2 පැය 30 මිනිත්තු");
		await act(async () => root.render(<TimeWorkedDemo example={{ ...example, correct_response: null }} stage={2} />));
		expect(host.textContent).not.toContain("2 පැය 30 මිනිත්තු");
	});
});
