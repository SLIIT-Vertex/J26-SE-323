import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	DecimalActivity,
	DecimalReadingMatcher,
	DecimalWorkedDemo,
	FractionInput,
	TenthsCircle,
	TenthsFrame,
} from "../DecimalAdventureJourney";
import { DECIMAL_GAMES, DECIMAL_SKILLS } from "../manifest";

describe("Decimal Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		host = document.createElement("div");
		host.style.width = "320px";
		document.body.append(host);
		root = createRoot(host);
	});
	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});
	it("contains exactly four games and four progress activities", () => {
		expect(DECIMAL_GAMES).toHaveLength(4);
		expect(DECIMAL_SKILLS).toHaveLength(4);
		expect(
			DECIMAL_GAMES.every((game) => game.challengeLabel === "අභියෝග 1ක්"),
		).toBe(true);
	});
	it("renders and toggles exactly ten rectangle parts with 48px targets", async () => {
		const onToggle = vi.fn();
		await act(async () =>
			root.render(<TenthsFrame selected={[2]} onToggle={onToggle} />),
		);
		const parts = [...host.querySelectorAll("button")] as HTMLButtonElement[];
		expect(parts).toHaveLength(10);
		expect(getComputedStyle(parts[0]).minHeight).toBe("48px");
		await act(async () => parts[2].click());
		expect(onToggle).toHaveBeenCalledWith(2);
		expect(parts[2].getAttribute("aria-pressed")).toBe("true");
	});
	it("renders exactly ten keyboard-operable circle sectors", async () => {
		const onToggle = vi.fn();
		await act(async () =>
			root.render(<TenthsCircle selected={[]} onToggle={onToggle} />),
		);
		const sectors = host.querySelectorAll(".tenths-circle-controls button");
		expect(sectors).toHaveLength(10);
		expect(sectors[0].getAttribute("aria-label")).toContain("1");
		await act(async () => (sectors[0] as HTMLButtonElement).click());
		expect(onToggle).toHaveBeenCalledWith(0);
	});
	it("matches reading tiles without radio controls and emits full evidence", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<DecimalReadingMatcher
					decimalTenths={[1, 2]}
					readingTiles={[
						{ reading_id: "reading-2", label_si: "දෙක" },
						{ reading_id: "reading-1", label_si: "එක" },
					]}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelector("input[type=radio]")).toBeNull();
		const sections = host.querySelectorAll("section");
		await act(async () =>
			(sections[0].querySelectorAll("button")[0] as HTMLButtonElement).click(),
		);
		await act(async () =>
			(sections[1].querySelectorAll("button")[1] as HTMLButtonElement).click(),
		);
		await act(async () =>
			(sections[0].querySelectorAll("button")[1] as HTMLButtonElement).click(),
		);
		await act(async () =>
			(sections[1].querySelectorAll("button")[0] as HTMLButtonElement).click(),
		);
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "decimal_reading_match",
				matches: [
					{ decimal_tenths: 1, reading_id: "reading-1" },
					{ decimal_tenths: 2, reading_id: "reading-2" },
				],
			}),
		);
	});
	it("keeps zero and decimal point fixed with one active answer cell", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<DecimalActivity
					game={{
						response_kind: "tenths_fraction_to_decimal",
						numerator: 3,
						denominator: 10,
						fixed_whole_digit: 0,
					}}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.textContent).toContain("0");
		expect(host.textContent).toContain(".");
		expect(host.querySelectorAll(".decimal-input button")).toHaveLength(1);
		const key = [...host.querySelectorAll(".decimal-keypad button")].find(
			(button) => button.textContent === "3",
		) as HTMLButtonElement;
		await act(async () => key.click());
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "tenths_fraction_to_decimal",
				entered_tenths_digit: 3,
				decimal_value: "0.3",
			}),
		);
	});
	it("aligns separate numerator and denominator inputs around a permanent bar", async () => {
		await act(async () =>
			root.render(
				<FractionInput
					numerator="3"
					denominator="10"
					active="denominator"
					onActivate={() => {}}
				/>,
			),
		);
		expect(host.querySelector(".fraction-bar")).not.toBeNull();
		const buttons = host.querySelectorAll("button");
		expect(buttons).toHaveLength(2);
		expect(buttons[0].getAttribute("aria-label")).toContain("ලවය");
		expect(buttons[1].getAttribute("aria-label")).toContain("හරය");
		expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});
	it("reveals the exact failed conversion only inside worked support", async () => {
		await act(async () =>
			root.render(
				<DecimalWorkedDemo
					stage={3}
					example={{
						prompt_si: "",
						steps_si: ["1", "2", "3"],
						game: {
							response_kind: "decimal_to_tenths_fraction",
							decimal_tenths: 7,
						},
						correct_response: { entered_numerator: 7, entered_denominator: 10 },
					}}
				/>,
			),
		);
		expect(host.textContent).toContain("0.7");
		expect(host.textContent).toContain("7");
		expect(host.textContent).toContain("10");
	});
});
