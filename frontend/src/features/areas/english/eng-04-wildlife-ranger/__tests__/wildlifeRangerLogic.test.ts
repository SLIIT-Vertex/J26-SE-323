import { describe, expect, it } from "vitest";
import { wildlifeMappingResponse } from "../wildlifeRangerLogic";

describe("wildlife ranger responses", () => {
	it.each(["animal_vocabulary_mapping", "lesson_heading_sort"] as const)(
		"serializes complete %s evidence",
		(kind) => {
			const response = wildlifeMappingResponse(
				kind,
				"cmd",
				[{ sequence: 1, source: "entry", target: "target" }],
				["entry"],
				["place:entry:target"],
			);
			expect(response).toMatchObject({
				kind,
				command_token: "cmd",
				unplaced_entry_tokens: [],
				placements: [{ entry_token: "entry", target_token: "target" }],
			});
		},
	);
	it("serializes body-part labels with server token direction", () => {
		const response = wildlifeMappingResponse(
			"animal_part_labeling",
			"cmd",
			[{ sequence: 1, source: "label", target: "part" }],
			["label"],
			["place:label:part"],
		);
		expect(response).toMatchObject({
			kind: "animal_part_labeling",
			unfilled_part_tokens: [],
			labels: [{ entry_token: "label", target_token: "part" }],
		});
	});
});
