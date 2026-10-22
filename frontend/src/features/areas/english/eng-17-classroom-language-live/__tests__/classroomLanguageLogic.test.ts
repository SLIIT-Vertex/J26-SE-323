import { describe, expect, it } from "vitest";
import {
	commandActionResponse,
	contextLinkResponse,
	functionSortResponse,
	questionSequenceResponse,
} from "../classroomLanguageLogic";

describe("Classroom Language Live responses", () => {
	it("constructs strict sort and context mappings", () => {
		const sort = functionSortResponse(
			"cmd",
			[{ sequence: 1, source: "e1", target: "h1" }],
			["e1"],
			["sort:h1"],
		);
		const context = contextLinkResponse(
			"cmd",
			[{ sequence: 1, source: "s1", target: "e1" }],
			["s1"],
			["link:e1"],
		);
		expect(sort.kind).toBe("classroom_function_sort");
		expect(context.kind).toBe("classroom_context_expression_links");
		if (
			sort.kind !== "classroom_function_sort" ||
			context.kind !== "classroom_context_expression_links"
		)
			throw new Error("wrong response kind");
		expect(sort.unplaced_expression_tokens).toEqual([]);
		expect(context.unlinked_situation_tokens).toEqual([]);
	});

	it("constructs safe code-scene and question-tile responses", () => {
		const action = commandActionResponse("cmd", "actor", "action", "state", [
			"act:action",
		]);
		const question = questionSequenceResponse(
			"cmd",
			"prompt",
			["c1", "c2"],
			["c1", "c2"],
			null,
			["slot:c1"],
		);
		expect(action.kind).toBe("classroom_command_action");
		expect(question.kind).toBe("classroom_question_sequence");
		if (question.kind !== "classroom_question_sequence")
			throw new Error("wrong response kind");
		expect(question.unused_chunk_tokens).toEqual([]);
	});
});
