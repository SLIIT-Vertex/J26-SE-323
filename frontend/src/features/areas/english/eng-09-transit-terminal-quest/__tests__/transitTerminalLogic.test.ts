import { describe, expect, it } from "vitest";
import { transportMappingResponse } from "../transitTerminalLogic";

describe("transport vocabulary responses", () => {
	it("serializes ticket mappings without a client answer map", () => {
		expect(
			transportMappingResponse(
				"cmd",
				[{ sequence: 1, source: "word", target: "vehicle" }],
				["word"],
				["place:vehicle"],
			),
		).toMatchObject({
			kind: "transport_vocabulary_mapping",
			unplaced_word_tokens: [],
			placements: [{ word_token: "word", vehicle_token: "vehicle" }],
		});
	});
});
