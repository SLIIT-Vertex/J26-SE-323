import { useCallback, useEffect, useRef, useState } from "react";
import type { AreaGameProps } from "../../areas/registry";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	PresentationManifest,
	SupportRoundActivity,
	SupportView,
} from "../api/generated";
import { ContractError } from "../api/runtime";
import { useMoveEvidence } from "./useMoveEvidence";

/**
 * The story of every remade game: the child starts on the hard mission (unsupported); a wrong
 * answer leads, through a story card, to training where the server picks each help round; then
 * a fresh mission with no help. Correct answers end the episode; a new mission opens a new one.
 */
export type EpisodePhase =
	| "story"
	| "mission"
	| "victory"
	| "to-training"
	| "training"
	| "return"
	| "withdrawing"
	| "rest";

export type MissionOutcome = "playing" | "correct" | "wrong";

type Withdrawal = {
	episodeId: string;
	supportRevisionId: string;
	manifestRevisionId: string;
};

const OUTCOME_PAUSE_MS = 1600;

export function useHardFirstEpisode({
	api,
	learnerId,
	condition,
	onFailure,
	areaId,
	skillId,
	onMissionResult,
	onNextHelpRound,
	summaryFields,
}: Pick<AreaGameProps, "api" | "learnerId" | "condition" | "onFailure"> & {
	areaId: string;
	/** The hard mission's skill (the default for `startMission`). */
	skillId: string;
	/** Right after the server scores a mission answer (for sounds and animation). */
	onMissionResult?(correct: boolean): void;
	/** When the server opens another help round (`previousCorrect` is the child's last try). */
	onNextHelpRound?(previousCorrect: boolean | null): void;
	/**
	 * The interaction-summary fields this area's server flow accepts. Each flow rejects any other
	 * field (it could carry personal data), so a game sends only these. Default: all of them.
	 */
	summaryFields?: readonly string[];
}) {
	const [phase, setPhase] = useState<EpisodePhase>("story");
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [outcome, setOutcome] = useState<MissionOutcome>("playing");
	const [busy, setBusy] = useState(false);
	const [withdrawal, setWithdrawal] = useState<Withdrawal | null>(null);
	const inFlight = useRef(false);
	const pause = useRef<ReturnType<typeof setTimeout>>(undefined);
	const callbacks = useRef({ onMissionResult, onNextHelpRound });
	callbacks.current = { onMissionResult, onNextHelpRound };
	const evidence = useMoveEvidence();
	const fields = useRef(summaryFields);
	fields.current = summaryFields;
	/** The child's moves, limited to what this area's flow accepts. */
	const summary = useCallback(() => {
		const full = evidence.summary();
		const keep = fields.current;
		if (!keep) return full;
		return {
			...full,
			interaction_summary: Object.fromEntries(
				Object.entries(full.interaction_summary).filter(([key]) =>
					keep.includes(key),
				),
			),
		};
	}, [evidence]);

	useEffect(() => () => clearTimeout(pause.current), []);

	const run = useCallback(
		async <T>(operation: () => Promise<T>): Promise<T | undefined> => {
			if (inFlight.current) return undefined;
			inFlight.current = true;
			setBusy(true);
			try {
				return await operation();
			} catch (error) {
				onFailure(error);
				return undefined;
			} finally {
				inFlight.current = false;
				setBusy(false);
			}
		},
		[onFailure],
	);

	const showQuestion = useCallback(
		(next: PresentationManifest | null) => {
			if (!next) {
				onFailure(new ContractError("MISSING_MANIFEST"));
				return;
			}
			setManifest(next);
			setOutcome("playing");
			evidence.reset();
			setPhase("mission");
		},
		[evidence, onFailure],
	);

	/**
	 * Open a new episode. A game that varies its mission passes the skills to try in order: when
	 * the learner has already had every fresh item of one, the next skill is tried instead.
	 */
	const startMission = async (
		missionSkills: string | readonly string[] = skillId,
	) => {
		const skills = typeof missionSkills === "string" ? [missionSkills] : missionSkills;
		const opened = await run(async () => {
			for (const [index, missionSkillId] of skills.entries()) {
				try {
					return await api.open(
						{
							learner_id: learnerId,
							session_id: crypto.randomUUID(),
							grade: 5,
							medium: "si",
							condition,
							environment: "development",
							allow_draft: true,
							area_id: areaId,
							atomic_skill_id: missionSkillId,
						},
						crypto.randomUUID(),
					);
				} catch (error) {
					const usedUp =
						(error as { code?: unknown } | null)?.code ===
						"PROBE_ALREADY_RESERVED_OR_EXPOSED";
					if (!usedUp || index === skills.length - 1) throw error;
				}
			}
			throw new ContractError("MISSING_MANIFEST");
		});
		if (!opened) return;
		setEpisodeId(opened.episode_id);
		setSupport(null);
		showQuestion(opened.manifest);
	};

	const submitMission = async (response: ConstructedResponse) => {
		if (!episodeId || !manifest) return;
		const isAfter = manifest.measurement_role === "unsupported_after";
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			...summary(),
		};
		const next = await run(() =>
			isAfter
				? api.answerAfter(episodeId, body, crypto.randomUUID())
				: api.answerBefore(episodeId, body, crypto.randomUUID()),
		);
		if (!next) return;
		const score = next.server_score;
		if (
			!score ||
			score.presentation_id !== manifest.presentation_id ||
			score.item_revision_id !== manifest.revision_id
		) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
			return;
		}
		const correct = score.correct === true;
		setOutcome(correct ? "correct" : "wrong");
		callbacks.current.onMissionResult?.(correct);
		const help = next.status === "support_active" ? next.support : null;
		if (help) setSupport(help);
		clearTimeout(pause.current);
		pause.current = setTimeout(
			() => setPhase(correct ? "victory" : help ? "to-training" : "rest"),
			OUTCOME_PAUSE_MS,
		);
	};

	const advanceTraining = (next: ChildEpisodeResponse) => {
		const round = next.support_round;
		if (round?.withdrawal_allowed) {
			setWithdrawal({
				episodeId: next.episode_id,
				supportRevisionId: round.support_revision_id,
				manifestRevisionId: round.manifest_revision_id,
			});
			setSupport(null);
			setPhase("return");
			return;
		}
		if (next.support) {
			callbacks.current.onNextHelpRound?.(
				round?.previous_attempt_correct ?? null,
			);
			setSupport(next.support);
			evidence.reset();
		}
	};

	const answerTraining = async (
		response: ConstructedResponse,
		activity: SupportRoundActivity,
	) => {
		const submit = api.answerSupported;
		if (!submit || !episodeId) return;
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
					...summary(),
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceTraining(next);
	};

	const finishDemonstration = async () => {
		if (!episodeId || !support) return;
		const game = support.game_manifest;
		if (game.schema_version !== "support-round-v1") return;
		const next = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: 1000,
					steps_viewed: 1,
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
		if (next) advanceTraining(next);
	};

	// The training screen is gone before this runs, so the acknowledgement below is true.
	useEffect(() => {
		if (phase !== "withdrawing" || !withdrawal) return;
		let cancelled = false;
		void (async () => {
			const removed = await run(() =>
				api.withdrawSupport(
					withdrawal.episodeId,
					{
						request_id: crypto.randomUUID(),
						support_revision_id: withdrawal.supportRevisionId,
						manifest_revision_id: withdrawal.manifestRevisionId,
						all_support_removed: true,
						answer_revealing_state_cleared: true,
						input_handlers_cleared: true,
					},
					crypto.randomUUID(),
				),
			);
			if (!removed || cancelled) return;
			const after = await run(() =>
				api.presentAfter(withdrawal.episodeId, crypto.randomUUID()),
			);
			if (!after || cancelled) return;
			setWithdrawal(null);
			showQuestion(after.manifest);
		})();
		return () => {
			cancelled = true;
		};
	}, [api, phase, run, showQuestion, withdrawal]);

	return {
		phase,
		episodeId,
		manifest,
		support,
		outcome,
		busy,
		evidence,
		/** Open a new episode on the hard mission (or on the first of the given skills that opens). */
		startMission,
		submitMission,
		answerTraining,
		finishDemonstration,
		/** From the "go and train" card into the first help round. */
		goTraining: () => {
			evidence.reset();
			setPhase("training");
		},
		/** From the "ready" card: remove the help and fetch the fresh mission. */
		flyBack: () => setPhase("withdrawing"),
	};
}
