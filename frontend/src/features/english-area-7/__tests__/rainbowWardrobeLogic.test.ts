import { describe, expect, it } from "vitest";
import { wardrobeMappingResponse } from "../rainbowWardrobeLogic";

describe("wardrobeMappingResponse", () => {
	it("keeps opaque garment mappings and interaction evidence", () => {
		const response = wardrobeMappingResponse(
			"cmd",
			[{ sequence: 1, source: "w-1", target: "g-1" }],
			["w-1", "w-2"],
			["select:w-1", "replace:g-1"],
		);
		expect(response.kind).toBe("clothes_vocabulary_mapping");
		if (response.kind !== "clothes_vocabulary_mapping")
			throw new Error("wrong response kind");
		expect(response.unplaced_word_tokens).toEqual(["w-2"]);
		expect(response.revisions).toBe(1);
	});
});
