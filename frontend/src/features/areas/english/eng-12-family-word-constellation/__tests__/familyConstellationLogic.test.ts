import { describe, expect, it } from "vitest";
import { familyLinkResponse } from "../familyConstellationLogic";

describe("family bilingual links", () => {
	it("serializes lesson-word links without a client answer map", () => {
		expect(
			familyLinkResponse(
				"cmd",
				[{ sequence: 1, source: "en", target: "si" }],
				["en"],
				["link:si"],
			),
		).toMatchObject({
			kind: "family_bilingual_links",
			unlinked_english_tokens: [],
			links: [{ english_token: "en", sinhala_token: "si" }],
		});
	});
});
