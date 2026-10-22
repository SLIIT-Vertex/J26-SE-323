import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type BodyActionId =
	| "bend"
	| "stretch_arms"
	| "arms_down"
	| "stand_straight"
	| "turn_around"
	| "sit_down";

const STATES: Record<
	BodyActionId,
	Extract<ConstructedResponse, { kind: "body_state" }>["final_body_state"]
> = {
	bend: {
		posture: "bent",
		arm_position: "down",
		orientation: "front",
		seat_state: "standing",
	},
	stretch_arms: {
		posture: "upright",
		arm_position: "stretched",
		orientation: "front",
		seat_state: "standing",
	},
	arms_down: {
		posture: "upright",
		arm_position: "down",
		orientation: "front",
		seat_state: "standing",
	},
	stand_straight: {
		posture: "straight",
		arm_position: "down",
		orientation: "front",
		seat_state: "standing",
	},
	turn_around: {
		posture: "upright",
		arm_position: "down",
		orientation: "back",
		seat_state: "standing",
	},
	sit_down: {
		posture: "upright",
		arm_position: "down",
		orientation: "front",
		seat_state: "seated",
	},
};

export function bodyStateResponse(
	commandId: string,
	actionId: BodyActionId,
	trace: string[],
	revisions: number,
): ConstructedResponse {
	return {
		kind: "body_state",
		command_id: commandId,
		final_body_state: STATES[actionId],
		semantic_action_id: actionId,
		interaction_trace: trace,
		revisions,
	};
}

export function navigationResponse(
	commandId: string,
	originId: string,
	destinationId: string,
	trace: string[],
	revisions: number,
	invalidDrops: number,
): ConstructedResponse {
	return {
		kind: "classroom_navigation",
		command_id: commandId,
		origin_id: originId,
		movement_path: trace
			.filter((entry) => entry.startsWith("move:"))
			.map((entry, index) => ({
				sequence: index + 1,
				action: "move" as const,
				destination_id: entry.slice(5),
			})),
		final_location_id: destinationId,
		interaction_trace: trace,
		revisions,
		invalid_drops: invalidDrops,
	};
}
