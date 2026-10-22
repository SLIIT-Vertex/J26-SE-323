import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type StudioLink = { sequence: number; source: string; target: string };
const revisions = (trace: string[]) =>
	trace.filter(
		(entry) => entry.startsWith("replace") || entry.startsWith("clear"),
	).length;

export function functionSortResponse(
	command: string,
	links: StudioLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "classroom_function_sort",
		command_token: command,
		placements: links.map((link) => ({
			sequence: link.sequence,
			expression_token: link.source,
			heading_token: link.target,
		})),
		unplaced_expression_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}

export function contextLinkResponse(
	command: string,
	links: StudioLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "classroom_context_expression_links",
		command_token: command,
		links: links.map((link) => ({
			sequence: link.sequence,
			situation_token: link.source,
			expression_token: link.target,
		})),
		unlinked_situation_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_link_count: 0,
		tap_alternative_used: true,
	};
}

export function commandActionResponse(
	command: string,
	actor: string,
	action: string,
	finalState: string,
	trace: string[],
): ConstructedResponse {
	return {
		kind: "classroom_command_action",
		command_token: command,
		actions: [
			{
				sequence: 1,
				actor_token: actor,
				action_token: action,
				target_token: null,
			},
		],
		final_scene_state: [finalState],
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_action_count: 0,
		tap_alternative_used: true,
	};
}

export function questionSequenceResponse(
	command: string,
	prompt: string,
	ordered: string[],
	all: string[],
	placeholder: string | null,
	trace: string[],
): ConstructedResponse {
	return {
		kind: "classroom_question_sequence",
		command_token: command,
		prompt_token: prompt,
		ordered_chunk_tokens: ordered,
		placeholder_token: placeholder,
		unused_chunk_tokens: all.filter((token) => !ordered.includes(token)),
		interaction_trace: trace,
		revisions: revisions(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}
