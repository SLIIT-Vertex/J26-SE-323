import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { River } from "../NumberWorldJourney";

describe("Number World ordering route", () => {
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
				<River
					game={{ values: [3721, 5831, 4210, 7021], ascending: true }}
					onChange={onChange}
				/>,
			),
		);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("renders a visual four-stop ascending route", () => {
		expect(host.textContent).toContain("කුඩා සිට විශාල දක්වා");
		expect(host.querySelectorAll(".river-bank button")).toHaveLength(4);
		expect(host.querySelectorAll(".river-route li")).toHaveLength(4);
		expect(
			[...host.querySelectorAll(".river-bank button")].every(
				(button) => button.getAttribute("aria-label")?.includes("මාර්ගයට"),
			),
		).toBe(true);
	});

	it("keeps cards stable and submits the chosen order", async () => {
		const cards = [
			...host.querySelectorAll<HTMLButtonElement>(".river-bank button"),
		];
		for (const index of [0, 2, 1, 3]) {
			await act(async () => cards[index].click());
		}

		expect(host.querySelectorAll(".river-bank button")).toHaveLength(4);
		expect(host.querySelectorAll(".river-bank button:disabled")).toHaveLength(4);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "number_order",
			order: [3721, 4210, 5831, 7021],
		});
	});
});
