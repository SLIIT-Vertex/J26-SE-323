import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExpandedTable } from "../NumberWorldJourney";

describe("Number World expanded place-value table", () => {
	let host: HTMLDivElement;
	let root: Root;
	const onChange = vi.fn();

	beforeEach(async () => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
		onChange.mockReset();
		await act(async () =>
			root.render(
				<ExpandedTable
					game={{ skill_id: "G5-MAT-NUM-EXPAND-01", number: 42_305 }}
					onChange={onChange}
				/>,
			),
		);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("builds the textbook expanded form from the six place columns", async () => {
		expect(host.textContent).toContain("42 305");
		expect(host.querySelectorAll(".expanded-column")).toHaveLength(6);
		expect(onChange).not.toHaveBeenCalled();
		const clicks = [0, 4, 2, 3, 0, 5];
		for (const [index, count] of clicks.entries()) {
			const button = host.querySelectorAll<HTMLButtonElement>(
				".expanded-step-button--increment",
			)[index];
			for (let step = 0; step < count; step += 1) {
				await act(async () => button.click());
			}
		}
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "expanded_form",
			terms: [40000, 2000, 300, 5],
		});
	});

	it("clears a previous answer when a new number is mounted", async () => {
		const button = host.querySelector<HTMLButtonElement>(
			".expanded-step-button--increment",
		);
		if (!button) throw new Error("expanded control missing");
		await act(async () => button.click());
		await act(async () =>
			root.render(
				<ExpandedTable
					game={{ skill_id: "G5-MAT-NUM-EXPAND-01", number: 10_000 }}
					onChange={onChange}
				/>,
			),
		);
		expect(host.textContent).toContain("10 000");
		expect(host.textContent).not.toContain("40 000");
	});
});
