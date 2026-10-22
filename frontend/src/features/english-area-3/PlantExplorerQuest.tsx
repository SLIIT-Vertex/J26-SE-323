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
	ExperimentCondition,
	PlantExplorerWorkedExample,
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
import {
	WordDropBoard,
	WordDropMotionContext,
	type WordDropState,
} from "../mobile-learning-flow/word-drop/WordDropBoard";
import { PLANT_ASSET_ROOT, PLANT_SKILLS } from "./manifest";
import { numberPairResponse, plantMappingResponse } from "./plantExplorerLogic";
import "./plant-explorer.css";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function PlantExplorerQuest({
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
		PLANT_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = PLANT_SKILLS[index];
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
					area_id: "G5-AREA-ENG-03",
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
	const record = (value: ConstructedResponse | null) => {
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
			support.game_manifest.schema_version !== "plant-explorer-support-v1"
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
		if (index < PLANT_SKILLS.length - 1)
			void openSkill(PLANT_SKILLS[index + 1].id);
		else setStep(done.length === PLANT_SKILLS.length ? "result" : "games");
	};

	return (
		<WordDropMotionContext.Provider value={reducedMotion}>
			<main
				className="classroom-action-quest plant-explorer"
				data-reduced-motion={reducedMotion || undefined}
			>
				<header className="caq-header">
					<AdventureBackButton
						onClick={step === "games" ? onBack : () => setStep("games")}
					/>
					<div>
						<h1>Plants, Trees and Creepers</h1>
					</div>
				</header>
				{step === "games" ? (
					<section
						className="caq-game-list"
						aria-label="Plants, Trees and Creepers games"
					>
						{PLANT_SKILLS.map((skill, position) => (
							<button
								className="caq-game-card"
								key={skill.id}
								onClick={() => void openSkill(skill.id)}
							>
								<img src={`${PLANT_ASSET_ROOT}/${skill.asset}`} alt="" />
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
							manifest?.game?.schema_version === "plant-explorer-item-v1" && (
								<>
									<div className="caq-command">
										<span>Explore and connect</span>
										<strong>{manifest.prompt_si}</strong>
									</div>
									<PlantActivity
										key={manifest.revision_id}
										game={manifest.game as Record<string, unknown>}
										onResponse={record}
									/>
									<button
										className="caq-primary"
										disabled={busy || !response}
										onClick={confirm}
									>
										Check my garden
									</button>
								</>
							)}
						{step === "support" && isSupportRound(support) && (
							<SupportRoundPlay
								support={support}
								busy={busy}
								ready={response !== null}
								checkLabel="Check my garden"
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
									<PlantActivity
										key={activity.revision_id}
										game={activity.game as Record<string, unknown>}
										onResponse={record}
									/>
								)}
							/>
						)}
						{step === "support" && support && !isSupportRound(support) && (
							<PlantSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						)}
						{step === "withdrawing" && (
							<p className="caq-status" role="status">
								The help is going away. Now explore a fresh plant on your own.
							</p>
						)}
						{step === "feedback" && (
							<section className="caq-feedback">
								<h2>
									{correct ? "Great growing!" : friendlyFeedback(feedback)}
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
		</WordDropMotionContext.Provider>
	);
}

type Row = Record<string, unknown>;
export function PlantActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	return game.response_kind === "singular_plural_pairing" ? (
		<PairBoard game={game} onResponse={onResponse} />
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
	const vocabulary = game.response_kind === "plant_vocabulary_mapping";
	const sources = (vocabulary ? game.words : game.labels) as Row[],
		targets = (vocabulary ? game.targets : game.parts) as Row[];
	const sourceKey = vocabulary ? "word_token" : "label_token",
		targetKey = vocabulary ? "target_token" : "part_token";
	const emit = (state: WordDropState) =>
		onResponse(
			state.links.length === sources.length
				? {
						...plantMappingResponse(
							game.response_kind as
								| "plant_vocabulary_mapping"
								| "plant_part_labeling",
							String(game.command_token),
							state.links,
							sources.map((row) => String(row[sourceKey])),
							state.trace,
						),
						tap_alternative_used: state.usedTap,
						invalid_drop_count: state.invalidDrops,
					}
				: null,
		);
	return (
		<section className="plant-board">
			<WordDropBoard
				diagram={
					!vocabulary
						? String(game.scene_asset).includes("tree")
							? "tree"
							: true
						: false
				}
				instruction={
					vocabulary
						? "Drag each word to the matching plant-part picture."
						: "Look at each number on the plant. Drag the part's name into its numbered box."
				}
				cards={sources.map((row) => ({
					id: String(row[sourceKey]),
					label: String(row.text_en),
				}))}
				targets={targets.map((row, index) => ({
					id: String(row[targetKey]),
					label: `Picture ${index + 1}`,
					visual: String(row.visual_key),
					count: vocabulary ? 2 : 1,
					emoji: plantEmoji(String(row.visual_key)),
					hint: "Drop a word",
				}))}
				onChange={emit}
			/>
		</section>
	);
}
function plantEmoji(key: string) {
	return /root/.test(key)
		? "🌱"
		: /petal/.test(key)
			? "🌸"
			: /bud/.test(key)
				? "🌷"
				: /flower/.test(key)
					? "🌸"
					: /fruit/.test(key)
						? "🥭"
						: /branch|trunk/.test(key)
							? "🪵"
							: /stem/.test(key)
								? "🌱"
								: "🍃";
}
function PairBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	const concepts = game.concepts as Row[],
		forms = game.forms as Row[];
	const targets = concepts.flatMap((row, index) =>
		(["singular", "plural"] as const).map((slot) => ({
			id: `${String(row.concept_token)}:${slot}`,
			label: slot === "singular" ? "One" : "Many",
			visual: String(row.concept_key),
			emoji:
				slot === "singular"
					? plantEmoji(String(row.concept_key))
					: plantEmoji(String(row.concept_key)).repeat(3),
			count: slot === "singular" ? 1 : 3,
			hint: `Row ${index + 1} · ${slot === "singular" ? "one item" : "three items"}`,
		})),
	);
	return (
		<section className="plant-board">
			<WordDropBoard
				instruction="Look at each picture. Drag the word for one item or for many of the same item."
				cards={forms.map((row) => ({
					id: String(row.form_token),
					label: String(row.text_en),
				}))}
				targets={targets}
				onChange={(state) => {
					if (state.links.length !== forms.length) return onResponse(null);
					onResponse({
						...numberPairResponse(
							String(game.command_token),
							concepts.map((row) => ({
								concept_token: String(row.concept_token),
								singular_form_token:
									state.links.find(
										(link) =>
											link.target === `${String(row.concept_token)}:singular`,
									)?.source ?? "",
								plural_form_token:
									state.links.find(
										(link) =>
											link.target === `${String(row.concept_token)}:plural`,
									)?.source ?? "",
							})),
							state.trace,
						),
						tap_alternative_used: state.usedTap,
						invalid_drop_count: state.invalidDrops,
					});
				}}
			/>
		</section>
	);
}
function PlantSupport({
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
	if (support.game_manifest.schema_version !== "plant-explorer-support-v1")
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's grow another way</h2>
			<PlantWorkedExample
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
function PlantWorkedExample({
	example,
	reveal,
}: {
	example: PlantExplorerWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	return (
		<div className="caq-worked plant-support-preview">
			<strong>{example.prompt_si}</strong>
			<span>
				{reveal && response
					? response.kind === "singular_plural_pairing"
						? `${response.pairs.length} pairs completed`
						: response.kind === "plant_vocabulary_mapping"
							? `${response.placements.length} words connected`
							: response.kind === "plant_part_labeling"
								? `${response.labels.length} parts labelled`
								: "Plant connection shown"
					: "?"}
			</span>
		</div>
	);
}
function friendlyFeedback(code: string | null) {
	if (code?.includes("number") || code?.includes("plural"))
		return "Look at one and many, then check the word ending.";
	if (code?.includes("stem") || code?.includes("root"))
		return "Look carefully at where the plant part grows.";
	return "Read the plant word and look at the picture again.";
}
