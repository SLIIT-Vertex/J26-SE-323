import { describe, expect, it } from "vitest";
import {
	objectMappingResponse,
	objectNameResponse,
} from "../everydayObjectLogic";

describe("everyday object responses", () => {
	it("serializes vocabulary mappings", () => {
		expect(
			objectMappingResponse(
				"object_vocabulary_mapping",
				"cmd",
				[{ sequence: 1, source: "word", target: "object" }],
				["word"],
				["place"],
			),
		).toMatchObject({
			kind: "object_vocabulary_mapping",
			unplaced_word_tokens: [],
			placements: [{ word_token: "word", object_token: "object" }],
		});
	});
	it("serializes lesson-place sorting", () => {
		expect(
			objectMappingResponse(
				"lesson_place_sort",
				"cmd",
				[{ sequence: 1, source: "entry", target: "zone" }],
				["entry"],
				["place"],
			),
		).toMatchObject({
			kind: "lesson_place_sort",
			unplaced_entry_tokens: [],
			placements: [{ entry_token: "entry", zone_token: "zone" }],
		});
	});
	it("preserves ordered whole-word chunks", () => {
		expect(
			objectNameResponse(
				"cmd",
				"object",
				["first", "second"],
				["slot:first", "slot:second"],
			),
		).toMatchObject({
			kind: "object_name_sequence",
			object_token: "object",
			ordered_chunk_tokens: ["first", "second"],
		});
	});
});
