import { describe, expect, it } from "vitest";
import {
	exhibitMappingResponse,
	pastBilingualResponse,
} from "../heritageLogic";

describe("Heritage Museum semantic responses", () => {
	it("constructs a complete bilingual mapping without semantic answer data", () => {
		const response = pastBilingualResponse(
			"command",
			[{ sequence: 1, source: "source-a", target: "target-b" }],
			["source-a"],
			["select:source-a", "place:target-b"],
		);
		expect(response.kind).toBe("past_bilingual_links");
		if (response.kind !== "past_bilingual_links")
			throw new Error("wrong response kind");
		expect(response.unlinked_english_tokens).toEqual([]);
		expect(JSON.stringify(response)).not.toContain("Timber");
	});

	it("tracks exhibit placement revisions", () => {
		const response = exhibitMappingResponse(
			"command",
			[{ sequence: 1, source: "source-a", target: "target-a" }],
			["source-a", "source-b"],
			["replace:target-a"],
		);
		expect(response.kind).toBe("heritage_exhibit_mapping");
		if (response.kind !== "heritage_exhibit_mapping")
			throw new Error("wrong response kind");
		expect(response.unplaced_word_tokens).toEqual(["source-b"]);
		expect(response.revisions).toBe(1);
	});
});
