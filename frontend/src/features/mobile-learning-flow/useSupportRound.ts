import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	SupportRoundManifest,
	SupportView,
} from "./api/generated";
import type { GameApi } from "./GameApi";

export type SupportRoundView = SupportView & {
	game_manifest: SupportRoundManifest;
};

export type SupportRoundWithdrawal = {
	episodeId: string;
	supportRevisionId: string;
	manifestRevisionId: string;
};

/** True when the server sent a multi-help round rather than a single-help panel. */
export function isSupportRound(
	support: SupportView | null,
): support is SupportRoundView {
	return support?.game_manifest.schema_version === "support-round-v1";
}

/**
 * The phone side of one multi-help round. The server chooses every help type and its order; the
 * phone only posts the supported answer or the end of a demonstration, then shows whatever the
 * server returns: the next round's help, or the order to remove every trace of help.
 */
export function useSupportRound({
	api,
	episodeId,
	run,
	onSupport,
	onWithdraw,
}: {
	api: GameApi;
	episodeId: string | null;
	run<T>(job: () => Promise<T>): Promise<T | undefined>;
	onSupport(support: SupportView): void;
	onWithdraw(withdrawal: SupportRoundWithdrawal): void;
}) {
	const advance = (next: ChildEpisodeResponse) => {
		const round = next.support_round;
		if (round?.withdrawal_allowed) {
			onWithdraw({
				episodeId: next.episode_id,
				supportRevisionId: round.support_revision_id,
				manifestRevisionId: round.manifest_revision_id,
			});
		} else if (next.support) onSupport(next.support);
	};

	const answer = async (
		support: SupportRoundView,
		response: ConstructedResponse,
		elapsedMs: number,
		moves: number,
	) => {
		const activity = support.game_manifest.activity;
		const submit = api.answerSupported;
		if (!episodeId || !activity || !submit) return;
		const next = await run(() =>
			submit(
				episodeId,
				{
					constructed_response: {
						...response,
						presentation_id: activity.presentation_id,
						item_revision_id: activity.revision_id,
						interaction_version: "constructed-response-v1",
					},
					response_time_ms: Math.max(0, elapsedMs),
					interaction_summary: { move_count: moves },
				},
				crypto.randomUUID(),
			),
		);
		if (next) advance(next);
	};

	const viewComplete = async (support: SupportRoundView, elapsedMs: number) => {
		if (!episodeId) return;
		const game = support.game_manifest;
		const next = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Math.max(1, elapsedMs),
					steps_viewed: Math.max(1, game.worked_example?.steps_si.length ?? 1),
					manifest_revision_id: game.revision_id,
					interaction_summary: {
						completed: true,
						renderer_id: game.renderer_id,
						parallel_example_id: game.parallel_example_id,
						support_actions: 1,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (next) advance(next);
	};

	return { answer, viewComplete };
}
