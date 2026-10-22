import { describe, expect, it } from "vitest";
import { parseChildEpisodeResponse } from "../api/runtime";
import visualRound from "./fixtures/maths-visual-guidance-round.json";

describe("support round contract", () => {
	it("accepts a maths visual demonstration shown on the child's own board, with its lesson", () => {
		// A real backend payload: a view stage that shows an activity instead of a worked example.
		const parsed = parseChildEpisodeResponse(visualRound);
		const manifest = parsed.support?.game_manifest;
		if (manifest?.schema_version !== "support-round-v1")
			throw new Error("not a round");
		expect(manifest.stage_kind).toBe("view");
		expect(manifest.activity).not.toBeNull();
		expect(manifest.worked_example).toBeNull();
		expect(manifest.activity?.answer?.mode).toBe("filled");
		expect(manifest.lesson?.steps_si.length).toBeGreaterThan(0);
		expect(manifest.lesson?.answer_si).toBeTruthy();
		expect(manifest.lesson?.continue_label_si).toBe("ඊළඟ");
	});
});

import helpLoop from "./fixtures/maths-help-loop.json";

describe("the whole maths help loop", () => {
	it("parses every help type the server sends, wrong answer after wrong answer", () => {
		// Real payloads, from the first wrong answer to the order running out.
		const types = helpLoop.map((payload) => {
			const parsed = parseChildEpisodeResponse(payload);
			const manifest = parsed.support?.game_manifest;
			if (manifest?.schema_version === "support-round-v1") {
				// Every stage teaches: a lesson, or (guided reasoning) answered questions.
				expect(
					manifest.lesson !== null || (manifest.guidance ?? []).length > 0,
				).toBe(true);
			}
			return parsed.support?.scaffold_type ?? null;
		});
		expect(new Set(types)).toEqual(
			new Set([
				"visual_guidance",
				"step_by_step_guidance",
				"conceptual_reexplanation",
				"simpler_same_game",
				"prerequisite_repair",
				"worked_parallel_example",
				null,
			]),
		);
	});
});
