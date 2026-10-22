// biome-ignore-all lint/a11y/useButtonType: mobile application controls, no forms.
import "@fontsource/noto-sans-sinhala/400.css";
import "@fontsource/noto-sans-sinhala/700.css";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { isSupportRound } from "../../../mobile-learning-flow/useSupportRound";
import "./sinhala-journey.css";
import { SupportTeardownRegistry } from "./teardown";

export type SinhalaActivity = {
	id: string;
	name: string;
	chapter: string;
	/** Locked by a content-review gate: shown, never opened. */
	blockedReason?: string;
};
export type DemonstrationView = {
	demonstration_id: string;
	goal_si: string;
	shown_si?: string | null;
	sign_display_si?: string;
	base_si?: string;
	/** A riddle demonstration: its lines first, its answer only at the last step. */
	riddle_lines_si?: string[];
	steps_si: string[];
	advance_label_si: string;
};
export type SinhalaGame = { opening_demonstration?: DemonstrationView };
export type BoardProps<Game> = {
	revision: string;
	game: Game;
	reducedMotion: boolean;
	busy: boolean;
	checkLabel: string;
	registry?: SupportTeardownRegistry;
	onSubmit(
		response: ConstructedResponse,
		interaction: Interaction,
		elapsed: number,
	): void;
};

const SUPPORT_NAMES: Record<string, string> = {
	visual_guidance: "බලන්න, හොයාගන්න",
	worked_parallel_example: "මම කරලා පෙන්නන්නම්",
	step_by_step_guidance: "අපි එකට කරමු",
};

type Step =
	| "activities"
	| "demo"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
export type Interaction = {
	moves: number;
	corrections: number;
	cancels: number;
	firstActionMs: number | null;
	mode: "drag" | "tap" | "keyboard" | "mixed" | null;
};
export const freshInteraction = (): Interaction => ({
	moves: 0,
	corrections: 0,
	cancels: 0,
	firstActionMs: null,
	mode: null,
});

/**
 * The shared Sinhala journey: activity list, unscored demonstration, independent item, the
 * server's help rounds, verified teardown, the fresh after item and truthful feedback. The
 * package supplies only its board.
 */
