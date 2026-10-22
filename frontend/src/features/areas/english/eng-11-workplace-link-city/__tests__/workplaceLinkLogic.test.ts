import { describe, expect, it } from "vitest";
import {
	occupationPlaceResponse,
	workVocabularyResponse,
} from "../workplaceLinkLogic";

describe("Workplace Link City responses", () => {
	it("constructs vocabulary mappings", () => {
		const response = workVocabularyResponse(
			"c",
			[{ sequence: 1, source: "w1", target: "r1" }],
			["w1"],
			["place:r1"],
		);
		expect(response.kind).toBe("work_vocabulary_mapping");
	});
	it("allows many occupations to share a place", () => {
		const response = occupationPlaceResponse(
			"c",
			[
				{ sequence: 1, source: "o1", target: "p1" },
				{ sequence: 2, source: "o2", target: "p1" },
			],
			["o1", "o2"],
			["link:p1", "link:p1"],
		);
		expect(response.kind).toBe("occupation_place_links");
		if (response.kind !== "occupation_place_links")
			throw new Error("wrong kind");
		expect(response.links.map((link) => link.place_token)).toEqual([
			"p1",
			"p1",
		]);
	});
});
