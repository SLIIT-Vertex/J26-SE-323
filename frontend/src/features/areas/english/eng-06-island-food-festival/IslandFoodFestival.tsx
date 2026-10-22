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
	ConstructedResponse,
	ExperimentCondition,
	IslandFoodWorkedExample,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../../../mobile-learning-flow/useSupportRound";
import "../../../mobile-learning-flow/english-game-shared.css";
import "./island-food-festival.css";
import {
	WordDropBoard,
	WordDropMotionContext,
	type WordDropState,
} from "../../../mobile-learning-flow/word-drop/WordDropBoard";
import {
	FOOD_GLYPHS,
	foodMappingResponse,
	foodNameResponse,
} from "./islandFoodLogic";
import { FOOD_SKILLS } from "./manifest";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function IslandFoodFestival({
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
		FOOD_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = FOOD_SKILLS[index];
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
					area_id: "G5-AREA-ENG-06",
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
			support.game_manifest.schema_version !== "island-food-festival-support-v1"
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
		if (index < FOOD_SKILLS.length - 1)
			void openSkill(FOOD_SKILLS[index + 1].id);
		else setStep(done.length === FOOD_SKILLS.length ? "result" : "games");
	};
	return (
		<WordDropMotionContext.Provider value={reducedMotion}>
			<main
				className="classroom-action-quest island-food-festival"
				data-reduced-motion={reducedMotion || undefined}
			>
				<header className="caq-header">
					<AdventureBackButton
						onClick={step === "games" ? onBack : () => setStep("games")}
					/>
					<div>
						<h1>Our food</h1>
					</div>
				</header>
				{step === "games" ? (
					<section className="caq-game-list" aria-label="Our food games">
						{FOOD_SKILLS.map((skill, position) => (
							<button
								className="caq-game-card"
								key={skill.id}
								onClick={() => void openSkill(skill.id)}
							>
								<span className="food-glyph" aria-hidden="true">
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
								"island-food-festival-item-v1" && (
								<>
									<div className="caq-command">
										<span>🍽️ Read, drag and discover</span>
										<strong>{manifest.prompt_si}</strong>
									</div>
									<FoodActivity
										key={manifest.revision_id}
										game={manifest.game as Record<string, unknown>}
										onResponse={record}
									/>
									<button
										className="caq-primary"
										disabled={busy || !response}
										onClick={confirm}
									>
										Check my foods
									</button>
								</>
							)}
						{step === "support" && isSupportRound(support) && (
							<SupportRoundPlay
								support={support}
								busy={busy}
								ready={response !== null}
								checkLabel="Check my foods"
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
									<FoodActivity
										key={activity.revision_id}
										game={activity.game as Record<string, unknown>}
										onResponse={record}
									/>
								)}
							/>
						)}
						{step === "support" && support && !isSupportRound(support) && (
							<FoodSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						)}
						{step === "withdrawing" && (
							<p className="caq-status" role="status">
								The help is going away. Now try a fresh festival card on your
								own.
							</p>
						)}
						{step === "feedback" && (
							<section className="caq-feedback">
								<h2>
									{correct
										? "Festival stamp earned!"
										: "Read the word and look at the food again."}
								</h2>
								<button className="caq-primary" onClick={advance}>
									{correct
										? index === 2
											? "Finish festival"
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
export function FoodGlyph({ variant }: { variant: number }) {
	return (
		<span className="food-glyph" aria-hidden="true">
			{FOOD_GLYPHS[variant] ?? "🍽️"}
		</span>
	);
}
export function FoodActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	return game.response_kind === "food_name_sequence" ? (
		<NameKitchen game={game} onResponse={onResponse} />
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
	const vocabulary = game.response_kind === "food_vocabulary_mapping";
	const sources = (vocabulary ? game.words : game.entries) as Row[];
	const targets = (vocabulary ? game.foods : game.stalls) as Row[];
	const sourceKey = vocabulary ? "word_token" : "entry_token",
		targetKey = vocabulary ? "food_token" : "stall_token";
	const baskets = ["🍞", "🍠", "🥛", "🍉", "🥕"];
	const basketNames = [
		"Bread, eggs & fish",
		"Yams & sweet potatoes",
		"Drinks",
		"Fruits",
		"Vegetables",
	];
	const emit = (state: WordDropState) =>
		onResponse(
			state.links.length === sources.length
				? {
						...foodMappingResponse(
							game.response_kind as
								| "food_vocabulary_mapping"
								| "food_lesson_group_sort",
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
		<section className="food-board">
			<WordDropBoard
				theme="market"
				single={vocabulary}
				instruction={
					vocabulary
						? "Drag each English word to its food picture."
						: "Drag each food into its basket. Look at the basket labels."
				}
				cards={sources.map((row) => ({
					id: String(row[sourceKey]),
					label: String(row.text_en),
					emoji: vocabulary ? undefined : foodEmoji(String(row.text_en)),
				}))}
				targets={targets.map((row, index) => ({
					id: String(row[targetKey]),
					label: vocabulary
						? `Picture ${index + 1}`
						: (basketNames[Number(row.stall_variant)] ??
							String(row.display_en)),
					emoji: vocabulary
						? (FOOD_GLYPHS[Number(row.renderer_variant)] ?? "🍽️")
						: (baskets[Number(row.stall_variant)] ?? "🧺"),
					hint: vocabulary ? "Choose a word" : "Drop food here",
				}))}
				onChange={emit}
			/>
		</section>
	);
}
function foodEmoji(label: string) {
	const names = [
		"Egg",
		"Bread",
		"Fish",
		"Coconut",
		"Buns",
		"Healthy Food",
		"Fatty Food",
		"Spicy Food",
		"Homemade Food",
		"Junk Food",
		"Manioc",
		"Sweet Potatoes",
		"Tea",
		"Milk",
		"Water",
		"Fruit Juice",
		"Banana",
		"Pineapple",
		"Mango",
		"Watermelon",
		"Olive",
		"Potato",
		"Cabbage",
		"Tomato",
		"Carrot",
		"Cucumber",
	];
	return FOOD_GLYPHS[names.indexOf(label)] ?? "🍽️";
}
function NameKitchen({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	const chunks = game.chunks as Row[];
	return (
		<section className="name-kitchen">
			<FoodGlyph variant={Number(game.renderer_variant)} />
			<WordDropBoard
				theme="market"
				instruction="Look at the food. Drag the words into the numbered spaces to build its name."
				cards={chunks.map((row) => ({
					id: String(row.chunk_token),
					label: String(row.text_en),
				}))}
				targets={chunks.map((_, index) => ({
					id: `slot-${index}`,
					label: `Word ${index + 1}`,
					emoji: "🍽️",
					hint: "Drop a word",
				}))}
				onChange={(state) => {
					if (state.links.length !== chunks.length) return onResponse(null);
					const ordered = chunks.map(
						(_, index) =>
							state.links.find((link) => link.target === `slot-${index}`)
								?.source ?? "",
					);
					onResponse({
						...foodNameResponse(
							String(game.command_token),
							String(game.food_token),
							ordered,
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
function FoodSupport({
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
		support.game_manifest.schema_version !== "island-food-festival-support-v1"
	)
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's try another festival example</h2>
			<FoodWorkedExample
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
function FoodWorkedExample({
	example,
	reveal,
}: {
	example: IslandFoodWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	const count = response
		? response.kind === "food_name_sequence"
			? response.ordered_chunk_tokens.length
			: response.kind === "food_vocabulary_mapping" ||
					response.kind === "food_lesson_group_sort"
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
