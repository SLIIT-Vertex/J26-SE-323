import { describe, expect, it } from "vitest";
import {
	numberPairResponse,
	plantMappingResponse,
} from "../plantExplorerLogic";

describe("plant explorer constructed responses", () => {
	it("serializes a complete garden vocabulary mapping", () => {
		const response = plantMappingResponse(
			"plant_vocabulary_mapping",
			"cmd-1",
			[
				{ sequence: 1, source: "word-roots", target: "target-roots" },
				{ sequence: 2, source: "word-leaves", target: "target-leaves" },
			],
			["word-roots", "word-leaves"],
			["place:word-roots:target-roots", "replace:word-leaves:target-leaves"],
		);

		expect(response).toMatchObject({
			kind: "plant_vocabulary_mapping",
			command_token: "cmd-1",
			revisions: 1,
			unplaced_word_tokens: [],
		});
	});

	it("keeps part and label token direction compatible with server scoring", () => {
		const response = plantMappingResponse(
			"plant_part_labeling",
			"cmd-2",
			[{ sequence: 1, source: "label-stem", target: "part-stem" }],
			["label-stem"],
			["place:label-stem:part-stem"],
		);

		expect(response).toMatchObject({
			kind: "plant_part_labeling",
			labels: [
				{ sequence: 1, part_token: "part-stem", label_token: "label-stem" },
			],
			unfilled_part_tokens: [],
		});
	});

	it("serializes singular and plural choices without leaking answer keys", () => {
		const response = numberPairResponse(
			"cmd-3",
			[
				{
					concept_token: "leaf",
					singular_form_token: "leaf-one",
					plural_form_token: "leaf-many",
				},
			],
			["singular:leaf-one:leaf", "plural:leaf-many:leaf"],
		);

		expect(response).toMatchObject({
			kind: "singular_plural_pairing",
			command_token: "cmd-3",
			pairs: [
				{
					concept_token: "leaf",
					singular_form_token: "leaf-one",
					plural_form_token: "leaf-many",
				},
			],
		});
	});
});
