import { describe, expect, it } from "vitest";
import {
	pairLinksResponse,
	profileReplyResponse,
	sceneReplyResponse,
	turnSequenceResponse,
} from "../conversationStreetLogic";

describe("Conversation Street constructed responses", () => {
	it("records semantic adjacency without free text", () => {
		const response = pairLinksResponse(
			"cmd",
			[{ sequence: 1, question: "q1", response: "r1" }],
			["q1", "q2"],
			["select:q1", "link:r1"],
		);
		expect(response.kind).toBe("conversation_pair_links");
		if (response.kind !== "conversation_pair_links") return;
		expect(response.unlinked_question_tokens).toEqual(["q2"]);
		expect(JSON.stringify(response)).not.toContain("learner_name");
	});

	it("builds the three controlled non-pair response modes", () => {
		expect(
			turnSequenceResponse(
				"cmd",
				"d",
				[{ turn: "t", speaker: "s" }],
				["t"],
				["slot:t"],
			).kind,
		).toBe("conversation_turn_sequence");
		expect(
			profileReplyResponse("cmd", "p", "q", ["c"], ["c"], ["slot:c"]).kind,
		).toBe("fictional_profile_reply");
		expect(sceneReplyResponse("cmd", "s", "q", "r").kind).toBe(
			"conversation_scene_reply",
		);
	});
});
