// biome-ignore-all lint/a11y/useButtonType: application controls, no forms.
import { useCallback, useEffect, useRef, useState } from "react";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../mobile-learning-flow/AdventureShared";
import type {
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import "../mobile-learning-flow/english-game-shared.css";
import "./classroom-language-live.css";
import {
	commandActionResponse,
	contextLinkResponse,
	functionSortResponse,
	questionSequenceResponse,
	type StudioLink,
} from "./classroomLanguageLogic";

const SKILLS = [
	{ id: "G5-ENG-CLASS-FUNCTION-01", name: "Phrase Portal Sort", icon: "🗂️" },
	{ id: "G5-ENG-CLASS-COMMAND-02", name: "Command Stage Director", icon: "🎬" },
	{
		id: "G5-ENG-CLASS-CONTEXT-03",
		name: "Situation Speech-Bubble Match",
		icon: "💬",
	},
	{ id: "G5-ENG-CLASS-QUESTION-04", name: "Question Tile Studio", icon: "❓" },
] as const;
type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type Row = Record<string, unknown>;

export function ClassroomLanguageLive({
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
	const [step, setStep] = useState<Step>("games"),
		[skill, setSkill] = useState<string | null>(null),
		[episode, setEpisode] = useState<string | null>(null),
		[manifest, setManifest] = useState<PresentationManifest | null>(null),
		[support, setSupport] = useState<SupportView | null>(null),
		[response, setResponse] = useState<ConstructedResponse | null>(null),
		[correct, setCorrect] = useState(false),
		[busy, setBusy] = useState(false),
		[supportStage, setSupportStage] = useState(0),
		[completed, setCompleted] = useState<string[]>([]),
		[startedAt, setStartedAt] = useState(Date.now()),
		[moves, setMoves] = useState(0),
		[pending, setPending] = useState<{
			episode: string;
			support: string;
			manifest: string;
		} | null>(null);
	const lock = useRef(false),
		index = Math.max(
			0,
			SKILLS.findIndex((entry) => entry.id === skill),
		);
	const run = useCallback(
		async <T,>(operation: () => Promise<T>) => {
			setBusy(true);
			try {
				return await operation();
			} catch (error) {
				onFailure(error);
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
		episodeId: episode,
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
	const openSkill = async (skillId: string) => {
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
					area_id: "G5-AREA-ENG-17",
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		lock.current = false;
		if (!opened) return;
		setSkill(skillId);
		setEpisode(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setCorrect(false);
		reset();
		setStep("question");
	};
	const submit = async () => {
		if (!episode || !manifest || !response || lock.current) return;
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
				invalid_drop_count: 0,
				tap_alternative_used: true,
			},
		};
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episode, body, crypto.randomUUID())
				: api.answerBefore(episode, body, crypto.randomUUID()),
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
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportStage(0);
			setStep("support");
		} else setStep("feedback");
	};
	const finishSupport = async () => {
		if (
			!episode ||
			!support ||
			support.game_manifest.schema_version !==
				"classroom-language-live-support-v1" ||
			supportStage < support.game_manifest.required_actions
		)
			return;
		const game = support.game_manifest;
		const done = await run(() =>
			api.completeSupport(
				episode,
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
			episode,
			support: support.revision_id,
			manifest: game.revision_id,
		});
		setSupport(null);
		setResponse(null);
		setStep("withdrawing");
	};
	const advance = () => {
		if (!skill || !correct) {
			if (skill) void openSkill(skill);
			return;
		}
		const next = completed.includes(skill) ? completed : [...completed, skill];
		setCompleted(next);
		if (index < SKILLS.length - 1) void openSkill(SKILLS[index + 1].id);
		else setStep(next.length === SKILLS.length ? "result" : "games");
	};
	const game =
		manifest?.game?.schema_version === "classroom-language-live-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main className="classroom-action-quest classroom-language-live">
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<p>Classroom Language</p>
					<h1>Language Live</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list">
					<div className="cll-stage" aria-hidden="true">
						<i />
						<i />
						<b>💬</b>
					</div>
					{SKILLS.map((entry) => (
						<button
							className="caq-game-card"
							key={entry.id}
							onClick={() => void openSkill(entry.id)}
						>
							<span>{entry.icon}</span>
							<span>
								<strong>{entry.name}</strong>
								<small>Read, connect, and move the character.</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(
								step,
								manifest?.measurement_role,
							)}
							activityCount={4}
							currentActivity={index + 1}
							completedActivities={completed.length}
						/>
					)}
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<strong>
									{manifest?.prompt_si
										.replaceAll("කල්පිත ", "")
										.replaceAll("කේත ", "")}
								</strong>
							</div>
							<StudioBoard
								key={manifest?.revision_id}
								game={game}
								onResponse={(next) => {
									setResponse(next);
									setMoves((value) => value + 1);
								}}
							/>
							<button
								className="caq-primary"
								disabled={busy || !response || incomplete(response)}
								onClick={submit}
							>
								Check my classroom response
							</button>
						</>
					)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null && !incomplete(response)}
							checkLabel="Check my classroom response"
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
								<StudioBoard
									key={activity.revision_id}
									game={activity.game as Record<string, unknown>}
									onResponse={(value) => {
										setResponse(value);
										setMoves((count) => count + 1);
									}}
								/>
							)}
						/>
					)}
					{step === "support" &&
						support?.game_manifest.schema_version ===
							"classroom-language-live-support-v1" && (
							<section className="caq-support">
								<h2>{support.title_si.replaceAll("කල්පිත ", "")}</h2>
								<p>
									{
										support.body_si[
											Math.min(supportStage, support.body_si.length - 1)
										]
									}
								</p>
								<button
									className="caq-primary"
									onClick={
										supportStage < support.game_manifest.required_actions
											? () => setSupportStage((value) => value + 1)
											: finishSupport
									}
								>
									{supportStage < support.game_manifest.required_actions
										? "Next language step"
										: "I’m ready to respond alone"}
								</button>
							</section>
						)}
					{step === "withdrawing" && (
						<p className="caq-status">
							All examples, scene states, speech bubbles, and tile hints are
							clearing.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Classroom response complete!"
									: "Read the classroom language and try again."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct ? "Continue" : "Try a fresh activity"}
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={4}
							gameCount={4}
							onContinue={() => setStep("games")}
						/>
					)}
				</section>
			)}
		</main>
	);
}

