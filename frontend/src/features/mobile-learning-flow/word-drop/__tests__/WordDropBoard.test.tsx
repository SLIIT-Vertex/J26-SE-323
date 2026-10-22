import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlantActivity } from "../../../english-area-3/PlantExplorerQuest";
import { FoodActivity } from "../../../english-area-6/IslandFoodFestival";
import { placeWord, WordDropBoard } from "../WordDropBoard";

vi.mock("phaser", () => ({
	default: {
		Scene: class {},
		Game: class {
			events = { emit: vi.fn() };
			destroy = vi.fn();
		},
		AUTO: 0,
		Scale: { FIT: 0, CENTER_BOTH: 0 },
	},
}));
let host: HTMLDivElement, root: Root;
beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});
afterEach(() => {
	act(() => root.unmount());
	host.remove();
});
function click(selector: string, index = 0) {
	const button = host.querySelectorAll<HTMLButtonElement>(selector)[index];
	if (!button) throw new Error(`Missing ${selector}`);
	act(() => button.click());
}
describe("word drop interaction", () => {
	it("reassigns words without duplicates and reindexes after displacing an occupied target", () => {
		expect(
			placeWord(
				[
					{ source: "a", target: "x", sequence: 1 },
					{ source: "b", target: "y", sequence: 2 },
				],
				"a",
				"y",
				true,
			),
		).toEqual([{ source: "a", target: "y", sequence: 1 }]);
	});
	it("allows several foods in the same basket", () => {
		expect(
			placeWord([{ source: "a", target: "x", sequence: 1 }], "b", "x", false),
		).toHaveLength(2);
	});
	it("offers equivalent tap input and clears all placements on reset", async () => {
		const changed = vi.fn();
		await act(async () =>
			root.render(
				<WordDropBoard
					cards={[{ id: "w", label: "Bread" }]}
					targets={[{ id: "b", label: "Basket", emoji: "🧺" }]}
					instruction="Sort"
					onChange={changed}
				/>,
			),
		);
		click(".phaser-board-mirror-cards button");
		click(".phaser-board-mirror-targets button");
		expect(changed.mock.lastCall?.[0]).toMatchObject({
			links: [{ source: "w", target: "b", sequence: 1 }],
			usedTap: true,
		});
		click(".phaser-board-reset");
		expect(changed.mock.lastCall?.[0].links).toEqual([]);
	});
	it("clears a completed food answer when reset instead of keeping a stale submission", async () => {
		const response = vi.fn();
		await act(async () =>
			root.render(
				<FoodActivity
					game={{
						response_kind: "food_vocabulary_mapping",
						command_token: "c",
						words: [{ word_token: "w", text_en: "Bread" }],
						foods: [{ food_token: "f", renderer_variant: 1 }],
					}}
					onResponse={response}
				/>,
			),
		);
		click(".phaser-board-mirror-cards button");
		click(".phaser-board-mirror-targets button");
		expect(response.mock.lastCall?.[0]?.placements).toHaveLength(1);
		click(".phaser-board-reset");
		expect(response.mock.lastCall?.[0]).toBeNull();
	});
	it("uses separate one and three pictures for each plant concept", async () => {
		await act(async () =>
			root.render(
				<PlantActivity
					game={{
						response_kind: "singular_plural_pairing",
						concepts: [{ concept_token: "c", concept_key: "leaf" }],
						forms: [
							{ form_token: "one", text_en: "Leaf" },
							{ form_token: "many", text_en: "Leaves" },
						],
					}}
					onResponse={() => {}}
				/>,
			),
		);
		// One leaf and many leaves are two places on the board, each with its own photo.
		const places = [
			...host.querySelectorAll(".phaser-board-mirror-targets button"),
		].map((button) => button.textContent ?? "");
		expect(places).toHaveLength(2);
		expect(places[0]).toContain("One");
		expect(places[1]).toContain("Many");
		expect(host.textContent).not.toContain("Plant Leaves");
	});
});
