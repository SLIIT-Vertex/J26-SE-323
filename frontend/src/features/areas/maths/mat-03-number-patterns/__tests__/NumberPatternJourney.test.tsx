import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PatternMechanic } from "../NumberPatternJourney";
import { NUMBER_PATTERN_CHAPTERS, NUMBER_PATTERN_SKILLS } from "../manifest";

function change(input: HTMLInputElement, value: string) {
	const setter = Object.getOwnPropertyDescriptor(
		HTMLInputElement.prototype,
		"value",
	)?.set;
	setter?.call(input, value);
	input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("Number Pattern Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	const onChange = vi.fn();

	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
		onChange.mockReset();
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("keeps the three games in easy-to-hard order with two challenges each", () => {
		expect(NUMBER_PATTERN_CHAPTERS.map((chapter) => chapter.id)).toEqual([
			"number_step_trail",
			"multiplication_bridge",
			"pattern_power_machine",
		]);
		for (const chapter of NUMBER_PATTERN_CHAPTERS) {
			expect(
				NUMBER_PATTERN_SKILLS.filter((skill) => skill.chapter === chapter.id),
			).toHaveLength(2);
		}
	});

	it("builds a constant-difference response with large labelled touch controls", async () => {
		await act(async () =>
			root.render(
				<PatternMechanic
					game={{
						chapter: "number_step_trail",
						operation: "add",
						visible_terms: [2, 4, 6, null, null],
						missing_indices: [3, 4],
					}}
					onChange={onChange}
				/>,
			),
		);

		const add = host.querySelector<HTMLButtonElement>(
			'[aria-label="එකතු කිරීම තෝරන්න"]',
		);
		const rule = host.querySelector<HTMLInputElement>(
			'[aria-label="පොදු අන්තරය ඇතුළත් කරන්න"]',
		);
		const terms = host.querySelectorAll<HTMLInputElement>(
			".pattern-node input",
		);
		expect(add).not.toBeNull();
		expect(rule).not.toBeNull();
		expect(terms).toHaveLength(2);
		expect(
			host.querySelectorAll(".pattern-operation-buttons button"),
		).toHaveLength(2);

		await act(async () => add?.click());
		await act(async () => {
			if (rule) change(rule, "2");
		});
		await act(async () => change(terms[0], "8"));
		await act(async () => change(terms[1], "10"));

		expect(onChange).toHaveBeenLastCalledWith(
			{
				kind: "constant_difference_pattern",
				operation: "add",
				difference: 2,
				completed_terms: [8, 10],
			},
			undefined,
		);
	});

	it("builds a constant-ratio response and exposes the hard-game machine", async () => {
		await act(async () =>
			root.render(
				<PatternMechanic
					game={{
						chapter: "pattern_power_machine",
						operation: "multiply",
						visible_terms: [3, 12, 48, null, null],
						missing_indices: [3, 4],
					}}
					onChange={onChange}
				/>,
			),
		);
		expect(host.querySelector<HTMLImageElement>(".pattern-machine")?.alt).toBe(
			"",
		);
		const rule = host.querySelector<HTMLInputElement>(
			'[aria-label="ගුණකය ඇතුළත් කරන්න"]',
		);
		const terms = host.querySelectorAll<HTMLInputElement>(
			".pattern-node input",
		);
		await act(async () => {
			if (rule) change(rule, "4");
		});
		await act(async () => change(terms[0], "192"));
		await act(async () => change(terms[1], "768"));
		expect(onChange).toHaveBeenLastCalledWith(
			{
				kind: "constant_ratio_pattern",
				multiplier: 4,
				completed_terms: [192, 768],
			},
			undefined,
		);
	});
});
