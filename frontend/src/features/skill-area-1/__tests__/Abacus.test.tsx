import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Abacus } from "../NumberWorldJourney";

describe("Number World abacus", () => {
	let host: HTMLDivElement;
	let root: Root;
	const onChange = vi.fn();

	beforeEach(async () => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
		onChange.mockReset();
		await act(async () => root.render(<Abacus game={{}} onChange={onChange} />));
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("renders one frame, six rods, and accessible 48px step controls", () => {
		const frame = host.querySelector<HTMLImageElement>(".abacus-frame");
		expect(frame?.getAttribute("src")).toContain("abacus-frame.png");
		expect(frame?.getAttribute("alt")).toBe("");
		expect(host.querySelectorAll(".abacus-frame-rod")).toHaveLength(6);
		expect(host.querySelectorAll(".abacus-rod-control")).toHaveLength(6);
		expect(host.querySelectorAll(".abacus-step-button")).toHaveLength(12);

		const add = host.querySelector<HTMLButtonElement>(
			'[aria-label="දස දහස් තැනට එකක් එකතු කරන්න"]',
		);
		const remove = host.querySelector<HTMLButtonElement>(
			'[aria-label="දස දහස් තැනින් එකක් ඉවත් කරන්න"]',
		);
		expect(add?.classList.contains("abacus-step-button--increment")).toBe(true);
		expect(remove?.classList.contains("abacus-step-button--decrement")).toBe(
			true,
		);
		expect(add?.disabled).toBe(false);
		expect(remove?.disabled).toBe(true);
	});

	it("updates the selected rod, number, expanded form, and submitted response", async () => {
		const add = host.querySelector<HTMLButtonElement>(
			'[aria-label="දස දහස් තැනට එකක් එකතු කරන්න"]',
		);
		const remove = host.querySelector<HTMLButtonElement>(
			'[aria-label="දස දහස් තැනින් එකක් ඉවත් කරන්න"]',
		);
		if (!add || !remove) throw new Error("abacus controls missing");

		await act(async () => add.click());
		await act(async () => add.click());

		expect(host.querySelector("[data-abacus-number]")?.textContent).toBe(
			"20,000",
		);
		expect(
			host.querySelector("[data-abacus-expanded]")?.getAttribute(
				"data-abacus-expanded",
			),
		).toBe("20000");
		expect(host.querySelectorAll(".abacus-frame-rod:nth-child(2) .abacus-bead")).toHaveLength(2);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "bead_placement",
			rods: [0, 2, 0, 0, 0, 0],
		});

		await act(async () => remove.click());
		expect(host.querySelector("[data-abacus-number]")?.textContent).toBe(
			"10,000",
		);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "bead_placement",
			rods: [0, 1, 0, 0, 0, 0],
		});
	});

	it("keeps every rod between zero and nine", async () => {
		const add = host.querySelector<HTMLButtonElement>(
			'[aria-label="එක තැනට එකක් එකතු කරන්න"]',
		);
		const remove = host.querySelector<HTMLButtonElement>(
			'[aria-label="එක තැනින් එකක් ඉවත් කරන්න"]',
		);
		if (!add || !remove) throw new Error("ones controls missing");

		for (let count = 0; count < 10; count += 1) {
			await act(async () => add.click());
		}
		expect(add.disabled).toBe(true);
		expect(host.querySelectorAll(".abacus-frame-rod:last-child .abacus-bead")).toHaveLength(9);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "bead_placement",
			rods: [0, 0, 0, 0, 0, 9],
		});

		for (let count = 0; count < 10; count += 1) {
			await act(async () => remove.click());
		}
		expect(remove.disabled).toBe(true);
		expect(host.querySelectorAll(".abacus-frame-rod:last-child .abacus-bead")).toHaveLength(0);
		expect(onChange).toHaveBeenLastCalledWith({
			kind: "bead_placement",
			rods: [0, 0, 0, 0, 0, 0],
		});
	});
});
