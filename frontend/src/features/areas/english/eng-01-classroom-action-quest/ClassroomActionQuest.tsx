// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
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
	ClassroomActionWorkedExample,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../../../mobile-learning-flow/useSupportRound";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import {
	type BodyActionId,
	bodyStateResponse,
	navigationResponse,
} from "./classroomActionLogic";
import {
	ACTION_ASSETS,
	ACTION_LABELS,
	CLASSROOM_ASSET_ROOT,
	CLASSROOM_SKILLS,
} from "./manifest";
import "../../../mobile-learning-flow/english-game-shared.css";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function ClassroomActionQuest({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: {
	api: GameApi;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("games");
	const [skillId, setSkillId] = useState<string | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
	const [feedback, setFeedback] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [supportStage, setSupportStage] = useState(0);
	const [completed, setCompleted] = useState<string[]>([]);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [moves, setMoves] = useState(0);
	const [pending, setPending] = useState<{
		episode: string;
		support: string;
		manifest: string;
	} | null>(null);
	const lock = useRef(false);
	const index = Math.max(
		0,
		CLASSROOM_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = CLASSROOM_SKILLS[index];

	const run = useCallback(
		async <T,>(job: () => Promise<T>) => {
			setBusy(true);
			try {
				return await job();
			} catch (error) {
				onFailure(error);
				return undefined;
			} finally {
				setBusy(false);
			}
		},
		[onFailure],
	);
	const reset = useCallback(() => {
		setResponse(null);
		setMoves(0);
		setStartedAt(Date.now());
	}, []);

	useEffect(() => {
		if (step !== "withdrawing" || !pending) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() =>
				api.withdrawSupport(
					pending.episode,
					{
						request_id: crypto.randomUUID(),
						support_revision_id: pending.support,
						manifest_revision_id: pending.manifest,
						all_support_removed: true,
						answer_revealing_state_cleared: true,
						input_handlers_cleared: true,
					},
					crypto.randomUUID(),
				),
			);
			if (!withdrawn || cancelled) return;
			const next = await run(() =>
				api.presentAfter(pending.episode, crypto.randomUUID()),
			);
			if (!next || cancelled) return;
			setManifest(next.manifest);
			setSupport(null);
			setPending(null);
			reset();
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pending, reset, run, step]);
	const round = useSupportRound({
		api,
		episodeId,
		run,
		onSupport: (next) => {
			setSupport(next);
			reset();
		},
		onWithdraw: (withdrawal) => {
			setPending({
				episode: withdrawal.episodeId,
				support: withdrawal.supportRevisionId,
				manifest: withdrawal.manifestRevisionId,
			});
			setSupport(null);
			setResponse(null);
			setStep("withdrawing");
		},
	});

	const openSkill = async (id: string) => {
		if (lock.current) return;
		lock.current = true;
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
					area_id: "G5-AREA-ENG-01",
					atomic_skill_id: id,
				},
				crypto.randomUUID(),
			),
		);
		lock.current = false;
		if (!opened) return;
		setSkillId(id);
		setEpisodeId(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setCorrect(false);
		reset();
		setStep("question");
	};

	const record = (value: ConstructedResponse) => {
		setResponse(value);
		setMoves((current) => current + 1);
	};

	const confirm = async () => {
		if (!episodeId || !manifest || !response || lock.current) return;
		lock.current = true;
		const elapsed = reducedMotion ? 0 : Date.now() - startedAt;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			response_time_ms: reducedMotion ? null : elapsed,
			interaction_summary: {
				move_count: moves,
				correction_count: Math.max(0, moves - 1),
				first_action_ms: 0,
				active_time_ms: elapsed,
				attempt_count: 1,
				invalid_drop_count:
					response.kind === "classroom_navigation" ? response.invalid_drops : 0,
				tap_alternative_used: true,
			},
		};
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episodeId, body, crypto.randomUUID())
				: api.answerBefore(episodeId, body, crypto.randomUUID()),
		);
		lock.current = false;
		if (!next) return;
		if (
			!next.server_score ||
			next.server_score.presentation_id !== manifest.presentation_id ||
			next.server_score.item_revision_id !== manifest.revision_id
		)
			return onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
		setCorrect(next.server_score.correct === true);
		setFeedback(next.server_score.feedback_column ?? null);
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportStage(0);
			setStep("support");
		} else setStep("feedback");
	};

	const finishSupport = async () => {
		if (
			!episodeId ||
			!support ||
			support.game_manifest.schema_version !== "classroom-action-support-v1"
		)
			return;
		const game = support.game_manifest;
		if (supportStage < game.required_actions) return;
		const done = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Date.now() - startedAt,
					steps_viewed: Math.max(1, supportStage),
					manifest_revision_id: game.revision_id,
					interaction_summary: {
						completed: true,
						renderer_id: game.renderer_id,
						parallel_example_id: game.parallel_example_id,
						support_actions: supportStage,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (!done) return;
		setPending({
			episode: episodeId,
			support: support.revision_id,
			manifest: game.revision_id,
		});
		setSupport(null);
		setResponse(null);
		setStep("withdrawing");
	};

	const advance = () => {
		if (!skillId || !correct)
			return skillId ? void openSkill(skillId) : undefined;
		const done = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(done);
		if (index < CLASSROOM_SKILLS.length - 1)
			void openSkill(CLASSROOM_SKILLS[index + 1].id);
		else setStep(done.length === CLASSROOM_SKILLS.length ? "result" : "games");
	};

	return (
		<main
			className="classroom-action-quest"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Our Good Behaviour</h1>
				</div>
			</header>
			{step === "games" ? (
				<section
					className="caq-game-list"
					aria-label="Our Good Behaviour games"
				>
					{CLASSROOM_SKILLS.map((skill, skillIndex) => (
						<button
							className="caq-game-card"
							key={skill.id}
							onClick={() => void openSkill(skill.id)}
						>
							<img src={`${CLASSROOM_ASSET_ROOT}/${skill.asset}`} alt="" />
							<span>
								<strong>{skill.name}</strong>
								<small>{skill.description}</small>
								<em>{skillIndex + 1}/3 · Easy to challenging</em>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
							activityCount={3}
							currentActivity={index + 1}
							completedActivities={completed.length}
						/>
					)}
					<p className="caq-position">
						Activity {index + 1}/3 · {active.name}
					</p>
					{step === "question" &&
						manifest?.game?.schema_version === "classroom-action-item-v1" && (
							<>
								<div className="caq-command" aria-live="polite">
									<span>Read and act</span>
									<strong>{String(manifest.game.command_text_en)}</strong>
								</div>
								<ClassroomActivity
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my action
								</button>
							</>
						)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null}
							checkLabel="Check my action"
							checkClassName="caq-primary"
							onCheck={() => {
								if (response)
									void round.answer(
										support,
										response,
										Date.now() - startedAt,
										moves,
									);
							}}
							onViewComplete={() =>
								void round.viewComplete(support, Date.now() - startedAt)
							}
							renderActivity={(activity) => (
								<ClassroomActivity
									key={activity.revision_id}
									game={activity.game as Record<string, unknown>}
									onResponse={record}
								/>
							)}
						/>
					)}
					{step === "support" && support && !isSupportRound(support) && (
						<ClassroomSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now try a new one on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>{correct ? "Great action!" : friendlyFeedback(feedback)}</h2>
							<button className="caq-primary" onClick={advance}>
								{correct
									? index === 2
										? "Finish quest"
										: "Next activity"
									: "Try another one"}
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={3}
							gameCount={3}
							onContinue={() => setStep("games")}
						/>
					)}
				</section>
			)}
		</main>
	);
}

