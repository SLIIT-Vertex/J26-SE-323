import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Kite } from "../NumberWorldJourney";

describe("Number World greatest and smallest number table", () => {
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
				<Kite
					game={{ digits: [2, 4, 3], greatest: true }}
					onChange={onChange}
				/>,
			),
		);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("renders the textbook-style place-value table", () => {
		expect(host.textContent).toContain("විශාලම සංඛ්‍යාව සාදන්න");
		expect(
			[...host.querySelectorAll(".extreme-place-table th")].map(
				(cell) => cell.textContent,
			),
		).toEqual(["සිය", "දහය", "එක"]);
		expect(host.querySelectorAll(".extreme-digit-circle button")).toHaveLength(
			3,
		);
		expect(host.querySelectorAll(".extreme-place-table td button")).toHaveLength(
			3,
		);
	});

	it("builds and submits the arranged number without revealing it", async () => {
		expect(host.textContent).not.toContain("432");
		const digits = [
			...host.querySelectorAll<HTMLButtonElement>(
				".extreme-digit-circle button",
			),
		];
		await act(async () => digits[1].click());
		expect(host.querySelectorAll(".extreme-digit-circle button")).toHaveLength(
			3,
		);
		expect(
			host.querySelectorAll(".extreme-digit-circle button:disabled"),
		).toHaveLength(1);
		await act(async () => digits[2].click());
		await act(async () => digits[0].click());

		expect(onChange).toHaveBeenLastCalledWith({
			kind: "digit_order",
			digits: [4, 3, 2],
		});
		expect(host.querySelector(".extreme-place-table tbody")?.textContent).toBe(
			"432",
		);
	});

	it("keeps the third card tappable in the three-digit smallest-number activity", async () => {
		await act(async () =>
			root.render(
				<Kite
					game={{ digits: [7, 0, 4], greatest: false }}
					onChange={onChange}
				/>,
			),
		);
		const source = host.querySelector(".extreme-digit-circle--3");
		if (!source) throw new Error("three-card source missing");
		const cards = [...source.querySelectorAll<HTMLButtonElement>("button")];
		await act(async () => cards[2].click());
		expect(host.querySelector(".extreme-place-table tbody")?.textContent).toBe("4??");
		await act(async () => cards[1].click());
		await act(async () => cards[0].click());
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "digit_order",
			digits: [4, 0, 7],
		});
	});
});
