import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Harbour } from "../NumberWorldJourney";

const positionGame = {
	skill_id: "G5-MAT-NUM-POSITION-01",
	number: 53_370,
	digit: 7,
};

describe("Number World place-value table", () => {
	let host: HTMLDivElement;
	let root: Root;
	const onChange = vi.fn();

	beforeEach(async () => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
		onChange.mockReset();
		await act(async () =>
			root.render(<Harbour game={positionGame} onChange={onChange} />),
		);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("renders the complete number, highlighted digit, and six ordered headings", () => {
		expect(host.querySelector("[data-question-number]")?.textContent).toBe(
			"53,370",
		);
		expect(host.querySelector(".is-target-digit")?.textContent).toBe("7");
		expect(
			[...host.querySelectorAll(".place-value-table th")].map((heading) =>
				heading.textContent?.replace(/\s+/g, " ").trim(),
			),
		).toEqual([
			"ලක්ෂ100 000",
			"දස දහස්10 000",
			"දහස්1 000",
			"සිය100",
			"දහය10",
			"එක1",
		]);
		expect(host.querySelectorAll(".place-value-table tbody button")).toHaveLength(
			6,
		);
		expect(host.querySelector(".place-value-frame-image")).toBeNull();
	});

	it("starts neutral and lets the learner replace their selected place", async () => {
		const buttons = [
			...host.querySelectorAll<HTMLButtonElement>(
				".place-value-table tbody button",
			),
		];
		expect(buttons.every((button) => button.ariaPressed === "false")).toBe(true);
		expect(host.querySelector("[data-selected-place]")).toBeNull();
		expect(host.textContent).not.toContain("හොඳයි");
		expect(host.textContent).not.toContain("නිවැරදි");

		await act(async () => buttons[3].click());
		expect(buttons[3].ariaPressed).toBe("true");
		expect(host.querySelector("[data-selected-place]")?.textContent).toContain(
			"සිය — 100",
		);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "drag_to_slot",
			selected_place: 2,
		});

		await act(async () => buttons[4].click());
		expect(buttons[3].ariaPressed).toBe("false");
		expect(buttons[4].ariaPressed).toBe("true");
		expect(host.querySelectorAll(".place-value-table td.is-selected")).toHaveLength(
			1,
		);
		expect(host.querySelector("[data-selected-place]")?.textContent).toContain(
			"දහය — 10",
		);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "drag_to_slot",
			selected_place: 1,
		});
	});

	it("highlights the requested unique digit without receiving the answer place", async () => {
		await act(async () =>
			root.render(
				<Harbour
					game={{
						skill_id: "G5-MAT-NUM-REPRESENTED-01",
						number: 57_588,
						digit: 7,
					}}
					onChange={onChange}
				/>,
			),
		);

		expect(host.querySelector("[data-question-number]")?.textContent).toBe(
			"57,588",
		);
		expect(host.querySelectorAll(".is-target-digit")).toHaveLength(1);
		expect(host.querySelector(".is-target-digit")?.textContent).toBe("7");
	});

	it("submits represented value and describes every answer in Sinhala", async () => {
		await act(async () =>
			root.render(
				<Harbour
					game={{ ...positionGame, skill_id: "G5-MAT-NUM-REPRESENTED-01" }}
					onChange={onChange}
				/>,
			),
		);
		const buttons = [
			...host.querySelectorAll<HTMLButtonElement>(
				".place-value-table tbody button",
			),
		];
		expect(
			buttons.every((button) =>
				button.getAttribute("aria-label")?.includes("ඉලක්කම"),
			),
		).toBe(true);

		await act(async () => buttons[4].click());
		expect(host.querySelector("[data-selected-place]")?.textContent).toContain(
			"7 × 10 = 70",
		);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "drag_to_slot",
			represented_value: 70,
		});
	});
});
