import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	ChildPlaceScene,
	DirectionActivity,
	DirectionCompass,
	DirectionWorkedDemo,
} from "../DirectionAdventureJourney";
import { DIRECTION_GAMES, DIRECTION_SKILLS } from "../manifest";

describe("Direction Adventure", () => {
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

	it("contains exactly two games and three progress activities", () => {
		expect(DIRECTION_GAMES).toHaveLength(2);
		expect(DIRECTION_SKILLS).toHaveLength(3);
		expect(DIRECTION_GAMES.map((game) => game.challengeLabel)).toEqual([
			"අභියෝග 2ක්",
			"අභියෝග 1ක්",
		]);
	});

	it("renders all eight code-drawn arrows within 320px", async () => {
		await act(async () => root.render(<DirectionCompass />));
		expect(host.querySelectorAll("svg line")).toHaveLength(8);
		expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});

	it("keeps four labelled 48px primary dropdowns attached to compass positions and emits evidence", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<DirectionActivity
					game={{
						response_kind: "main_direction_compass",
						active_positions: ["top", "right", "bottom", "left"],
						direction_options: ["north", "east", "south", "west"],
					}}
					onResponse={onResponse}
				/>,
			),
		);
		const selects = [...host.querySelectorAll("select")] as HTMLSelectElement[];
		expect(selects).toHaveLength(4);
		expect(selects.map((select) => select.getAttribute("aria-label"))).toEqual(
			expect.arrayContaining([
				expect.stringContaining("ඉහළ"),
				expect.stringContaining("වම"),
			]),
		);
		expect(getComputedStyle(selects[0]).minHeight).toBe("48px");
		for (const [index, value] of ["north", "east", "south", "west"].entries()) {
			await act(async () => {
				selects[index].value = value;
				selects[index].dispatchEvent(new Event("change", { bubbles: true }));
			});
		}
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "main_direction_compass",
				selection_order: ["top", "right", "bottom", "left"],
			}),
		);
	});

	it("renders every scene direction and child-centred place exactly once", async () => {
		const directions = [
			"north",
			"north_east",
			"east",
			"south_east",
			"south",
			"south_west",
			"west",
			"north_west",
		] as const;
		const places = [
			"dagoba",
			"mango_tree",
			"house",
			"school",
			"shop",
			"gate",
			"coconut_tree",
			"post_office",
		];
		await act(async () =>
			root.render(
				<ChildPlaceScene
					placements={places.map((place_id, index) => ({
						place_id,
						direction: directions[index],
						label_si: place_id,
					}))}
				/>,
			),
		);
		expect(host.querySelectorAll(".scene-place")).toHaveLength(8);
		expect(host.querySelectorAll(".scene-child")).toHaveLength(1);
		expect(
			new Set(
				[...host.querySelectorAll(".scene-place")].map((node) =>
					node.getAttribute("data-place"),
				),
			).size,
		).toBe(8);
	});

	it("reveals the exact failed compass answer in worked support", async () => {
		await act(async () =>
			root.render(
				<DirectionWorkedDemo
					stage={4}
					example={{
						prompt_si: "මාලිමාව",
						steps_si: ["1", "2", "3"],
						game: {
							response_kind: "main_direction_compass",
							active_positions: ["top", "right", "bottom", "left"],
							direction_options: ["north", "east", "south", "west"],
						},
						correct_response: {
							selections: [
								{ position: "top", direction: "north" },
								{ position: "right", direction: "east" },
								{ position: "bottom", direction: "south" },
								{ position: "left", direction: "west" },
							],
						},
					}}
				/>,
			),
		);
		expect(
			[...host.querySelectorAll("select")].map(
				(node) => (node as HTMLSelectElement).value,
			),
		).toEqual(["north", "east", "south", "west"]);
	});
});
