// biome-ignore-all lint/a11y/useButtonType: mobile application controls, no forms.
import { useCallback, useEffect, useRef, useState } from "react";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	SuccessCelebration,
} from "../mobile-learning-flow/AdventureShared";
import type {
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../english-area-1/classroom-action-quest.css";
import "./conversation-street.css";
import {
	pairLinksResponse,
	profileReplyResponse,
	sceneReplyResponse,
	turnSequenceResponse,
	type ConversationLink,
} from "./conversationStreetLogic";

const SKILLS = [
	{ id: "G5-ENG-CONV-PAIR-01", name: "Conversation Matchmaker", icon: "🤝" },
	{ id: "G5-ENG-CONV-TURN-02", name: "Dialogue Director", icon: "🎭" },
	{
		id: "G5-ENG-CONV-FRAME-03",
		name: "Fictional Profile Reply Lab",
		icon: "🪪",
	},
	{
		id: "G5-ENG-CONV-DESCRIBE-04",
		name: "Show-and-Tell Conversation",
		icon: "🎤",
	},
] as const;
type Api = Pick<
	LearningFlowClient,
	| "open"
	| "answerBefore"
	| "completeSupport"
	| "withdrawSupport"
	| "presentAfter"
	| "answerAfter"
>;
type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type Row = Record<string, unknown>;

export function ConversationStreet({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: {
	api: Api;
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
					area_id: "G5-AREA-ENG-18",
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
				"conversation-street-support-v1" ||
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
		manifest?.game?.schema_version === "conversation-street-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main className="classroom-action-quest conversation-street">
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<p>Useful Expressions</p>
					<h1>Conversation Street</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list">
					<div className="cs-street" aria-hidden="true">
						<i>🏫</i>
						<b>💬</b>
						<i>🏠</i>
					</div>
					<p className="cs-privacy">
						<strong>Fictional conversations only.</strong> Never enter your
						name, age, address, school, family facts, likes, abilities, or pets.
					</p>
					{SKILLS.map((entry) => (
						<button
							className="caq-game-card"
							key={entry.id}
							onClick={() => void openSkill(entry.id)}
						>
							<span>{entry.icon}</span>
							<span>
								<strong>{entry.name}</strong>
								<small>Read and respond as the fictional people.</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={4}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<p className="cs-fictional-label">
								🎭 {String(game.fictional_notice)}
							</p>
							<ConversationBoard
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
								Send this fictional turn
							</button>
						</>
					)}
					{step === "support" &&
						support?.game_manifest.schema_version ===
							"conversation-street-support-v1" && (
							<section className="caq-support">
								<h2>{support.title_si}</h2>
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
										? "Next conversation step"
										: "I’m ready to talk as the character alone"}
								</button>
							</section>
						)}
					{step === "withdrawing" && (
						<p className="caq-status">
							The practice transcript, profile hints, scene cues, selected
							bubbles, and animation state are clearing.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Conversation turn complete!"
									: "Read the fictional conversation and try again."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct ? "Continue" : "Try a fresh conversation"}
							</button>
						</section>
					)}
					{step === "result" && (
						<section className="caq-feedback caq-result">
							<SuccessCelebration />
							<h2>Conversation Street complete!</h2>
							<p>
								You connected reviewed English turns using fictional
								information.
							</p>
						</section>
					)}
				</section>
			)}
		</main>
	);
}

function incomplete(response: ConstructedResponse) {
	switch (response.kind) {
		case "conversation_pair_links":
			return response.unlinked_question_tokens.length > 0;
		case "conversation_turn_sequence":
			return response.unused_turn_tokens.length > 0;
		case "fictional_profile_reply":
			return response.unused_chunk_tokens.length > 0;
		case "conversation_scene_reply":
			return response.response_token == null;
		default:
			return true;
	}
}

function ConversationBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	if (game.response_kind === "conversation_pair_links")
		return <PairBoard game={game} onResponse={onResponse} />;
	if (game.response_kind === "conversation_turn_sequence")
		return <TurnBoard game={game} onResponse={onResponse} />;
	if (game.response_kind === "fictional_profile_reply")
		return <ProfileBoard game={game} onResponse={onResponse} />;
	return <SceneBoard game={game} onResponse={onResponse} />;
}

function PairBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const questions = game.questions as Row[],
		responses = game.responses as Row[];
	const [selected, setSelected] = useState<string | null>(null),
		[links, setLinks] = useState<ConversationLink[]>([]),
		[trace, setTrace] = useState<string[]>([]);
	const link = (response: string) => {
		if (!selected) return;
		const remaining = links.filter(
				(row) => row.question !== selected && row.response !== response,
			),
			next = [
				...remaining,
				{ sequence: remaining.length + 1, question: selected, response },
			],
			nextTrace = [...trace, `link:${response}`];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		onResponse(
			pairLinksResponse(
				String(game.command_token),
				next,
				questions.map((row) => String(row.question_token)),
				nextTrace,
			),
		);
	};
	return (
		<section className="cs-venue">
			<SpeakerPair />
			<div className="cs-timeline">
				{questions.map((row, index) => (
					<button
						className={selected === row.question_token ? "selected" : ""}
						data-opaque-token={String(row.question_token)}
						key={String(row.question_token)}
						onClick={() => {
							setSelected(String(row.question_token));
							setTrace((value) => [
								...value,
								`select:${String(row.question_token)}`,
							]);
						}}
					>
						<span>Fictional speaker {index + 1}</span>
						<strong>{String(row.text_en)}</strong>
					</button>
				))}
			</div>
			<p className="cs-missing">Missing response turn</p>
			<div className="cs-response-sheet">
				{responses.map((row) => (
					<button
						data-opaque-token={String(row.response_token)}
						key={String(row.response_token)}
						onClick={() => link(String(row.response_token))}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
			<ConversationTranscript rows={questions} field="text_en" />
		</section>
	);
}

function TurnBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const turns = game.turns as Row[],
		all = turns.map((row) => String(row.turn_token));
	const [ordered, setOrdered] = useState<
		Array<{ turn: string; speaker: string }>
	>([]);
	const choose = (row: Row) => {
		if (ordered.some((item) => item.turn === row.turn_token)) return;
		const next = [
			...ordered,
			{ turn: String(row.turn_token), speaker: String(row.speaker_token) },
		];
		setOrdered(next);
		onResponse(
			turnSequenceResponse(
				String(game.command_token),
				String(game.dialogue_token),
				next,
				all,
				next.map((item) => `slot:${item.turn}`),
			),
		);
	};
	return (
		<section className="cs-venue">
			<SpeakerPair />
			<ol className="cs-ordered">
				{ordered.map((item) => (
					<li key={item.turn}>
						{String(turns.find((row) => row.turn_token === item.turn)?.text_en)}
					</li>
				))}
			</ol>
			<div className="cs-response-sheet">
				{turns.map((row) => (
					<button
						disabled={ordered.some((item) => item.turn === row.turn_token)}
						key={String(row.turn_token)}
						onClick={() => choose(row)}
					>
						<small>{speakerLabel(game, String(row.speaker_token))}</small>
						{String(row.text_en)}
					</button>
				))}
			</div>
			<button
				className="cs-clear"
				onClick={() => {
					setOrdered([]);
					onResponse(
						turnSequenceResponse(
							String(game.command_token),
							String(game.dialogue_token),
							[],
							all,
							["clear:all"],
						),
					);
				}}
			>
				Clear current timeline
			</button>
			<ConversationTranscript rows={turns} field="text_en" />
		</section>
	);
}

function ProfileBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const chunks = game.chunks as Row[],
		all = chunks.map((row) => String(row.chunk_token)),
		facts = game.profile_facts as Row[];
	const [ordered, setOrdered] = useState<string[]>([]);
	const emit = (next: string[], trace: string[]) =>
		onResponse(
			profileReplyResponse(
				String(game.command_token),
				String(game.profile_token),
				String(game.question_token),
				next,
				all,
				trace,
			),
		);
	return (
		<section className="cs-venue">
			<article className="cs-profile">
				<strong>🎭 Talk as this fictional character</strong>
				<h2>{String(game.profile_label)}</h2>
				{facts.map((row) => (
					<p key={String(row.fact_token)}>
						<b>{String(row.label)}:</b> {String(row.value)}
					</p>
				))}
			</article>
			<div className="cs-question-bubble">
				Fictional interviewer: <strong>{String(game.question_text)}</strong>
			</div>
			<div className="cs-slots">
				{all.map((token) => (
					<span key={`slot-${token}`}>
						{ordered.includes(token)
							? String(chunks.find((row) => row.chunk_token === token)?.text_en)
							: "…"}
					</span>
				))}
			</div>
			<div className="cs-response-sheet">
				{chunks.map((row) => (
					<button
						disabled={ordered.includes(String(row.chunk_token))}
						key={String(row.chunk_token)}
						onClick={() => {
							const next = [...ordered, String(row.chunk_token)];
							setOrdered(next);
							emit(
								next,
								next.map((token) => `slot:${token}`),
							);
						}}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
			<button
				className="cs-clear"
				onClick={() => {
					setOrdered([]);
					emit([], ["clear:all"]);
				}}
			>
				Clear current reply
			</button>
			<details>
				<summary>Accessible fictional profile</summary>
				{facts.map((row) => (
					<p key={`detail-${String(row.fact_token)}`}>
						{String(row.label)}: {String(row.value)}
					</p>
				))}
			</details>
		</section>
	);
}

function SceneBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const responses = game.responses as Row[],
		renderer = game.scene_renderer as Row;
	return (
		<section className="cs-venue">
			<SpeakerPair />
			<div
				className="cs-code-scene"
				role="img"
				aria-label={`Code-built fictional ${String(renderer.non_colour_cue)} scene`}
			>
				<span>{String(renderer.emoji)}</span>
				<i />
			</div>
			<div className="cs-question-bubble">
				Show-and-tell speaker: <strong>{String(game.prompt_text)}</strong>
			</div>
			<div className="cs-response-sheet">
				{responses.map((row) => (
					<button
						data-opaque-token={String(row.response_token)}
						key={String(row.response_token)}
						onClick={() =>
							onResponse(
								sceneReplyResponse(
									String(game.command_token),
									String(game.scene_token),
									String(game.prompt_token),
									String(row.response_token),
								),
							)
						}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
		</section>
	);
}

function SpeakerPair() {
	return (
		<section className="cs-speakers" aria-label="Two fictional speakers">
			<span>
				<i />
				Speaker A
			</span>
			<span>
				<i />
				Speaker B
			</span>
		</section>
	);
}
function ConversationTranscript({
	rows,
	field,
}: {
	rows: Row[];
	field: string;
}) {
	return (
		<details className="cs-transcript">
			<summary>Accessible transcript choices</summary>
			{rows.map((row) => (
				<p key={String(Object.values(row)[0])}>{String(row[field])}</p>
			))}
		</details>
	);
}
function speakerLabel(game: Game, token: string) {
	return String(
		(game.speaker_labels as Row[]).find((row) => row.speaker_token === token)
			?.label ?? "Fictional speaker",
	);
}
