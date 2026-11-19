import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AreaGameProps } from "../../registry";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	PresentationManifest,
	SupportRoundActivity,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import { LandscapeGameStage } from "../../../mobile-learning-flow/landscape/LandscapeGameStage";
import { type MissionOutcome, SkyCityMission } from "./SkyCityMission";
import { artUrl, type SkyArtKey } from "./skyArt";
import { skySounds } from "./skySounds";
import { CITY_SKILL_ID, readAddends, SKY_AREA_ID } from "./skyRules";
import { TrainingGround } from "./TrainingGround";
import { useMoveEvidence } from "./useMoveEvidence";
import "./sky-adventure.css";

type Phase =
	| "story"
	| "mission"
	| "victory"
	| "to-training"
	| "training"
	| "return"
	| "withdrawing"
	| "rest";

type Withdrawal = {
	episodeId: string;
	supportRevisionId: string;
	manifestRevisionId: string;
};

const OUTCOME_PAUSE_MS = 1600;

/**
 * Nimo's Sky Adventure (Addition). The child starts on the city mission; a closed warehouse door
 * sends Nimo to training, where the server chooses each help round; then Nimo returns to the city
 * for a fresh mission with no help.
 */
export function NimoSkyAdventure({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: AreaGameProps) {
	const [phase, setPhase] = useState<Phase>("story");
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [outcome, setOutcome] = useState<MissionOutcome>("playing");
	const [busy, setBusy] = useState(false);
	const [withdrawal, setWithdrawal] = useState<Withdrawal | null>(null);
	const inFlight = useRef(false);
	const pause = useRef<ReturnType<typeof setTimeout>>(undefined);
	const evidence = useMoveEvidence();
	const addends = useMemo(
		() => readAddends(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => () => clearTimeout(pause.current), []);
	useEffect(() => skySounds.preload(), []);

	// Each story moment has its own little tune.
	useEffect(() => {
		if (phase === "to-training")
			skySounds.play("jingle-train", { steady: true });
		if (phase === "training") skySounds.play("whoosh");
		if (phase === "return") skySounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") skySounds.play("fly");
		if (phase === "victory") skySounds.play("jingle-victory", { steady: true });
		if (phase === "rest") skySounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const run = useCallback(
		async <T,>(operation: () => Promise<T>): Promise<T | undefined> => {
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

	const startMission = async () => {
		const opened = await run(() =>
			api.open(
				{
					learner_id: learnerId,
					session_id: crypto.randomUUID(),
					grade: 5,
					medium: "si",
					condition,
					environment: "development",
					allow_draft: true,
					area_id: SKY_AREA_ID,
					atomic_skill_id: CITY_SKILL_ID,
				},
				crypto.randomUUID(),
			),
		);
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
			...evidence.summary(),
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
		if (correct) {
			skySounds.play("gate-open");
			skySounds.play("jingle-open", { delay: 0.35, steady: true });
			skySounds.play("sparkle", { delay: 0.8, volume: 0.6 });
		} else {
			skySounds.play("gate-locked");
		}
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
			skySounds.play(
				round?.previous_attempt_correct === false ? "hmm" : "sparkle",
				{
					volume: 0.7,
				},
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
					...evidence.summary(),
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

	return (
		<LandscapeGameStage label="නිමෝගේ අහස් සවාරිය" onBack={onBack}>
			<section
				className="sky-adventure"
				data-sky-phase={phase}
				data-episode-id={episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<SkyCityMission
						key={manifest.revision_id}
						addends={addends}
						returning={manifest.measurement_role === "unsupported_after"}
						outcome={outcome}
						busy={busy}
						reducedMotion={reducedMotion}
						evidence={evidence}
						onSubmit={(response) => void submitMission(response)}
					/>
				)}
				{phase === "training" && support && (
					<TrainingGround
						key={support.revision_id}
						support={support}
						busy={busy}
						reducedMotion={reducedMotion}
						evidence={evidence}
						onAnswer={(response, activity) =>
							void answerTraining(response, activity)
						}
						onViewComplete={() => void finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<StoryCard
						title="අහස් නගරය බේරාගමු"
						nimo="nimoIdle"
						lines={[
							"අහස් නගරයේ උත්සවයට ශක්තිය මදි!",
							"ගුවන් නැව් බඩු පෙට්ටි ගෙනෙනවා. නිමෝට උදව් කරමු!",
						]}
						action="යමු!"
						busy={busy}
						onAction={() => void startMission()}
					/>
				)}
				{phase === "to-training" && (
					<StoryCard
						title="නිමෝගේ පුහුණුව"
						nimo="nimoThink"
						lines={["දොර අරින්න නිමෝට තව ශක්තිය ඕනෑ.", "පුහුණුවට ගිහින් ශක්තිය පුරවගමු!"]}
						action="පුහුණුවට යමු"
						onAction={() => {
							evidence.reset();
							setPhase("training");
						}}
					/>
				)}
				{phase === "return" && (
					<StoryCard
						title="ශක්තිය පිරිලා!"
						nimo="nimoPlane"
						lines={["නිමෝ දැන් ශක්තියෙන් පිරිලා.", "නගරයට ආපසු ගිහින් ගබඩාව අරිමු!"]}
						action="නගරයට යමු"
						onAction={() => setPhase("withdrawing")}
					/>
				)}
				{phase === "withdrawing" && (
					<StoryCard
						title="නගරයට පියාසර කරනවා…"
						nimo="nimoPlane"
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<StoryCard
						title="නගරය බේරුණා!"
						nimo="nimoCheer"
						lines={["ගබඩාව ඇරුණා. උත්සවයට ශක්තිය ලැබුණා!"]}
						action="ඊළඟ ගුවන් නැව් ටික"
						busy={busy}
						onAction={() => void startMission()}
					/>
				)}
				{phase === "rest" && (
					<StoryCard
						title="හොඳ උත්සාහයක්!"
						nimo="nimoIdle"
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් නගරයට උදව් කරමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onAction={() => void startMission()}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

function StoryCard({
	title,
	nimo,
	lines,
	action,
	busy = false,
	onAction,
}: {
	title: string;
	nimo: SkyArtKey;
	lines: string[];
	action?: string;
	busy?: boolean;
	onAction?(): void;
}) {
	return (
		<div className="sky-story">
			<img className="sky-story-nimo" src={artUrl(nimo)} alt="" />
			<div className="sky-story-card" role="dialog" aria-label={title}>
				<h2>{title}</h2>
				{lines.map((line) => (
					<p key={line}>{line}</p>
				))}
				{action && onAction && (
					<button
						type="button"
						className="sky-action"
						disabled={busy}
						onClick={() => {
							skySounds.play("tap");
							onAction();
						}}
					>
						{action}
					</button>
				)}
				{!action && busy && <p role="status">…</p>}
			</div>
		</div>
	);
}
