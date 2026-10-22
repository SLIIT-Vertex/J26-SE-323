import { describe, expect, it } from "vitest";
import { bilingualResponse, sceneResponse } from "../earthSkyLogic";

describe("Earth & Sky Explorer responses", () => {
	it("builds complete bilingual semantic links", () => {
		const response = bilingualResponse(
			"cmd",
			[{ sequence: 1, source: "e1", target: "s2" }],
			["e1"],
			["select:e1", "link:s2"],
		);
		expect(response).toMatchObject({
			kind: "earth_sky_bilingual_links",
			unlinked_english_tokens: [],
			tap_alternative_used: true,
		});
	});
	it("records scene replacements without embedding an answer map", () => {
		const response = sceneResponse(
			"cmd",
			[{ sequence: 1, source: "w1", target: "c2" }],
			["w1", "w2"],
			["replace:c2"],
		);
		expect(response).toMatchObject({
			kind: "earth_sky_scene_mapping",
			unplaced_word_tokens: ["w2"],
			revisions: 1,
		});
		expect(response).not.toHaveProperty("target_mapping");
	});
});