export function ClassroomActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	return game.response_kind === "body_state" ? (
		<ActionMirror game={game} onResponse={onResponse} />
	) : (
		<ClassroomDash game={game} onResponse={onResponse} />
	);
}

function ActionMirror({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const [selected, setSelected] = useState<BodyActionId | null>(null);
	const [trace, setTrace] = useState<string[]>([]);
	const allowed = Array.isArray(game.allowed_interaction_ids)
		? game.allowed_interaction_ids.map(String)
		: [];
	const choose = (action: BodyActionId) => {
		const nextTrace = [...trace, `pose:${action}`];
		setSelected(action);
		setTrace(nextTrace);
		onResponse(
			bodyStateResponse(
				String(game.command_token),
				action,
				nextTrace,
				Math.max(0, nextTrace.length - 1),
			),
		);
	};
	return (
		<section
			className="action-mirror"
			aria-label="Choose and create the matching body action"
		>
			<div className="caq-stage">
				<img
					src={`${CLASSROOM_ASSET_ROOT}/${selected ? ACTION_ASSETS[selected] : "student-standing-neutral.png"}`}
					alt={selected ? ACTION_LABELS[selected].en : "Student ready to act"}
				/>
			</div>
			<div className="pose-controls">
				{allowed.map((id) => (
					<button
						key={id}
						className={selected === id ? "selected" : ""}
						aria-pressed={selected === id}
						onClick={() => choose(id as BodyActionId)}
					>
						<img src={`${CLASSROOM_ASSET_ROOT}/${ACTION_ASSETS[id]}`} alt="" />
						<span>{ACTION_LABELS[id]?.en}</span>
					</button>
				))}
			</div>
		</section>
	);
}

function ClassroomDash({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const start = String(game.character_start_location);
	// The simpler version offers fewer places; the scene shows only the places the server allows.
	const allowed = new Set(
		Array.isArray(game.allowed_destination_ids)
			? game.allowed_destination_ids.map(String)
			: ["wall-zone", "blackboard-zone", "start-a"],
	);
	const [location, setLocation] = useState(start);
	const [trace, setTrace] = useState<string[]>([]);
	const [revisions, setRevisions] = useState(0);
	const move = (destination: string) => {
		const nextTrace = [...trace, `move:${destination}`];
		const nextRevisions = trace.length ? revisions + 1 : revisions;
		setLocation(destination);
		setTrace(nextTrace);
		setRevisions(nextRevisions);
		onResponse(
			navigationResponse(
				String(game.command_token),
				String(game.origin_id),
				destination,
				nextTrace,
				nextRevisions,
				0,
			),
		);
	};
	return (
		<section
			className="classroom-dash"
			style={{
				backgroundImage: `url(${CLASSROOM_ASSET_ROOT}/classroom-playfield.png)`,
			}}
			aria-label="Move the student around the classroom"
		>
			{allowed.has("wall-zone") && (
				<button
					className="destination wall"
					aria-label="Move to the wall"
					onClick={() => move("wall-zone")}
				>
					<span>Wall</span>
				</button>
			)}
			{allowed.has("blackboard-zone") && (
				<button
					className="destination blackboard"
					aria-label="Move to the blackboard"
					onClick={() => move("blackboard-zone")}
				>
					<span>Blackboard</span>
				</button>
			)}
			{allowed.has("start-a") && (
				<button
					className="destination origin"
					aria-label="Return to the starting place"
					onClick={() => move("start-a")}
				>
					<img src={`${CLASSROOM_ASSET_ROOT}/start-position-mat.png`} alt="" />
					<span>Start</span>
				</button>
			)}
			<img
				className={`runner at-${location}`}
				src={`${CLASSROOM_ASSET_ROOT}/${location === "start-a" ? "student-standing-neutral.png" : "student-running.png"}`}
				alt={`Student at ${location.replace("-zone", "")}`}
			/>
		</section>
	);
}

function ClassroomSupport({
	support,
	stage,
	onNext,
	onComplete,
}: {
	support: SupportView;
	stage: number;
	onNext(): void;
	onComplete(): void;
}) {
	if (support.game_manifest.schema_version !== "classroom-action-support-v1")
		return null;
	const game = support.game_manifest;
	const example = game.worked_example;
	return (
		<section className="caq-support" data-support-type={support.scaffold_type}>
			<p>Help type: {support.title_si}</p>
			<h2>Let's try another way</h2>
			<ClassroomWorkedExample
				example={example}
				reveal={stage > 0 || support.scaffold_type === "visual_guidance"}
			/>
			<ol>
				{example.steps_si.map((text, index) => (
					<li className={index < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="caq-primary"
				onClick={stage < game.required_actions ? onNext : onComplete}
			>
				{stage < game.required_actions
					? "Next help step"
					: "Now I will try alone"}
			</button>
		</section>
	);
}

function ClassroomWorkedExample({
	example,
	reveal,
}: {
	example: ClassroomActionWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	if (!response) return null;
	if (response.kind === "body_state")
		return (
			<div className="caq-worked">
				<strong>{String(example.game.command_text_en)}</strong>
				<img
					src={`${CLASSROOM_ASSET_ROOT}/${reveal ? ACTION_ASSETS[response.semantic_action_id] : "student-standing-neutral.png"}`}
					alt={reveal ? "Demonstrated body action" : "Student ready"}
				/>
			</div>
		);
	if (response.kind !== "classroom_navigation") return null;
	if (response.kind !== "classroom_navigation") return null;
	const target = reveal
		? response.final_location_id
		: String(example.game.character_start_location);
	return (
		<div className="caq-worked route">
			<strong>{String(example.game.command_text_en)}</strong>
			<img
				src={`${CLASSROOM_ASSET_ROOT}/${target === "start-a" ? "student-standing-neutral.png" : "student-running.png"}`}
				alt="Demonstrated classroom movement"
			/>
			<span>{reveal ? target.replace("-zone", "") : "?"}</span>
		</div>
	);
}

function friendlyFeedback(code: string | null) {
	if (code?.includes("wall") || code?.includes("landmark"))
		return "Look carefully at the classroom place and try again.";
	if (code?.includes("return") || code?.includes("origin"))
		return "Remember where the journey began.";
	return "Look at the action word and try another movement.";
}
