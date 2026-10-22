import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

const revisionCount = (trace: string[]) =>
	trace.filter(
		(entry) => entry.startsWith("replace") || entry.startsWith("clear"),
	).length;

export type ConversationLink = {
	sequence: number;
	question: string;
	response: string;
};

export function pairLinksResponse(
	command: string,
	links: ConversationLink[],
	questions: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "conversation_pair_links",
		command_token: command,
		links: links.map((link) => ({
			sequence: link.sequence,
			question_token: link.question,
			response_token: link.response,
		})),
		unlinked_question_tokens: questions.filter(
			(question) => !links.some((link) => link.question === question),
		),
		interaction_trace: trace,
		revisions: revisionCount(trace),
		invalid_link_count: 0,
		tap_alternative_used: true,
	};
}

export function turnSequenceResponse(
	command: string,
	dialogue: string,
	ordered: Array<{ turn: string; speaker: string }>,
	all: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "conversation_turn_sequence",
		command_token: command,
		dialogue_token: dialogue,
		ordered_turn_tokens: ordered.map((row) => row.turn),
		speaker_assignments: ordered.map((row) => ({
			turn_token: row.turn,
			speaker_token: row.speaker,
		})),
		unused_turn_tokens: all.filter(
			(token) => !ordered.some((row) => row.turn === token),
		),
		interaction_trace: trace,
		revisions: revisionCount(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}

export function profileReplyResponse(
	command: string,
	profile: string,
	question: string,
	ordered: string[],
	all: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "fictional_profile_reply",
		command_token: command,
		profile_token: profile,
		question_token: question,
		ordered_chunk_tokens: ordered,
		unused_chunk_tokens: all.filter((token) => !ordered.includes(token)),
		interaction_trace: trace,
		revisions: revisionCount(trace),
		invalid_drop_count: 0,
		tap_alternative_used: true,
	};
}

export function sceneReplyResponse(
	command: string,
	scene: string,
	prompt: string,
	response: string,
): ConstructedResponse {
	return {
		kind: "conversation_scene_reply",
		command_token: command,
		scene_token: scene,
		prompt_token: prompt,
		response_token: response,
		ordered_chunk_tokens: [],
		ordered_statement_tokens: [],
		interaction_trace: [`select:${response}`],
		revisions: 0,
		invalid_action_count: 0,
		tap_alternative_used: true,
	};
}