export function SinhalaJourney<Game extends SinhalaGame>({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
	areaId,
	title,
	activities,
	isGame,
	Board,
	rootClassName,
	renderReveal,
}: {
	api: GameApi;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
	areaId: string;
	title: string;
	activities: readonly SinhalaActivity[];
	isGame(value: unknown): value is Game;
	Board(props: BoardProps<Game>): ReactNode;
	rootClassName: string;
	/** A post-scoring illustration, drawn only when the server sends a reveal key. */
	renderReveal?(revealKey: string): ReactNode;
}) {
	const [step, setStep] = useState<Step>("activities");
	const [skill, setSkill] = useState<string | null>(null);
	const [episode, setEpisode] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [feedback, setFeedback] = useState<{
		correct: boolean;
		text: string;
		reveal?: string;
	} | null>(null);
	const [completed, setCompleted] = useState<string[]>([]);
	const [busy, setBusy] = useState(false);
	const [online, setOnline] = useState(() => navigator.onLine !== false);
	const [demoStep, setDemoStep] = useState(0);
	const lock = useRef(false);
	const teardown = useRef(new SupportTeardownRegistry());
	const supportRoot = useRef<HTMLDivElement>(null);
	const live = useRef<HTMLParagraphElement>(null);

	useEffect(() => {
		const update = () => setOnline(navigator.onLine !== false);
		window.addEventListener("online", update);
		window.addEventListener("offline", update);
		return () => {
			window.removeEventListener("online", update);
			window.removeEventListener("offline", update);
		};
	}, []);

	// Every mutation goes through here: one at a time, never offline.
	const run = useCallback(
		async <T,>(operation: () => Promise<T>) => {
			if (lock.current || navigator.onLine === false) return undefined;
			lock.current = true;
			setBusy(true);
			try {
				return await operation();
			} catch (error) {
				onFailure(error);
				return undefined;
			} finally {
				lock.current = false;
				setBusy(false);
			}
		},
		[onFailure],
	);

	const index = Math.max(
		0,
		activities.findIndex((row) => row.id === skill),
	);
	const game = isGame(manifest?.game) ? (manifest?.game as Game) : null;

	const openActivity = async (skillId: string) => {
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
					area_id: areaId,
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		if (!opened) return;
		setSkill(skillId);
		setEpisode(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setFeedback(null);
		setDemoStep(0);
		setStep("demo");
	};

	const submit = async (
		response: ConstructedResponse,
		interaction: Interaction,
		elapsed: number,
	) => {
		if (!episode || !manifest) return;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			// Timing is evidence only, never a penalty; reduced motion users may opt out.
			response_time_ms: reducedMotion ? null : elapsed,
			interaction_summary: summary(interaction, elapsed),
		};
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episode, body, crypto.randomUUID())
				: api.answerBefore(episode, body, crypto.randomUUID()),
		);
		if (!next) return;
		const score = next.server_score;
		if (
			!score ||
			score.presentation_id !== manifest.presentation_id ||
			score.item_revision_id !== manifest.revision_id
		)
			return onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
		setFeedback({
			correct: score.correct === true,
			text: score.feedback_si ?? "",
			reveal: score.reveal_key,
		});
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setStep("support");
		} else setStep("feedback");
	};

	const round = isSupportRound(support) ? support.game_manifest : null;

	const advanceSupport = (next: ChildEpisodeResponse) => {
		const round = next.support_round;
		if (next.server_score?.feedback_si)
			setFeedback({
				correct: next.server_score.correct === true,
				text: next.server_score.feedback_si,
				reveal: next.server_score.reveal_key,
			});
		if (round?.withdrawal_allowed) {
			void withdraw(round.support_revision_id, round.manifest_revision_id);
		} else if (next.support) setSupport(next.support);
	};

	const answerSupported = async (
		response: ConstructedResponse,
		interaction: Interaction,
		elapsed: number,
	) => {
		const activity = round?.activity;
		const send = api.answerSupported;
		if (!episode || !activity || !send) return;
		const next = await run(() =>
			send(
				episode,
				{
					constructed_response: {
						...response,
						presentation_id: activity.presentation_id,
						item_revision_id: activity.revision_id,
						interaction_version: "constructed-response-v1",
					},
					response_time_ms: Math.max(0, elapsed),
					interaction_summary: summary(interaction, elapsed),
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceSupport(next);
	};

	const finishWorked = async (presses: number, elapsed: number) => {
		if (!episode || !support) return;
		const manifestRevision = support.game_manifest.revision_id;
		const next = await run(() =>
			api.completeSupport(
				episode,
				{
					duration_ms: Math.max(1, elapsed),
					steps_viewed: presses,
					manifest_revision_id: manifestRevision,
					interaction_summary: { completed: true, next_presses: presses },
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceSupport(next);
	};

	// Withdrawal: tear everything down first, count what is left, then ask the server.
	const withdraw = async (
		supportRevision: string,
		manifestRevision: string,
	) => {
		setStep("withdrawing");
		setSupport(null);
		await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
		const receipt = teardown.current.teardown(
			supportRoot.current,
			live.current,
			{
				support: supportRevision,
				manifest: manifestRevision,
			},
		);
		if (!episode) return;
		const withdrawn = await run(() =>
			api.withdrawSupport(
				episode,
				{
					request_id: crypto.randomUUID(),
					support_revision_id: supportRevision,
					manifest_revision_id: manifestRevision,
					all_support_removed: true,
					answer_revealing_state_cleared: true,
					input_handlers_cleared: true,
					teardown_receipt: receipt,
				},
				crypto.randomUUID(),
			),
		);
		if (!withdrawn) return;
		const after = await run(() =>
			api.presentAfter(episode, crypto.randomUUID()),
		);
		if (!after?.manifest) return;
		setFeedback(null);
		setManifest(after.manifest);
		setStep("question");
	};

	const continueAfterFeedback = () => {
		if (!skill) return;
		if (
			manifest?.measurement_role !== "unsupported_after" &&
			!feedback?.correct
		)
			return;
		const next = completed.includes(skill) ? completed : [...completed, skill];
		setCompleted(next);
		setStep(next.length === activities.length ? "result" : "activities");
	};

	const supportActivity = round?.activity;
	const worked = round?.worked_example as
		| {
				revision_id: string;
				prompt_si: string;
				game: unknown;
				steps_si: string[];
				solution: Record<string, unknown>;
		  }
		| null
		| undefined;

	return (
		<main
			className={`sinhala-journey ${rootClassName}`}
			data-reduced-motion={reducedMotion || undefined}
			data-episode-id={episode ?? undefined}
			aria-busy={busy}
		>
			<header className="pj-header">
				<AdventureBackButton
					onClick={step === "activities" ? onBack : () => setStep("activities")}
				/>
				<div>
					<p>සිංහල</p>
					<h1>{title}</h1>
				</div>
			</header>
			{!online && (
				<p className="pj-offline" role="status">
					අන්තර්ජාලය නැවත ලැබෙන තුරු ක්‍රීඩාව නවතා ඇත. ඔයාගේ පිළිතුරු ආරක්ෂිතයි.
				</p>
			)}
			<p className="sr-only" aria-live="polite" ref={live} />
			{step === "activities" && (
				<section className="pj-activities" aria-label="ක්‍රියාකාරකම්">
					{activities.map((activity, position) => (
						<button
							key={activity.id}
							className="pj-activity-card"
							data-blocked={activity.blockedReason ? "true" : undefined}
							disabled={busy || !online || Boolean(activity.blockedReason)}
							onClick={() => void openActivity(activity.id)}
						>
							<span aria-hidden="true">
								{completed.includes(activity.id) ? "🎉" : "🌟"}
							</span>
							<strong>{activity.name}</strong>
							<small>
								{activity.chapter} · {position + 1}/{activities.length}
								{completed.includes(activity.id) ? " · සම්පූර්ණයි" : ""}
							</small>
							{activity.blockedReason && <em>{activity.blockedReason}</em>}
						</button>
					))}
				</section>
			)}
			{step !== "activities" && step !== "result" && (
				<AdventureProgress
					stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
					activityCount={activities.length}
					currentActivity={index + 1}
					completedActivities={completed.length}
				/>
			)}
			{step === "demo" && game?.opening_demonstration && (
				<Demonstration
					demo={game.opening_demonstration}
					step={demoStep}
					onNext={() => setDemoStep((value) => value + 1)}
					onDone={() => setStep("question")}
				/>
			)}
			{step === "question" && game && manifest && (
				<section className="pj-play">
					<h2>{manifest.prompt_si}</h2>
					<Board
						key={manifest.revision_id}
						revision={manifest.revision_id}
						game={game}
						reducedMotion={reducedMotion}
						busy={busy || !online}
						checkLabel="පරීක්ෂා කරන්න"
						onSubmit={submit}
					/>
				</section>
			)}
			{step === "support" && support && (
				<div className="pj-support" ref={supportRoot} data-support-node>
					<h2 data-support-node>
						<span aria-hidden="true">🌱 </span>
						{SUPPORT_NAMES[support.scaffold_type] ?? support.title_si}
					</h2>
					{round?.guidance && round.guidance.length > 0 && (
						<ol className="pj-guidance" data-support-node>
							{round.guidance.map((pair) => (
								<li key={pair.question_si}>{pair.question_si}</li>
							))}
						</ol>
					)}
					{feedback?.text && (
						<p className="pj-gentle" data-support-node>
							{feedback.text}
						</p>
					)}
					{feedback?.reveal && renderReveal && (
						<div data-support-node>{renderReveal(feedback.reveal)}</div>
					)}
					{worked && (
						<WorkedExample
							worked={worked}
							reducedMotion={reducedMotion}
							busy={busy}
							registry={teardown.current}
							onDone={(presses) => void finishWorked(presses, 0)}
						/>
					)}
					{supportActivity && isGame(supportActivity.game) && (
						<>
							<h3 data-support-node>{supportActivity.prompt_si}</h3>
							<Board
								key={supportActivity.revision_id}
								revision={supportActivity.revision_id}
								game={supportActivity.game as Game}
								reducedMotion={reducedMotion}
								busy={busy || !online}
								registry={teardown.current}
								checkLabel="පරීක්ෂා කරන්න"
								onSubmit={answerSupported}
							/>
						</>
					)}
					{(round?.cues_si ?? []).map((cue) => (
						<p key={cue} className="pj-cue" data-support-node>
							{cue}
						</p>
					))}
				</div>
			)}
			{step === "withdrawing" && (
				<p className="pj-status" role="status">
					උදව් ඉවත් කරනවා. දැන් අලුත් එකක් ඔයාම කරමු.
				</p>
			)}
			{step === "feedback" && (
				<section className="pj-feedback" role="status">
					<h2>
						<span aria-hidden="true">{feedback?.correct ? "🎉 " : "🌱 "}</span>
						{feedback?.correct ? "හරි! නියමයි" : "හොඳ උත්සාහයක්"}
					</h2>
					{feedback?.text && <p>{feedback.text}</p>}
					{feedback?.reveal && renderReveal?.(feedback.reveal)}
					<button
						className="primary-action"
						onClick={continueAfterFeedback}
						disabled={busy}
					>
						{manifest?.measurement_role === "unsupported_after" ||
						feedback?.correct
							? "ඉදිරියට"
							: "නැවත උත්සාහ කරමු"}
					</button>
				</section>
			)}
			{step === "result" && (
				<GameSuccessScreen
					gameNumber={activities.length}
					gameCount={activities.length}
					onContinue={() => setStep("activities")}
				/>
			)}
		</main>
	);
}

export function summary(interaction: Interaction, elapsed: number) {
	return {
		move_count: interaction.moves,
		correction_count: interaction.corrections,
		cancelled_drag_count: interaction.cancels,
		first_action_ms: interaction.firstActionMs ?? 0,
		active_time_ms: Math.max(0, elapsed),
		...(interaction.mode ? { input_mode: interaction.mode } : {}),
	};
}

function Demonstration({
	demo,
	step,
	onNext,
	onDone,
}: {
	demo: DemonstrationView;
	step: number;
	onNext(): void;
	onDone(): void;
}) {
	const last = step >= demo.steps_si.length - 1;
	return (
		<section className="pj-demo" aria-live="polite">
			<h2>
				{demo.goal_si.replace(/\s*🌟$/u, "")}
				<span aria-hidden="true"> 🌟</span>
			</h2>
			<div className="pj-demo-board">
				{demo.base_si || demo.sign_display_si ? (
					<>
						<span className="pj-glyph">
							{demo.base_si ?? demo.sign_display_si}
						</span>
						<span aria-hidden="true">→</span>
						<span className="pj-glyph">{last ? demo.shown_si : "?"}</span>
					</>
				) : demo.riddle_lines_si ? (
					<div className="pj-demo-riddle">
						{demo.riddle_lines_si.map((line) => (
							<p key={line}>{line}</p>
						))}
						<p className="pj-demo-answer">{last ? demo.shown_si : "?"}</p>
					</div>
				) : (
					<p className="pj-demo-text">{demo.shown_si}</p>
				)}
			</div>
			<p>{demo.steps_si[Math.min(step, demo.steps_si.length - 1)]}</p>
			<p className="pj-note">මෙය ලකුණු නොලැබෙන පෙන්වීමක්.</p>
			<button className="primary-action" onClick={last ? onDone : onNext}>
				{last ? "දැන් ඔයාම කරලා බලන්න! 💪" : demo.advance_label_si}
			</button>
		</section>
	);
}

function WorkedExample({
	worked,
	reducedMotion,
	busy,
	registry,
	onDone,
}: {
	worked: {
		revision_id: string;
		prompt_si: string;
		game: unknown;
		steps_si: string[];
		solution: Record<string, unknown>;
	};
	reducedMotion: boolean;
	busy: boolean;
	registry: SupportTeardownRegistry;
	onDone(presses: number): void;
}) {
	// The count is what the child actually pressed, not the authored step total.
	const [presses, setPresses] = useState(0);
	useEffect(() => registry.cache(worked.solution), [registry, worked.solution]);
	const shown = worked.steps_si.slice(0, presses + 1);
	const result =
		typeof worked.solution.result_text_si === "string"
			? worked.solution.result_text_si
			: null;
	const done = presses >= worked.steps_si.length;
	return (
		<section
			className="pj-worked"
			data-support-node
			data-reduced-motion={reducedMotion || undefined}
		>
			<h3>{worked.prompt_si}</h3>
			<ol>
				{shown.map((line) => (
					<li key={line}>{line}</li>
				))}
			</ol>
			{done && result && <p className="pj-glyph">{result}</p>}
			<button
				className="primary-action"
				disabled={busy}
				onClick={() =>
					done ? onDone(presses) : setPresses((value) => value + 1)
				}
			>
				{done ? "දැන් ඔයාම කරලා බලන්න! 💪" : "ඊළඟ"}
			</button>
		</section>
	);
}
