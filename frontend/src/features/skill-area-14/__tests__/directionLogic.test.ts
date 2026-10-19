import { describe, expect, it } from "vitest";
import { compassResponse, sceneResponse } from "../directionLogic";

describe("direction evidence builders", () => {
	it("emits ordered primary compass evidence only when complete", () => {
		const positions = ["top", "right", "bottom", "left"] as const;
		expect(
			compassResponse(
				"main_direction_compass",
				[...positions],
				{ top: "north" },
				["top"],
			),
		).toBeNull();
		expect(
			compassResponse(
				"main_direction_compass",
				[...positions],
				{
					top: "north",
					right: "east",
					bottom: "south",
					left: "west",
				},
				[...positions],
			),
		).toEqual({
			kind: "main_direction_compass",
			selections: [
				{ position: "top", direction: "north" },
				{ position: "right", direction: "east" },
				{ position: "bottom", direction: "south" },
				{ position: "left", direction: "west" },
			],
			selection_order: [...positions],
		});
	});

	it("preserves scene, place, order, and revision evidence", () => {
		const statements = [
			{ statement_id: "s1", place_id: "dagoba", template_si: "___" },
		];
		expect(
			sceneResponse("scene-1", statements, { s1: "north" }, ["s1"], 2),
		).toEqual({
			kind: "place_direction_scene",
			scene_id: "scene-1",
			selections: [
				{ statement_id: "s1", place_id: "dagoba", selected_direction: "north" },
			],
			selection_order: ["s1"],
			revisions: 2,
		});
	});
});
