import { describe, expect, it } from "vitest";
import { flowerMappingResponse } from "../bloomBuilderLogic";

describe("flowerMappingResponse", () => {
	it("constructs a complete semantic flower response with detail evidence", () => {
		const response = flowerMappingResponse("cmd", [{ sequence: 1, source: "w-1", target: "f-1" }], ["w-1"], ["select:w-1", "place:f-1"], 2);
		expect(response.kind).toBe("flower_vocabulary_mapping");
		if (response.kind !== "flower_vocabulary_mapping") throw new Error("wrong response kind");
		expect(response.unplaced_word_tokens).toEqual([]);
		expect(response.detail_sheet_open_count).toBe(2);
	});
});
