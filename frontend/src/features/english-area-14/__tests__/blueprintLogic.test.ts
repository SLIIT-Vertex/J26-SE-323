import { describe, expect, it } from "vitest";
import {
	groupResponse,
	sequenceResponse,
	vocabularyResponse,
} from "../blueprintLogic";
describe("blueprint responses", () => {
	it("builds mappings", () => {
		expect(
			vocabularyResponse(
				"c",
				[{ sequence: 1, source: "w", target: "s" }],
				["w"],
				["place:s"],
			),
		).toMatchObject({
			kind: "place_vocabulary_mapping",
			unplaced_word_tokens: [],
		});
		expect(
			groupResponse(
				"c",
				[{ sequence: 1, source: "e", target: "h" }],
				["e"],
				["sort:h"],
			),
		).toMatchObject({
			kind: "lesson_place_group_sort",
			unplaced_entry_tokens: [],
		});
	});
	it("builds sequence", () =>
		expect(
			sequenceResponse("c", "p", ["a", "b"], ["a", "b"], ["slot:2"]),
		).toMatchObject({ kind: "place_name_sequence", unused_chunk_tokens: [] }));
});
