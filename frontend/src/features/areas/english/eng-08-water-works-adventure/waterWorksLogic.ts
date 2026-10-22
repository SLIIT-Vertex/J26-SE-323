import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";

export type WaterLink = { sequence: number; source: string; target: string };

export const SCENE_MARKS = ["🛁", "🍲", "🧼", "🥤", "🌱"] as const;

export function waterActionResponse(
	commandToken: string,
	links: WaterLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "water_action_mapping",
		command_token: commandToken,
		placements: links.map((link) => ({
			sequence: link.sequence,
			action_token: link.source,
			scene_token: link.target,
		})),
		unplaced_action_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
