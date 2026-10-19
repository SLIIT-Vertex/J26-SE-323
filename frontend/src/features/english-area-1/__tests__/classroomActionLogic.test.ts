import { describe, expect, it } from "vitest";
import { bodyStateResponse, navigationResponse } from "../classroomActionLogic";

describe("classroom action response builders", () => {
	it("creates semantic body-state evidence", () => {
		const response = bodyStateResponse("bend", "bend", ["pose:bend"], 0);
		expect(response).toMatchObject({
			kind: "body_state",
			command_id: "bend",
			final_body_state: { posture: "bent", arm_position: "down", orientation: "front", seat_state: "standing" },
			semantic_action_id: "bend",
		});
	});
	it("preserves the ordered movement path and origin", () => {
		const response = navigationResponse("come_back", "start-a", "start-a", ["move:wall-zone", "move:start-a"], 1, 0);
		expect(response).toMatchObject({
			kind: "classroom_navigation",
			origin_id: "start-a",
			final_location_id: "start-a",
			movement_path: [
				{ sequence: 1, action: "move", destination_id: "wall-zone" },
				{ sequence: 2, action: "move", destination_id: "start-a" },
			],
		});
	});
});
