import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	CompoundDistanceTable,
	DistanceActivity,
} from "../DistanceAdventureJourney";
import { DISTANCE_GAMES, DISTANCE_SKILLS } from "../manifest";
describe("Distance Adventure", () => {
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
	it("contains exactly three games and five activities", () => {
		expect(DISTANCE_GAMES.map((g) => g.challengeCount)).toEqual([2, 2, 1]);
		expect(DISTANCE_SKILLS).toHaveLength(5);
		expect(
			DISTANCE_GAMES.every((game) =>
				game.asset.startsWith("/curriculum/game/G5-AREA-MAT-09/"),
			),
		).toBe(true);
	});
	it("renders aligned km/m working cells with accessible 48px targets", async () => {
		await act(async () =>
			root.render(
				<CompoundDistanceTable
					game={{
						operation: "add",
						left_kilometres: 3,
						left_metres: 650,
						right_kilometres: 2,
						right_metres: 475,
					}}
				/>,
			),
		);
		expect(host.querySelectorAll(".distance-cell")).toHaveLength(4);
		expect(host.textContent).toContain("1000 m ⇄ 1 km");
		expect(
			getComputedStyle(host.querySelector(".distance-cell") as HTMLElement)
				.minHeight,
		).toBe("48px");
		expect(host.querySelector('[aria-label="අවසාන km"]')).not.toBeNull();
	});
	it("submits conversion evidence including zero-padded formal metres", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<DistanceActivity
					game={{ response_kind: "distance_conversion", source_value: 4075 }}
					onResponse={onResponse}
				/>,
			),
		);
		const click = async (label: string, digit: number) => {
			await act(async () =>
				(
					host.querySelector(`[aria-label="${label}"]`) as HTMLButtonElement
				).click(),
			);
			await act(async () =>
				(
					host.querySelector(`[aria-label="අංක ${digit}"]`) as HTMLButtonElement
				).click(),
			);
		};
		await click("කිලෝමීටර් ගණන", 4);
		await click("ඉතිරි මීටර් ඉලක්කම් තුනකින්", 7);
		await act(async () =>
			(host.querySelector('[aria-label="අංක 5"]') as HTMLButtonElement).click(),
		);
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "distance_conversion",
			source_value: 4075,
			source_unit: "m",
			kilometres: 4,
			metres: 75,
			total_metres: 4075,
			formal_metres: "075",
		});
	});
});
