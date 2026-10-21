import type { LearningFlowClient } from "./api/learningFlowClient";

export type GameApi = Pick<
	LearningFlowClient,
	| "open"
	| "answerBefore"
	| "completeSupport"
	| "withdrawSupport"
	| "presentAfter"
	| "answerAfter"
> &
	Partial<Pick<LearningFlowClient, "answerSupported">>;
