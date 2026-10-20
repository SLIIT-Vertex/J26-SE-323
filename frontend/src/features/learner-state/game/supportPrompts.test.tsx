import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";

import type { LearnerStateAction } from "../../mobile-learning-flow/api/generated";
import { LearnerSupportPrompt } from "./LearnerSupportPrompt";
import {
	learnerStatePromptsEnabled,
	NO_PROMPT_YET,
	nextSupportPrompt,
	type PromptMemory,
	QUIET_ANSWERS,
	QUIET_MS,
} from "./supportPrompts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("nextSupportPrompt", () => {
	it.each([
		["request_reengagement_support", "take-a-break"],
		["request_tutor_support", "keep-going"],
		["monitor", null],
		["collect_more_evidence", null],
		["none", null],
	] as [LearnerStateAction, string | null][])("%s shows %s", (action, prompt) => {
		expect(nextSupportPrompt(NO_PROMPT_YET, action, 0).prompt).toBe(prompt);
	});

	it("stays quiet for a few answers and a few minutes after a prompt", () => {
		let memory: PromptMemory = NO_PROMPT_YET;
		const step = (action: LearnerStateAction, now: number) => {
			const next = nextSupportPrompt(memory, action, now);
			memory = next.memory;
			return next.prompt;
		};
		const later = QUIET_MS + 1;

		expect(step("request_tutor_support", 0)).toBe("keep-going");
		for (let answer = 1; answer <= QUIET_ANSWERS; answer += 1) {
			expect(step("request_reengagement_support", later)).toBeNull();
		}
		expect(step("request_reengagement_support", later)).toBe("take-a-break");
		// Enough answers, but too soon.
		for (let answer = 1; answer <= QUIET_ANSWERS; answer += 1) step("monitor", later + 1);
		expect(step("request_tutor_support", later + 2)).toBeNull();
	});

	it("can be switched off for silent mode", () => {
		expect(learnerStatePromptsEnabled(undefined)).toBe(true);
		expect(learnerStatePromptsEnabled("on")).toBe(true);
		expect(learnerStatePromptsEnabled("off")).toBe(false);
		expect(learnerStatePromptsEnabled(" OFF ")).toBe(false);
	});
});

describe("LearnerSupportPrompt", () => {
	it.each(["take-a-break", "keep-going"] as const)(
		"%s encourages without labelling the child and can be closed",
		(prompt) => {
			const host = document.createElement("div");
			const root = createRoot(host);
			const onDismiss = vi.fn();
			act(() => root.render(<LearnerSupportPrompt prompt={prompt} onDismiss={onDismiss} />));

			const text = host.textContent ?? "";
			// No words for "confused" or "attention": prompts describe the task, not the child.
			expect(text).not.toMatch(/ව්‍යාකූල|අවධාන|confus|attention/i);
			expect(host.querySelector("aside")?.getAttribute("aria-live")).toBe("polite");
			act(() => host.querySelector("button")?.click());
			expect(onDismiss).toHaveBeenCalledOnce();
			act(() => root.unmount());
		},
	);
});
