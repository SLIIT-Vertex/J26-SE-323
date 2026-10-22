import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	exchangeLabel,
	SUBTRACTION_CHAPTERS,
	SUBTRACTION_SKILLS,
} from "../manifest";
import { SubtractionMechanic } from "../SubtractionAdventureJourney";

function change(input: HTMLInputElement, value: string) {
	const setter = Object.getOwnPropertyDescriptor(
		HTMLInputElement.prototype,
		"value",
	)?.set;
	setter?.call(input, value);
	input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("Subtraction Adventure", () => {
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

	it("keeps three games in easy-to-hard order with two challenges", () => {
		expect(SUBTRACTION_CHAPTERS.map((chapter) => chapter.difficulty)).toEqual([
			"පහසු",
			"මධ්‍යම",
			"අභියෝගාත්මක",
		]);
		for (const chapter of SUBTRACTION_CHAPTERS) {
			expect(
				SUBTRACTION_SKILLS.filter((skill) => skill.chapter === chapter.id),
			).toHaveLength(2);
		}
		expect(exchangeLabel("tens", "ones")).toBe(
			"දහය තැනින් එකක් ගෙන එක තැනට දහයක් එක් කරන්න",
		);
	});

	it("builds an aligned column response without revealing the answer", async () => {
		await act(async () =>
			root.render(
				<SubtractionMechanic
					reducedMotion
					game={{
						places: ["hundreds", "tens", "ones"],
						place_labels_si: ["සිය", "දහය", "එක"],
						width: 3,
						minuend: 685,
						subtrahend: 339,
					}}
					onChange={onChange}
				/>,
			),
		);
		expect(host.textContent).not.toContain("346");
		const ones = host.querySelector<HTMLInputElement>(
			'[aria-label="එක තැනේ පිළිතුරු ඉලක්කම ඇතුළත් කරන්න"]',
		);
		expect(ones).not.toBeNull();
		for (const control of host.querySelectorAll<HTMLElement>(".touch-target")) {
			expect(control.style.minHeight || "48px").toBeTruthy();
		}
		// One button on the ones column borrows 1 from the tens.
		await act(async () => {
			host
				.querySelector<HTMLButtonElement>('.borrow-button[data-place="ones"]')
				?.click();
		});
		const fields = host.querySelectorAll<HTMLInputElement>(".result-digit");
		await act(async () => change(fields[0], "3"));
		await act(async () => change(fields[1], "4"));
		await act(async () => change(fields[2], "6"));
		expect(onChange).toHaveBeenLastCalledWith(
			{
				kind: "column_subtraction",
				result_digits: [3, 4, 6],
				exchanges: [{ from_place: "tens", to_place: "ones" }],
			},
			expect.objectContaining({ digitEntries: 1 }),
		);
		expect(
			[...host.querySelectorAll(".exchange-token")].map(
				(node) => node.textContent,
			),
		).toEqual(["7", "15"]);
	});

	it("builds expanded and story responses and resets with a new mount", async () => {
		await act(async () =>
			root.render(
				<SubtractionMechanic
					reducedMotion={false}
					game={{
						representation: "expanded",
						places: ["thousands", "hundreds", "tens", "ones"],
						place_labels_si: ["දහස්", "සිය", "දහය", "එක"],
						width: 4,
						minuend: 7828,
						subtrahend: 2506,
					}}
					onChange={onChange}
				/>,
			),
		);
		const rows = ["minuend", "subtrahend", "adjusted", "result"] as const;
		const values = {
			minuend: ["7000", "800", "20", "8"],
			subtrahend: ["2000", "500", "0", "6"],
			adjusted: ["7000", "800", "20", "8"],
			result: ["5000", "300", "20", "2"],
		};
		for (const row of rows) {
			const fields = host.querySelectorAll<HTMLInputElement>(
				`[data-row="${row}"] input`,
			);
			for (const [index, value] of values[row].entries()) {
				await act(async () => change(fields[index], value));
			}
		}
		const finalResult =
			host.querySelector<HTMLInputElement>(".expanded-result");
		expect(finalResult).not.toBeNull();
		await act(async () => change(finalResult as HTMLInputElement, "5322"));
		expect(onChange).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "expanded_subtraction",
				result: 5322,
				subtrahend_terms: [2000, 500, 0, 6],
			}),
			expect.anything(),
		);

		await act(async () =>
			root.render(
				<SubtractionMechanic
					key="fresh"
					reducedMotion
					game={{
						relationship: "how_many_more",
						places: ["hundreds", "tens", "ones"],
						place_labels_si: ["සිය", "දහය", "එක"],
						width: 3,
						asset: "/curriculum/game/G5-AREA-MAT-02/fruit-tokens.png",
						quantities: [
							{ source: "first", label_si: "පළමු කූඩයේ පළතුරු", value: 640 },
							{ source: "second", label_si: "දෙවන කූඩයේ පළතුරු", value: 215 },
						],
					}}
					onChange={onChange}
				/>,
			),
		);
		expect(host.querySelector("img")?.alt).toBe("");
		expect(host.querySelector(".result-digit")).toBeNull();
		await act(async () => {
			host
				.querySelector<HTMLButtonElement>(
					'[data-source="first"] .story-minuend',
				)
				?.click();
		});
		await act(async () => {
			host
				.querySelector<HTMLButtonElement>(
					'[data-source="second"] .story-subtrahend',
				)
				?.click();
		});
		const digits = host.querySelectorAll<HTMLInputElement>(".result-digit");
		expect(digits).toHaveLength(3);
		await act(async () => change(digits[0], "4"));
		await act(async () => change(digits[1], "2"));
		await act(async () => change(digits[2], "5"));
		expect(onChange).toHaveBeenLastCalledWith(
			{
				kind: "difference_story",
				relationship: "how_many_more",
				minuend_source: "first",
				subtrahend_source: "second",
				result_digits: [4, 2, 5],
				result: 425,
			},
			expect.objectContaining({ digitEntries: 1 }),
		);
	});
});