function incomplete(response: ConstructedResponse) {
	switch (response.kind) {
		case "classroom_function_sort":
			return response.unplaced_expression_tokens.length > 0;
		case "classroom_context_expression_links":
			return response.unlinked_situation_tokens.length > 0;
		case "classroom_command_action":
			return response.actions.length !== 1;
		case "classroom_question_sequence":
			return response.unused_chunk_tokens.length > 0;
		default:
			return true;
	}
}

function StudioBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const [selected, setSelected] = useState<string | null>(null),
		[links, setLinks] = useState<StudioLink[]>([]),
		[trace, setTrace] = useState<string[]>([]);
	if (game.response_kind === "classroom_command_action")
		return <CommandBoard game={game} onResponse={onResponse} />;
	if (game.response_kind === "classroom_question_sequence")
		return <QuestionBoard game={game} onResponse={onResponse} />;
	const context = game.response_kind === "classroom_context_expression_links";
	const sources = (context ? game.situations : game.expressions) as Row[],
		targets = (context ? game.expressions : game.heading_zones) as Row[];
	const sourceKey = context ? "situation_token" : "expression_token",
		targetKey = context ? "expression_token" : "heading_token";
	const place = (target: string) => {
		if (!selected) return;
		const remaining = links.filter(
				(link) => link.source !== selected && link.target !== target,
			),
			next = [
				...remaining,
				{ sequence: remaining.length + 1, source: selected, target },
			],
			nextTrace = [
				...trace,
				links.some((link) => link.source === selected)
					? `replace:${target}`
					: `place:${target}`,
			];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		onResponse(
			context
				? contextLinkResponse(
						String(game.command_token),
						next,
						sources.map((row) => String(row[sourceKey])),
						nextTrace,
					)
				: functionSortResponse(
						String(game.command_token),
						next,
						sources.map((row) => String(row[sourceKey])),
						nextTrace,
					),
		);
	};
	return (
		<section className="cll-board">
			{selected && <p className="cll-dock">Selected card ready</p>}
			<div className="cll-tray">
				{sources.map((row, index) => (
					<button
						data-opaque-token={String(row[sourceKey])}
						key={String(row[sourceKey])}
						aria-pressed={selected === row[sourceKey]}
						onClick={() => setSelected(String(row[sourceKey]))}
					>
						{context ? (
							<SituationCue
								variant={Number(row.renderer_variant)}
								index={index}
							/>
						) : (
							String(row.text_en)
						)}
					</button>
				))}
			</div>
			<div className="cll-portals">
				{targets.map((row) => (
					<button
						data-opaque-token={String(row[targetKey])}
						key={String(row[targetKey])}
						onClick={() => place(String(row[targetKey]))}
					>
						<strong>{String(row.text_en)}</strong>
						<small>
							{links.some((link) => link.target === row[targetKey])
								? "✓ placed"
								: "tap to place"}
						</small>
					</button>
				))}
			</div>
		</section>
	);
}

function CommandBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const controls = game.action_controls as Row[];
	const [selected, setSelected] = useState<number | null>(null);
	return (
		<section className="cll-command">
			<h2>{String(game.command_text)}</h2>
			<p>Move the character below.</p>
			<div
				className="cll-character"
				data-pose={selected ?? -1}
				role="img"
				aria-label="Classroom character"
			>
				<i />
				<b />
				<b />
			</div>
			<div className="cll-controls">
				{controls.map((control, index) => (
					<button
						data-opaque-token={String(control.action_token)}
						key={String(control.action_token)}
						onClick={() => {
							setSelected(Number(control.renderer_variant));
							onResponse(
								commandActionResponse(
									String(game.command_token),
									String(game.actor_token),
									String(control.action_token),
									String(control.state_token),
									[`act:${String(control.action_token)}`],
								),
							);
						}}
					>
						Scene action {index + 1}
					</button>
				))}
			</div>
		</section>
	);
}

function QuestionBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const chunks = game.chunks as Row[],
		all = chunks.map((row) => String(row.chunk_token));
	const [ordered, setOrdered] = useState<string[]>([]);
	const choose = (token: string) => {
		if (ordered.includes(token)) return;
		const next = [...ordered, token];
		setOrdered(next);
		onResponse(
			questionSequenceResponse(
				String(game.command_token),
				String(game.prompt_token),
				next,
				all,
				game.placeholder_token == null ? null : String(game.placeholder_token),
				next.map((value) => `slot:${value}`),
			),
		);
	};
	return (
		<section className="cll-question">
			<p className="cll-frame">
				Build the printed question · {Number(game.required_slot_count)} tiles
			</p>
			<div className="cll-slots">
				{Array.from(
					{ length: Number(game.required_slot_count) },
					(_, index) => (
						<span key={`slot-${all[index]}`}>
							{ordered[index]
								? String(
										chunks.find((row) => row.chunk_token === ordered[index])
											?.text_en,
									)
								: "…"}
						</span>
					),
				)}
			</div>
			<div className="cll-tiles">
				{chunks.map((row) => (
					<button
						key={String(row.chunk_token)}
						disabled={ordered.includes(String(row.chunk_token))}
						onClick={() => choose(String(row.chunk_token))}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
			<button
				className="cll-clear"
				onClick={() => {
					setOrdered([]);
					onResponse(
						questionSequenceResponse(
							String(game.command_token),
							String(game.prompt_token),
							[],
							all,
							game.placeholder_token == null
								? null
								: String(game.placeholder_token),
							["clear:all"],
						),
					);
				}}
			>
				Clear tiles
			</button>
		</section>
	);
}

function SituationCue({ variant, index }: { variant: number; index: number }) {
	return (
		<span
			className="cll-situation"
			data-v={variant}
			role="img"
			aria-label={`Classroom situation ${index + 1}`}
		>
			<i />
			<b />
		</span>
	);
}
