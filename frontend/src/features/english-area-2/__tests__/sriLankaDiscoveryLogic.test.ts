import { describe, expect, it } from "vitest";
import { groupingResponse, mappingResponse } from "../sriLankaDiscoveryLogic";

describe("Sri Lanka Discovery response builders", () => {
	it("builds a complete semantic label response", () => {
		const response = mappingResponse(
			"semantic_label_mapping",
			"opaque",
			[{ sequence: 1, sourceId: "l1", destinationId: "d1" }],
			["l1"],
			["place:l1:d1"],
		);
		expect(response.kind).toBe("semantic_label_mapping");
		if (response.kind === "semantic_label_mapping")
			expect(response.unplaced_label_ids).toEqual([]);
	});

	it("retains every grouping member", () => {
		const response = groupingResponse(
			"opaque",
			{ g1: ["m1"], g2: ["m2"] },
			["m1", "m2"],
			["group:m1:g1", "group:m2:g2"],
		);
		expect(response.kind).toBe("semantic_grouping");
		if (response.kind === "semantic_grouping")
			expect(response.unassigned_member_ids).toEqual([]);
	});
});
