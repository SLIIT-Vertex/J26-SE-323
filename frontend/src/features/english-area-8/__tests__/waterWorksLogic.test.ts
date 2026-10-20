import { describe, expect, it } from "vitest";
import { waterActionResponse } from "../waterWorksLogic";

describe("water action responses", () => {
	it("serializes action-to-scene mappings without a client answer map", () => {
		expect(
			waterActionResponse(
				"cmd",
				[{ sequence: 1, source: "action", target: "scene" }],
				["action"],
				["route:scene"],
			),
		).toMatchObject({
			kind: "water_action_mapping",
			unplaced_action_tokens: [],
			placements: [{ action_token: "action", scene_token: "scene" }],
		});
	});
});
