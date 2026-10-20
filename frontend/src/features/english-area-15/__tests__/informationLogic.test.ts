import { describe, expect, it } from "vitest";
import { bilingualResponse, objectResponse } from "../informationLogic";
describe("information responses", () => {
	it("builds bilingual links", () =>
		expect(
			bilingualResponse(
				"c",
				[{ sequence: 1, source: "e", target: "s" }],
				["e"],
				["link:s"],
			),
		).toMatchObject({
			kind: "information_bilingual_links",
			unlinked_english_tokens: [],
		}));
	it("builds object mappings without answers", () =>
		expect(
			objectResponse(
				"c",
				[{ sequence: 1, source: "w", target: "o" }],
				["w"],
				["place:o"],
			),
		).toMatchObject({
			kind: "information_object_mapping",
			unplaced_word_tokens: [],
		}));
});
