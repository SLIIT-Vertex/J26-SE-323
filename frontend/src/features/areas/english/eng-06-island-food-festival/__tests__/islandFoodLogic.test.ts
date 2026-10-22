import { describe, expect, it } from "vitest";
import { foodMappingResponse, foodNameResponse } from "../islandFoodLogic";

describe("island food responses", () => {
	it("serializes vocabulary mappings", () => {
		expect(
			foodMappingResponse(
				"food_vocabulary_mapping",
				"cmd",
				[{ sequence: 1, source: "word", target: "food" }],
				["word"],
				["place"],
			),
		).toMatchObject({
			kind: "food_vocabulary_mapping",
			unplaced_word_tokens: [],
			placements: [{ word_token: "word", food_token: "food" }],
		});
	});
	it("serializes lesson stall sorting", () => {
		expect(
			foodMappingResponse(
				"food_lesson_group_sort",
				"cmd",
				[{ sequence: 1, source: "entry", target: "stall" }],
				["entry"],
				["place"],
			),
		).toMatchObject({
			kind: "food_lesson_group_sort",
			unplaced_entry_tokens: [],
			placements: [{ entry_token: "entry", stall_token: "stall" }],
		});
	});
	it("preserves ordered whole-word chunks", () => {
		expect(
			foodNameResponse("cmd", "food", ["Rice", "and", "Curry"], ["slot:1"]),
		).toMatchObject({
			kind: "food_name_sequence",
			food_token: "food",
			ordered_chunk_tokens: ["Rice", "and", "Curry"],
		});
	});
});
