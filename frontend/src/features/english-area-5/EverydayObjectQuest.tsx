// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
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
	EverydayObjectWorkedExample,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import {
	OBJECT_PICTURES,
	picture,
} from "../mobile-learning-flow/phaser-board/pictures";
import { SequenceBoard } from "../mobile-learning-flow/phaser-board/SequenceBoard";
import { sceneFor } from "../mobile-learning-flow/phaser-board/scenes";
import { TokenBoard } from "../mobile-learning-flow/phaser-board/TokenBoard";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import "../mobile-learning-flow/english-game-shared.css";
import "./everyday-object-quest.css";
import {
	objectMappingResponse,
	objectNameResponse,
} from "./everydayObjectLogic";
import { OBJECT_SKILLS } from "./manifest";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

const GLYPHS = [
	"🪑",
	"✏️",
	"📏",
	"🛏️",
	"🥄",
	"🪥",
	"🧹",
	"🍽️",
	"📘",
	"📒",
	"🧰",
	"📔",
	"✏️⚙️",
	"📎⚙️",
] as const;

export function EverydayObjectQuest({
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
		OBJECT_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = OBJECT_SKILLS[index];
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
					area_id: "G5-AREA-ENG-05",
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
		setMoves((value) => value + 1);
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
					"invalid_drop_count" in response ? response.invalid_drop_count : 0,
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
			support.game_manifest.schema_version !==
				"everyday-object-quest-support-v1"
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
		if (index < OBJECT_SKILLS.length - 1)
			void openSkill(OBJECT_SKILLS[index + 1].id);
		else setStep(done.length === OBJECT_SKILLS.length ? "result" : "games");
	};
	return (
		<main
			className="classroom-action-quest everyday-object-quest"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>What we use</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list" aria-label="What we use games">
					{OBJECT_SKILLS.map((skill, position) => (
						<button
							className="caq-game-card"
							key={skill.id}
							onClick={() => void openSkill(skill.id)}
						>
							<span className="object-icon" aria-hidden="true">
								{skill.icon}
							</span>
							<span>
								<strong>{skill.name}</strong>
								<small>{skill.description}</small>
								<em>{position + 1}/3 · Easy to challenging</em>
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
							activityCount={3}
							currentActivity={index + 1}
							completedActivities={completed.length}
						/>
					)}
					<p className="caq-position">
						Activity {index + 1}/3 · {active.name}
					</p>
					{step === "question" &&
						manifest?.game?.schema_version ===
							"everyday-object-quest-item-v1" && (
							<>
								<div className="caq-command">
									<span className="code-companion" aria-hidden="true">
										✏️✨📏
									</span>
									<strong>{manifest.prompt_si}</strong>
								</div>
								<ObjectActivity
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my objects
								</button>
							</>
						)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null}
							checkLabel="Check my objects"
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
								<ObjectActivity
									key={activity.revision_id}
									game={activity.game as Record<string, unknown>}
									onResponse={record}
								/>
							)}
						/>
					)}
					{step === "support" && support && !isSupportRound(support) && (
						<ObjectSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now tidy a fresh set on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Brilliant tidying!"
									: "Read the word and inspect the object again."}
							</h2>
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

type Row = Record<string, unknown>;
function _ObjectGlyph({ variant }: { variant: number }) {
	return (
		<span className="object-icon" aria-hidden="true">
			{GLYPHS[variant] ?? "🔷"}
		</span>
	);
}
export function ObjectActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	return game.response_kind === "object_name_sequence" ? (
		<NameBuilder game={game} onResponse={onResponse} />
	) : (
		<MappingBoard game={game} onResponse={onResponse} />
	);
}
function MappingBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	const vocabulary = game.response_kind === "object_vocabulary_mapping";
	const kind = game.response_kind as
		| "object_vocabulary_mapping"
		| "lesson_place_sort";
	const entries = (vocabulary ? game.words : game.entries) as Row[];
	return (
		<TokenBoard
			theme="meadow"
			layout={vocabulary ? "grid" : "bins"}
			scene={sceneFor("G5-AREA-ENG-05")}
			sources={entries}
			sourceKey={vocabulary ? "word_token" : "entry_token"}
			sourcePicture={(row) =>
				vocabulary
					? undefined
					: { emoji: picture(OBJECT_PICTURES, row.renderer_variant) }
			}
			targets={(vocabulary ? game.objects : game.zones) as Row[]}
			targetKey={vocabulary ? "object_token" : "zone_token"}
			target={(row) =>
				vocabulary
					? {
							picture: {
								emoji: picture(OBJECT_PICTURES, row.renderer_variant),
							},
						}
					: {
							label: String(row.display_en),
							capacity: entries.length,
							picture: { emoji: Number(row.zone_variant) === 0 ? "🏫" : "🏠" },
						}
			}
			instruction={
				vocabulary
					? "Drag each word onto the thing it names."
					: "Where does each thing belong? Drag it to the classroom or home."
			}
			build={(links, tokens, trace) =>
				objectMappingResponse(
					kind,
					String(game.command_token),
					links,
					tokens,
					trace,
				)
			}
			onResponse={onResponse}
		/>
	);
}

function NameBuilder({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	return (
		<SequenceBoard
			theme="meadow"
			scene={sceneFor("G5-AREA-ENG-05")}
			chunks={game.chunks as Row[]}
			chunkKey="chunk_token"
			picture={{ emoji: picture(OBJECT_PICTURES, game.renderer_variant) }}
			instruction="Put the words in order to name this thing."
			build={(ordered, _all, trace) =>
				objectNameResponse(
					String(game.command_token),
					String(game.object_token),
					ordered,
					trace,
				)
			}
			onResponse={onResponse}
		/>
	);
}

function ObjectSupport({
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
	if (
		support.game_manifest.schema_version !== "everyday-object-quest-support-v1"
	)
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's tidy another example</h2>
			<ObjectWorkedExample
				example={game.worked_example}
				reveal={stage > 0 || support.scaffold_type === "visual_guidance"}
			/>
			<ol>
				{game.worked_example.steps_si.map((text, index) => (
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
function ObjectWorkedExample({
	example,
	reveal,
}: {
	example: EverydayObjectWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	const count = response
		? response.kind === "object_name_sequence"
			? response.ordered_chunk_tokens.length
			: response.kind === "object_vocabulary_mapping" ||
					response.kind === "lesson_place_sort"
				? response.placements.length
				: 0
		: 0;
	return (
		<div className="wildlife-support-preview">
			<strong>{example.prompt_si}</strong>
			<span>
				{reveal ? `${count} connections shown on a fresh example` : "?"}
			</span>
		</div>
	);
}
