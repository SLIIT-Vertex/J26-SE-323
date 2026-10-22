import { describe, expect, it } from "vitest";
import {
	netMatchResponse,
	orientationResponse,
	shapeTableResponse,
} from "../shapeLogic";

describe("shape adventure evidence", () => {
	it("builds complete table evidence only after every cell is filled", () => {
		const ids = ["cube", "cylinder"];
		expect(shapeTableResponse(ids, {})).toBeNull();
		const response = shapeTableResponse(ids, {
			"cube:faces": 6,
			"cube:vertices": 8,
			"cube:edges": 12,
			"cylinder:faces": 2,
			"cylinder:vertices": 0,
			"cylinder:edges": 2,
		});
		expect(response).toEqual(
			expect.objectContaining({
				kind: "shape_property_table",
				rows: [
					{ solid_id: "cube", faces: 6, vertices: 8, edges: 12 },
					{ solid_id: "cylinder", faces: 2, vertices: 0, edges: 2 },
				],
			}),
		);
	});
	it("preserves ordered orientation and matching evidence", () => {
		expect(
			orientationResponse(["shelf", "plumb_line"], {
				shelf: "horizontal",
				plumb_line: "vertical",
			})?.selections,
		).toHaveLength(2);
		expect(
			netMatchResponse(["cube"], { cube: "cube" }, ["match:cube:cube"]),
		).toEqual({
			kind: "solid_net_match",
			matches: [{ solid_id: "cube", net_id: "cube" }],
			interaction_trace: ["match:cube:cube"],
		});
	});
});
