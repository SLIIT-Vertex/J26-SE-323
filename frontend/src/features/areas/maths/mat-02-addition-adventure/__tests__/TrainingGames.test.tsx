import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CrystalFlight } from "../CrystalFlight";
import { NumberFactory } from "../NumberFactory";

const flight = vi.hoisted(() => ({ collect: vi.fn(), destroy: vi.fn() }));
const factory = vi.hoisted(() => ({
	show: vi.fn(),
	refuse: vi.fn(),
	destroy: vi.fn(),
}));
vi.mock("../crystalScene", () => ({
	mountCrystalFlight: vi.fn(async () => flight),
}));
vi.mock("../factoryScene", () => ({
	mountFactory: vi.fn(async () => factory),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

function byLabel(host: HTMLElement, label: string) {
	const element = host.querySelector<HTMLButtonElement>(
		`[aria-label="${label}"]`,
	);
	if (!element) throw new Error(`missing ${label}`);
	return element;
}

describe("Training games", () => {
	let host: HTMLDivElement;
	let root: Root;

	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
		vi.clearAllMocks();
	});

	it("flies through every crystal before the energy total can be set", async () => {
		const onResponse = vi.fn();
		await act(async () => {
			root.render(
				<CrystalFlight
					values={[8, 3]}
					reducedMotion
					evidence={evidence}
					onResponse={onResponse}
				/>,
			);
		});
		expect(host.querySelector(".crystal-total")?.hasAttribute("disabled")).toBe(
			true,
		);
		await act(async () => {
			byLabel(host, "ශක්තිය 8 ඇති ස්ඵටිකය එකතු කරන්න").click();
			byLabel(host, "ශක්තිය 3 ඇති ස්ඵටිකය එකතු කරන්න").click();
		});
		expect(flight.collect).toHaveBeenCalledTimes(2);
		expect(host.querySelector(".crystal-instruction")?.textContent).toBe(
			"මුළු ශක්තිය කීයද?",
		);
		await act(async () => {
			for (let at = 0; at < 11; at++) byLabel(host, "ශක්තිය වැඩි කරන්න").click();
		});
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "combine_quantities",
			combined: true,
			total: 11,
		});
	});

	it("shows a finished machine that cannot be touched as a worked example", async () => {
		const onResponse = vi.fn();
		await act(async () => {
			root.render(
				<NumberFactory
					addends={[382, 728, 298]}
					demo
					reducedMotion
					evidence={evidence}
					onResponse={onResponse}
				/>,
			);
		});
		expect(factory.show).toHaveBeenCalledWith([8, 0, 4, 1], { type: "set" });
		const digits = [...host.querySelectorAll(".factory-digit strong")].map(
			(digit) => digit.textContent,
		);
		expect(digits).toEqual(["1", "4", "0", "8"]);
		const enabled = [...host.querySelectorAll("button")].filter(
			(button) => !button.matches(":disabled"),
		);
		expect(enabled).toHaveLength(0);
		expect(onResponse).toHaveBeenLastCalledWith(null);
	});

	it("shows the answer faintly behind unset wheels in a help stage", async () => {
		await act(async () => {
			root.render(
				<NumberFactory
					addends={[458, 379]}
					hint
					reducedMotion
					evidence={evidence}
					onResponse={vi.fn()}
				/>,
			);
		});
		const ghosts = [
			...host.querySelectorAll(".factory-digit[data-ghost] strong"),
		].map((digit) => digit.textContent);
		expect(ghosts).toEqual(["8", "3", "7"]);
	});
});
