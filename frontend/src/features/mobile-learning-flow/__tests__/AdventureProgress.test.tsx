import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import {
	adaptiveGameProgressStage,
	AdventureProgress,
} from "../AdventureProgress";

describe("adaptive game progress", () => {
	it("maps the journey phases to all four visible stages", () => {
		expect(adaptiveGameProgressStage("question", "unsupported_before")).toBe(1);
		expect(adaptiveGameProgressStage("support", "supported_practice")).toBe(2);
		expect(adaptiveGameProgressStage("question", "unsupported_after")).toBe(3);
		expect(adaptiveGameProgressStage("result", "unsupported_after")).toBe(4);
	});

	it("moves the current marker and completes earlier numbers without a star", async () => {
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);

		await act(async () => root.render(<AdventureProgress stage={3} />));

		const items = [...host.querySelectorAll("span")];
		expect(host.querySelector("[data-progress-stage='3']")).not.toBeNull();
		expect(items.map((item) => item.className)).toEqual([
			"is-done",
			"is-done",
			"is-current",
		]);
		expect(host.querySelector("[aria-current='step']")?.childNodes[0]?.textContent).toBe("3");

		await act(async () => root.unmount());
		host.remove();
	});

	it("keeps the numbered three-step progress when a game has fewer activities", async () => {
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);

		await act(async () =>
			root.render(<AdventureProgress stage={1} activityCount={1} />),
		);

		expect(
			[...host.querySelectorAll("span")].map((item) => item.textContent),
		).toEqual(["1", "2", "3"]);

		await act(async () => root.unmount());
		host.remove();
	});

	it("shows exactly five activity markers for the division journey", async () => {
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);
		await act(async () => root.render(<AdventureProgress stage={1} activityCount={5} currentActivity={3} completedActivities={2} />));
		expect(host.querySelectorAll("span")).toHaveLength(5);
		expect(host.querySelector("[data-activity-count='5']")).not.toBeNull();
		expect(host.querySelector("[aria-current='step']")?.childNodes[0]?.textContent).toBe("3");
		await act(async () => root.unmount());
		host.remove();
	});
});
