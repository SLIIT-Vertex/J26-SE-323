// When the child app shows a gentle learner-state prompt after a scored answer.
//
// Prompts react only to the two support actions; "monitor", "collect_more_evidence" and "none"
// never show anything. A prompt is followed by a quiet period, so the child is not interrupted
// again and again. Set VITE_LEARNER_STATE_PROMPTS=off for silent mode (pilot study, see
// docs/learner-state/12_PILOT_STUDY_PLAN.md): decisions are still recorded, nothing is shown.

import type { LearnerStateAction } from "../../mobile-learning-flow/api/generated";

export type SupportPrompt = "take-a-break" | "keep-going";

/** Answers that must pass after a prompt before the next one may appear. */
export const QUIET_ANSWERS = 3;
/** Minimum time between two prompts. */
export const QUIET_MS = 2 * 60_000;

export type PromptMemory = { answersSincePrompt: number; lastPromptAt: number | null };

export const NO_PROMPT_YET: PromptMemory = {
	answersSincePrompt: Number.POSITIVE_INFINITY,
	lastPromptAt: null,
};

export function learnerStatePromptsEnabled(
	setting: string | undefined = import.meta.env.VITE_LEARNER_STATE_PROMPTS,
): boolean {
	return setting?.trim().toLowerCase() !== "off";
}

function promptFor(action: LearnerStateAction): SupportPrompt | null {
	// Re-engagement comes first in the learner-state priority, so it is a separate action.
	if (action === "request_reengagement_support") return "take-a-break";
	if (action === "request_tutor_support") return "keep-going";
	return null;
}

/** One scored answer: whether to show a prompt now, and the updated memory. */
export function nextSupportPrompt(
	memory: PromptMemory,
	action: LearnerStateAction,
	now: number,
): { prompt: SupportPrompt | null; memory: PromptMemory } {
	const answersSincePrompt = memory.answersSincePrompt + 1;
	const prompt = promptFor(action);
	const quiet =
		answersSincePrompt <= QUIET_ANSWERS ||
		(memory.lastPromptAt !== null && now - memory.lastPromptAt < QUIET_MS);
	if (prompt === null || quiet) {
		return { prompt: null, memory: { ...memory, answersSincePrompt } };
	}
	return { prompt, memory: { answersSincePrompt: 0, lastPromptAt: now } };
}
