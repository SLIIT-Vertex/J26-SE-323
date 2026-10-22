// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import {
	type CSSProperties,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import type {
	CapacityAdventureWorkedExample,
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	type CapacityArithmeticResponse,
	canonicalCapacityArithmetic,
	formatCapacity,
	portionCounts,
	splitCapacity,
} from "./capacityLogic";
import { CAPACITY_GAMES, CAPACITY_SKILLS } from "./manifest";
import "./capacity-adventure.css";

type Step =
	| "chapters"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function CapacityAdventureJourney({
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
	const [step, setStep] = useState<Step>("chapters"),
		[skillId, setSkillId] = useState<string | null>(null),
		[episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null),
		[support, setSupport] = useState<SupportView | null>(null),
		[response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false),
		[feedbackColumn, setFeedbackColumn] = useState<string | null>(null),
		[busy, setBusy] = useState(false),
		[supportStage, setSupportStage] = useState(0);
	const [completed, setCompleted] = useState<string[]>([]),
		[startedAt, setStartedAt] = useState(Date.now()),
		[moves, setMoves] = useState(0),
		[corrections, setCorrections] = useState(0),
		[exchanges, setExchanges] = useState(0),
		[overflows, setOverflows] = useState(0);
	const [pending, setPending] = useState<{
		episode: string;
		support: string;
		manifest: string;
	} | null>(null);
	const lock = useRef(false);
	const index = Math.max(
		0,
		CAPACITY_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = CAPACITY_SKILLS[index];
	const activeGameIndex = CAPACITY_GAMES.findIndex(
		(game) => game.id === active?.chapter,
	);
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
		setStartedAt(Date.now());
		setMoves(0);
		setCorrections(0);
		setExchanges(0);
		setOverflows(0);
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
					area_id: "G5-AREA-MAT-11",
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
	const record = (
		value: ConstructedResponse | null,
		evidence?: { correction?: boolean; exchange?: boolean; overflow?: boolean },
	) => {
		setResponse(value);
		setMoves((count) => count + 1);
		if (evidence?.correction) setCorrections((count) => count + 1);
		if (evidence?.exchange) setExchanges((count) => count + 1);
		if (evidence?.overflow) setOverflows((count) => count + 1);
	};
	const confirm = async () => {
		if (!episodeId || !manifest || !response || lock.current) return;
		lock.current = true;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			response_time_ms: reducedMotion ? null : Date.now() - startedAt,
			interaction_summary: {
				move_count: moves,
				correction_count: corrections,
				first_action_ms: 0,
				active_time_ms: reducedMotion ? 0 : Date.now() - startedAt,
				attempt_count: 1,
				working_cell_count: response.kind === "capacity_arithmetic" ? 4 : 0,
				exchange_count: exchanges,
				overflow_count: overflows,
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
		) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
			return;
		}
		setCorrect(next.server_score.correct === true);
		setFeedbackColumn(next.server_score.feedback_column ?? null);
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
			support.game_manifest.schema_version === "half-set-manifest-v1"
		)
			return;
		const game = support.game_manifest;
		if (
			game.schema_version !== "support-round-v1" &&
			supportStage < game.required_actions
		)
			return;
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
		if (done) advanceSupport(done);
	};
	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) {
			setPending({
				episode: next.episode_id,
				support: next.support_round.support_revision_id,
				manifest: next.support_round.manifest_revision_id,
			});
			setSupport(null);
			setResponse(null);
			setStep("withdrawing");
			return;
		}
		if (next.support) {
			setSupport(next.support);
			setSupportStage(0);
			reset();
		}
	};
	const answerSupport = async () => {
		const submit = api.answerSupported;
		const game = support?.game_manifest;
		if (
			!submit ||
			!episodeId ||
			!response ||
			!game ||
			game.schema_version !== "support-round-v1" ||
			!game.activity
		)
			return;
		const activity = game.activity;
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
					response_time_ms: Date.now() - startedAt,
					interaction_summary: { move_count: moves },
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceSupport(next);
	};
	const advance = () => {
		if (!skillId) return;
		if (!correct) {
			void openSkill(skillId);
			return;
		}
		const nextDone = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(nextDone);
		const nextSkill = CAPACITY_SKILLS[index + 1];
		if (nextSkill?.chapter === active?.chapter) void openSkill(nextSkill.id);
		else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) advance();
	}, [step, correct]);

	return (
		<main
			className="capacity-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="capacity-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>පරිමාව හා ධාරිතාව</h1>
			</header>
			{step === "chapters" ? (
				<section className="capacity-game-list" aria-label="ධාරිතා ක්‍රීඩා">
					{CAPACITY_GAMES.map((game) => (
						<button
							className="capacity-game-card"
							key={game.id}
							onClick={() => {
								const first = CAPACITY_SKILLS.find(
									(skill) => skill.chapter === game.id,
								);
								if (first) void openSkill(first.id);
							}}
						>
							<img src={game.asset} alt="" />
							<span>
								<strong>{game.title}</strong>
								<small>
									{game.challengeLabel} · {game.difficulty}
								</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="capacity-play game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={5}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="capacity-position">
						ක්‍රියාකාරකම {index + 1}/5 · {active?.name}
					</p>
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<CapacityActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="capacity-primary"
								disabled={busy || !response}
								onClick={confirm}
							>
								තහවුරු කරන්න
							</button>
						</>
					)}
					{step === "support" &&
						support &&
						(support.game_manifest.schema_version === "support-round-v1" ? (
							<SupportRoundFrame
								support={support}
								busy={busy}
								onViewComplete={() => void finishSupport()}
								renderActivity={(activity) => (
									<CapacityActivity
										key={activity.revision_id}
										game={activity.game}
										onResponse={record}
									/>
								)}
							>
								{support.game_manifest.stage_kind !== "view" && (
									<button
										className="capacity-primary"
										disabled={busy || !response}
										onClick={() => void answerSupport()}
									>
										තහවුරු කරන්න
									</button>
								)}
							</SupportRoundFrame>
						) : (
							<CapacitySupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						))}
					{step === "withdrawing" && (
						<p role="status">පිළිතුරු සහිත සහාය ඉවත් කර නව ප්‍රශ්නය සූදානම් කරමින්…</p>
					)}
					{step === "feedback" && !correct && (
						<section className="capacity-feedback">
							<h2>{feedbackName(feedbackColumn)} නැවත බලමු.</h2>
							<button className="capacity-primary" onClick={advance}>
								නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={activeGameIndex + 1}
							gameCount={CAPACITY_GAMES.length}
							onContinue={() => {
								const nextGame = CAPACITY_GAMES[activeGameIndex + 1];
								const nextSkill =
									nextGame &&
									CAPACITY_SKILLS.find(
										(skill) => skill.chapter === nextGame.id,
									);
								if (nextSkill) void openSkill(nextSkill.id);
								else setStep("chapters");
							}}
						/>
					)}
				</section>
			)}
		</main>
	);
}

function feedbackName(value: string | null) {
	return (
		(
			{
				scale: "පරිමාණය",
				total: "දැනට ඇති එකතුව",
				conversion: "1000 ml කාණ්ඩ",
				litres: "l තීරුව",
				millilitres: "ml තීරුව",
				delivery: "බෙදාහැරීම",
			} as Record<string, string>
		)[value ?? ""] ?? "ගණනය"
	);
}

export function CapacityActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(
		response: ConstructedResponse | null,
		evidence?: { correction?: boolean; exchange?: boolean; overflow?: boolean },
	): void;
}) {
	const kind = String(game.response_kind);
	if (kind === "vessel_reading")
		return <VesselActivity game={game} onResponse={onResponse} />;
	if (kind === "capacity_composition")
		return <RecipeBench game={game} onResponse={onResponse} />;
	if (kind === "capacity_conversion")
		return <TransferMachine game={game} onResponse={onResponse} />;
	if (kind === "capacity_arithmetic")
		return <CapacityWorkingTable game={game} onResponse={onResponse} />;
	return <DeliveryMission game={game} onResponse={onResponse} />;
}

export function GraduatedVessel({
	levelMl,
	activeTick,
	onTick,
}: {
	levelMl: number;
	activeTick?: number;
	onTick?(value: number): void;
}) {
	return (
		<fieldset className="graduated-vessel">
			<legend className="sr-only">දියර මට්ටම {levelMl} මිලිලීටර්</legend>
			<div className="vessel-body">
				<div
					className="liquid"
					style={{ height: `${vesselPercent(levelMl)}%` }}
				/>
				<div
					className="liquid-surface"
					style={{ bottom: `${vesselPercent(levelMl)}%` }}
				/>
				{Array.from({ length: 10 }, (_, index) => (index + 1) * 100)
					.reverse()
					.map((value) => (
						<button
							key={value}
							className={activeTick === value ? "active" : ""}
							style={{
								bottom: `calc(${vesselPercent(value)}% - 24px)`,
								minHeight: 48,
							}}
							aria-label={`${value} මිලිලීටර් සලකුණ`}
							onClick={() => onTick?.(value)}
						>
							<span>{value}</span>
						</button>
					))}
			</div>
			<strong>ml</strong>
		</fieldset>
	);
}

function vesselPercent(value: number) {
	return value / 10 - 5;
}

function VesselActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(
		response: ConstructedResponse | null,
		evidence?: { correction?: boolean },
	): void;
}) {
	const start = Number(game.start_level_ml);
	const [level, setLevel] = useState(start);
	const [actions, setActions] = useState<number[]>([]);
	const set = (next: number, correction = false) => {
		const safe = Math.max(100, Math.min(1000, next));
		const trace = [...actions, safe];
		setLevel(safe);
		setActions(trace);
		onResponse(
			{
				kind: "vessel_reading",
				capacity_ml: Number(game.capacity_ml),
				selected_tick_ml: safe,
				liquid_level_ml: safe,
				adjustment_actions: trace,
			},
			{ correction },
		);
	};
	return (
		<div className="vessel-workspace">
			<GraduatedVessel
				levelMl={level}
				activeTick={level}
				onTick={(value) => set(value, true)}
			/>
			<div className="pour-controls">
				<button
					aria-label="මිලිලීටර් 100 වත් කරන්න"
					disabled={level >= 1000}
					onClick={() => set(level + 100)}
				>
					+ 100 ml
				</button>
				<button
					aria-label="මිලිලීටර් 100 ඉවත් කරන්න"
					disabled={level <= 100}
					onClick={() => set(level - 100, true)}
				>
					− 100 ml
				</button>
			</div>
			<img
				className="pour-jug"
				src="/curriculum/game/G5-AREA-MAT-11/lab-pouring-jug.png"
				alt=""
			/>
		</div>
	);
}

function RecipeBench({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(
		response: ConstructedResponse | null,
		evidence?: { correction?: boolean; overflow?: boolean },
	): void;
}) {
	const target = Number(game.target_ml);
	const portions = Array.isArray(game.available_portions_ml)
		? game.available_portions_ml.map(Number)
		: [];
	const [selected, setSelected] = useState<number[]>([]);
	const total = selected.reduce((sum, value) => sum + value, 0);
	const emit = (next: number[], correction = false) => {
		const nextTotal = next.reduce((sum, value) => sum + value, 0);
		setSelected(next);
		onResponse(
			{
				kind: "capacity_composition",
				target_ml: target,
				selected_portions_ml: next,
				portion_counts: portionCounts(next),
				constructed_total_ml: nextTotal,
				overflow_ml: Math.max(0, nextTotal - target),
			},
			{ correction, overflow: nextTotal > target },
		);
	};
	return (
		<div className="recipe-bench">
			<TankFill level={Math.min(1000, total)} />
			<strong
				className={
					total > target ? "is-error" : total === target ? "is-complete" : ""
				}
			>
				දැනට: {total} ml {total === 1000 ? "= 1 l" : ""}
			</strong>
			<div className="portion-controls">
				{portions.map((value) => (
					<button
						key={value}
						aria-label={`${value} මිලිලීටර් කොටස වත් කරන්න`}
						onClick={() => emit([...selected, value])}
					>
						{value} ml
					</button>
				))}
			</div>
			<button
				className="capacity-secondary"
				disabled={!selected.length}
				onClick={() => emit(selected.slice(0, -1), true)}
			>
				අවසන් කොටස ඉවත් කරන්න
			</button>
		</div>
	);
}

function TankFill({ level }: { level: number }) {
	return (
		<div className="tank-fill">
			<img src="/curriculum/game/G5-AREA-MAT-11/litre-tank-frame.png" alt="" />
			<div className="tank-liquid" style={{ height: `${level / 10}%` }} />
		</div>
	);
}

function TransferMachine({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(
		response: ConstructedResponse | null,
		evidence?: { exchange?: boolean },
	): void;
}) {
	const total = Number(game.source_total_ml);
	const full = Math.floor(total / 1000);
	const leftover = total - full * 1000;
	// How many full 1000 ml jugs the child has poured into the litre tank.
	const [moved, setMoved] = useState(0);
	const [note, setNote] = useState(
		"1000 ml = 1 l. පිරුණු ජෝගු ලීටර් ටැංකියට වත් කරන්න.",
	);
	const emit = (count: number) =>
		onResponse(
			{
				kind: "capacity_conversion",
				source_litres: Number(game.source_litres),
				source_millilitres: Number(game.source_millilitres),
				source_total_ml: total,
				result_litres: count,
				result_millilitres: total - count * 1000,
				exchange_count: count,
			},
			{ exchange: true },
		);
	const pour = (count: number) => {
		setMoved(count);
		emit(count);
		setNote(
			count === full
				? `පිරුණු ජෝගු ${full} ම ගියා. ඉතිරි ${leftover} ml ලීටරයකට අඩු නිසා ml ලෙස තබන්න.`
				: `1 l ක් = 1000 ml. තවත් පිරුණු ජෝගු ${full - count} ක් ඇත.`,
		);
	};
	return (
		<div className="transfer-machine litre-machine">
			<p className="litre-machine-total">
				<strong>{total.toLocaleString("en-US").replace(",", " ")} ml</strong>
			</p>
			<p className="litre-machine-note" role="status">
				{note}
			</p>
			<div className="litre-machine-row">
				{/* biome-ignore lint/a11y/useSemanticElements: a fieldset would add form chrome to this drag-and-drop tray. */}
				<div className="litre-machine-jugs" role="group" aria-label="මිලිලීටර් ජෝගු">
					{Array.from({ length: full - moved }, (_, index) => (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: every full jug is the same 1000 ml.
							key={`full-${index}`}
							className="touch-target litre-jug is-full"
							aria-label="1000 ml ජෝගුව ලීටර් ටැංකියට වත් කරන්න"
							draggable
							onDragEnd={() => pour(moved + 1)}
							onClick={() => pour(moved + 1)}
						>
							<span aria-hidden="true">🫙</span>
							1000 ml
						</button>
					))}
					{leftover > 0 && (
						<button
							type="button"
							className="touch-target litre-jug is-partial"
							style={{ "--fill": `${leftover / 10}%` } as CSSProperties}
							onClick={() => {
								emit(moved);
								setNote(
									`${leftover} ml යනු 1000 ml ට අඩුයි — එයින් ලීටරයක් සෑදිය නොහැක. එය ${leftover} ml ලෙසම ඉතිරි වේ.`,
								);
							}}
						>
							<span aria-hidden="true">🥛</span>
							{leftover} ml
						</button>
					)}
				</div>
				<span className="litre-machine-arrow" aria-hidden="true">
					➜
				</span>
				{/* biome-ignore lint/a11y/useSemanticElements: a fieldset would add form chrome to this drop target. */}
				<div
					className="litre-machine-tank"
					role="group"
					aria-label={`ලීටර් ටැංකිය: ${moved} l`}
				>
					<img
						src="/curriculum/game/G5-AREA-MAT-11/litre-tank-frame.png"
						alt=""
					/>
					<div className="litre-machine-litres">
						{Array.from({ length: moved }, (_, index) => (
							<button
								type="button"
								// biome-ignore lint/suspicious/noArrayIndexKey: every litre in the tank is the same.
								key={`litre-${index}`}
								className="touch-target litre-chip"
								aria-label="1 l ආපසු ml ලෙස වත් කරන්න"
								onClick={() => pour(moved - 1)}
							>
								1 l
							</button>
						))}
					</div>
				</div>
			</div>
			<p className="litre-machine-answer" aria-live="polite">
				පිළිතුර: <b>{moved}</b> l <b>{total - moved * 1000}</b> ml
			</p>
		</div>
	);
}

type CapacityField = "mlWork" | "exchange" | "resultLitres" | "resultMl";

export function CapacityWorkingTable({
	game,
	onResponse,
	demo,
	demoStage = 4,
}: {
	game: Record<string, unknown>;
	onResponse?(
		response: ConstructedResponse | null,
		evidence?: { exchange?: boolean },
	): void;
	demo?: CapacityArithmeticResponse;
	demoStage?: number;
}) {
	const operation = String(game.operation) as "add" | "subtract";
	const leftL = Number(game.left_litres),
		leftMl = Number(game.left_millilitres),
		rightL = Number(game.right_litres),
		rightMl = Number(game.right_millilitres);
	const [active, setActive] = useState<CapacityField>("mlWork"),
		[values, setValues] = useState<Record<CapacityField, number | null>>({
			mlWork: null,
			exchange: null,
			resultLitres: null,
			resultMl: null,
		}),
		[order, setOrder] = useState<CapacityField[]>([]);
	const display = (field: CapacityField) => {
		if (!demo) return values[field];
		const revealAt: Record<CapacityField, number> = {
			mlWork: 1,
			exchange: 2,
			resultMl: 3,
			resultLitres: 4,
		};
		if (demoStage < revealAt[field]) return null;
		return {
			mlWork: demo.millilitre_subtotal_or_adjustment,
			exchange: demo.carried_or_borrowed_litres,
			resultLitres: demo.result_litres,
			resultMl: demo.result_millilitres,
		}[field];
	};
	const emit = (
		next: Record<CapacityField, number | null>,
		nextOrder: CapacityField[],
		exchange = false,
	) => {
		setValues(next);
		setOrder(nextOrder);
		if (!onResponse || Object.values(next).some((value) => value === null))
			return onResponse?.(null, { exchange });
		const canonical = canonicalCapacityArithmetic(
			operation,
			leftL,
			leftMl,
			rightL,
			rightMl,
		);
		const stepByField: Record<CapacityField, string> = {
			mlWork:
				operation === "add"
					? `ml:${leftMl}+${rightMl}=${next.mlWork}`
					: `ml:${next.mlWork}-${rightMl}=${next.resultMl}`,
			exchange:
				operation === "add"
					? `carry:${next.exchange}`
					: `borrow:${next.exchange}`,
			resultMl:
				operation === "add"
					? `ml-result:${next.resultMl}`
					: `adjust:${leftL}->${leftL - Number(next.exchange)}:${leftMl}->${next.mlWork}`,
			resultLitres:
				operation === "add"
					? `litres:${leftL}+${rightL}+${next.exchange}=${next.resultLitres}`
					: `litres:${leftL - Number(next.exchange)}-${rightL}=${next.resultLitres}`,
		};
		let steps = nextOrder.map((field) => stepByField[field]);
		if (
			operation === "subtract" &&
			nextOrder.join() === "exchange,mlWork,resultMl,resultLitres"
		)
			steps = [
				stepByField.exchange,
				stepByField.resultMl,
				stepByField.mlWork,
				stepByField.resultLitres,
			];
		onResponse(
			{
				...canonical,
				millilitre_subtotal_or_adjustment: Number(next.mlWork),
				carried_or_borrowed_litres: Number(next.exchange),
				exchange_used: Number(next.exchange) > 0,
				working_steps: steps,
				result_litres: Number(next.resultLitres),
				result_millilitres: Number(next.resultMl),
			},
			{ exchange },
		);
	};
	const write = (digit: number, clear = false) => {
		if (demo) return;
		const next = {
			...values,
			[active]: clear
				? null
				: Number(`${values[active] ?? ""}${digit}`.slice(-4)),
		};
		const nextOrder: CapacityField[] = clear
			? order.filter((field) => field !== active)
			: order.includes(active)
				? order
				: [...order, active];
		emit(next, nextOrder);
	};
	return (
		<fieldset
			className="capacity-working"
			onKeyDown={(event) => {
				if (/^[0-9]$/.test(event.key)) write(Number(event.key));
				if (event.key === "Backspace") write(0, true);
			}}
		>
			<legend className="sr-only">ලීටර් සහ මිලිලීටර් ලිඛිත වගුව</legend>
			<table className="capacity-table">
				<thead>
					<tr>
						<th>ක්‍රියාව</th>
						<th>l</th>
						<th>ml</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<th>පළමු අගය</th>
						<td>{leftL}</td>
						<td>{String(leftMl).padStart(3, "0")}</td>
					</tr>
					<tr>
						<th>{operation === "add" ? "+" : "−"} දෙවන අගය</th>
						<td>{rightL}</td>
						<td>{String(rightMl).padStart(3, "0")}</td>
					</tr>
					<tr className="exchange-row">
						<th>හුවමාරුව</th>
						<td>
							<CapacityCell
								label="ගෙන ගිය හෝ ණයට ගත් ලීටර්"
								field="exchange"
								active={active}
								value={display("exchange")}
								select={setActive}
							/>
						</td>
						<td>
							<CapacityCell
								label="මිලිලීටර් එකතුව හෝ සකස් කළ අගය"
								field="mlWork"
								active={active}
								value={display("mlWork")}
								select={setActive}
							/>
						</td>
					</tr>
					<tr className="answer-row">
						<th>පිළිතුර</th>
						<td>
							<CapacityCell
								label="අවසාන ලීටර්"
								field="resultLitres"
								active={active}
								value={display("resultLitres")}
								select={setActive}
							/>
						</td>
						<td>
							<CapacityCell
								label="අවසාන මිලිලීටර්"
								field="resultMl"
								active={active}
								value={display("resultMl")}
								select={setActive}
								threeDigits
							/>
						</td>
					</tr>
				</tbody>
			</table>
			{!demo && (
				<>
					<button
						className="exchange-control"
						onClick={() => {
							const next = { ...values, exchange: 1 };
							const nextOrder: CapacityField[] = order.includes("exchange")
								? order
								: [...order, "exchange"];
							emit(next, nextOrder, true);
							setActive("mlWork");
						}}
					>
						1000 ml ⇄ 1 l
					</button>
					<NumberPad onDigit={write} onClear={() => write(0, true)} />
					<div className="field-navigation">
						{(
							[
								"mlWork",
								"exchange",
								"resultMl",
								"resultLitres",
							] as CapacityField[]
						).map((field) => (
							<button
								aria-pressed={active === field}
								key={field}
								onClick={() => setActive(field)}
							>
								{
									{
										mlWork: "ml වැඩ",
										exchange: "හුවමාරුව",
										resultMl: "පිළිතුරු ml",
										resultLitres: "පිළිතුරු l",
									}[field]
								}
							</button>
						))}
					</div>
				</>
			)}
			<p className="exchange-note">1000 ml = 1 l</p>
		</fieldset>
	);
}

function CapacityCell({
	label,
	field,
	active,
	value,
	select,
	threeDigits,
}: {
	label: string;
	field: CapacityField;
	active: CapacityField;
	value: number | null;
	select(field: CapacityField): void;
	threeDigits?: boolean;
}) {
	return (
		<button
			className={`capacity-cell ${active === field ? "selected" : ""}`}
			aria-label={label}
			aria-pressed={active === field}
			onClick={() => select(field)}
		>
			{value === null
				? "?"
				: threeDigits
					? String(value).padStart(3, "0")
					: value}
		</button>
	);
}
function NumberPad({
	onDigit,
	onClear,
}: {
	onDigit(value: number): void;
	onClear(): void;
}) {
	return (
		<fieldset className="capacity-keypad">
			<legend className="sr-only">අංක යතුරු පුවරුව</legend>
			{[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map((number) => (
				<button
					aria-label={`අංක ${number}`}
					key={number}
					onClick={() => onDigit(number)}
				>
					{number}
				</button>
			))}
			<button aria-label="තෝරාගත් කොටුව හිස් කරන්න" onClick={onClear}>
				⌫
			</button>
		</fieldset>
	);
}

function DeliveryMission({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(
		response: ConstructedResponse | null,
		evidence?: { correction?: boolean; overflow?: boolean },
	): void;
}) {
	const request = Number(game.requested_total_ml),
		available = Array.isArray(game.available_containers_ml)
			? game.available_containers_ml.map(Number)
			: [];
	const [selected, setSelected] = useState<number[]>([]);
	const total = selected.reduce((sum, value) => sum + value, 0);
	const emit = (next: number[], correction = false) => {
		const delivered = next.reduce((sum, value) => sum + value, 0),
			parts = splitCapacity(delivered);
		setSelected(next);
		onResponse(
			{
				kind: "capacity_delivery",
				mission_id: String(game.mission_id),
				requested_total_ml: request,
				selected_containers_ml: next,
				delivered_total_ml: delivered,
				working_steps: next
					.map((value) => `portion:${value}`)
					.concat([
						`total:${delivered}`,
						`convert:${delivered}=${parts.litres}:${parts.millilitres}`,
					]),
				result_litres: parts.litres,
				result_millilitres: parts.millilitres,
				remaining_or_overflow_ml: Math.abs(request - delivered),
				contextual_answer: `delivered:${delivered}`,
			},
			{ correction, overflow: delivered > request },
		);
	};
	return (
		<div className="delivery-mission">
			<img
				src="/curriculum/game/G5-AREA-MAT-11/water-delivery-cart.png"
				alt=""
			/>
			<div className="delivery-request">
				<strong>ඉල්ලීම: {formatCapacity(request)}</strong>
				<span>බෙදාහැරූ ප්‍රමාණය: {formatCapacity(total)}</span>
			</div>
			<div className="portion-controls">
				{available.map((value) => (
					<button
						key={value}
						aria-label={`${value} මිලිලීටර් රථයට පටවන්න`}
						onClick={() => emit([...selected, value])}
					>
						{value} ml
					</button>
				))}
			</div>
			<button
				className="capacity-secondary"
				disabled={!selected.length}
				onClick={() => emit(selected.slice(0, -1), true)}
			>
				අවසන් භාජනය ඉවත් කරන්න
			</button>
		</div>
	);
}

function CapacitySupport({
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
	if (support.game_manifest.schema_version !== "capacity-adventure-support-v1")
		return null;
	const manifest = support.game_manifest;
	const example = manifest.worked_example;
	return (
		<section className="capacity-support">
			<p className="support-type">{support.title_si}</p>
			<h2>{example.prompt_si}</h2>
			{manifest.scaffold_type === "visual_guidance" ? (
				<CapacityVisualCue game={example.game as Record<string, unknown>} />
			) : (
				<CapacityWorkedDemo example={example} stage={stage} />
			)}
			<ol>
				{example.steps_si.map((text, index) => (
					<li className={index < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="capacity-primary"
				onClick={stage < manifest.required_actions ? onNext : onComplete}
			>
				{stage < manifest.required_actions ? "ඊළඟ පියවර" : "දැන් මම කරමි"}
			</button>
		</section>
	);
}

function CapacityVisualCue({ game }: { game: Record<string, unknown> }) {
	const kind = String(game.response_kind);
	if (kind === "vessel_reading")
		return (
			<div className="capacity-visual-cue">
				<GraduatedVessel levelMl={Number(game.start_level_ml)} />
			</div>
		);
	if (kind === "capacity_composition")
		return (
			<div className="capacity-visual-cue">
				<TankFill level={0} />
				<strong>හිස් කොටස බලන්න.</strong>
			</div>
		);
	if (kind === "capacity_arithmetic")
		return (
			<div className="capacity-visual-cue">
				<table className="capacity-table">
					<thead>
						<tr>
							<th>ක්‍රියාව</th>
							<th>l</th>
							<th className="cue-focus">ml</th>
						</tr>
					</thead>
					<tbody>
						<tr>
							<th>පළමු අගය</th>
							<td>{String(game.left_litres)}</td>
							<td className="cue-focus">
								{String(game.left_millilitres).padStart(3, "0")}
							</td>
						</tr>
						<tr>
							<th>{game.operation === "add" ? "+" : "−"} දෙවන අගය</th>
							<td>{String(game.right_litres)}</td>
							<td className="cue-focus">
								{String(game.right_millilitres).padStart(3, "0")}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		);
	return (
		<div className="capacity-visual-cue">
			<div className="group-blocks">
				<i>1000 ml</i>
				<i>1000 ml</i>
			</div>
			<strong>
				{kind === "capacity_delivery" ? "මූලාශ්‍රය → ගමනාන්තය" : "1000 ml → 1 l"}
			</strong>
		</div>
	);
}

export function CapacityWorkedDemo({
	example,
	stage,
}: {
	example: CapacityAdventureWorkedExample;
	stage: number;
}) {
	const response = example.correct_response;
	const game = example.game as Record<string, unknown>;
	if (!response) return null;
	if (response.kind === "vessel_reading")
		return (
			<div className="capacity-worked">
				<GraduatedVessel
					levelMl={
						stage >= 3
							? response.liquid_level_ml
							: Math.max(100, response.liquid_level_ml - (3 - stage) * 100)
					}
					activeTick={stage >= 3 ? response.selected_tick_ml : undefined}
				/>
				{stage >= 3 && <strong>{response.capacity_ml} ml</strong>}
			</div>
		);
	if (response.kind === "capacity_composition") {
		const visible = response.selected_portions_ml.slice(0, stage);
		const total = visible.reduce((sum, value) => sum + value, 0);
		return (
			<div className="capacity-worked">
				<TankFill level={total} />
				<strong>
					{total} ml {stage >= example.steps_si.length ? "= 1 l" : ""}
				</strong>
				{stage >= example.steps_si.length && (
					<small>වෙනත් නිවැරදි සංයෝජනද ඇත.</small>
				)}
			</div>
		);
	}
	if (response.kind === "capacity_conversion") {
		const groups = Array.from(
			{ length: Math.min(stage, response.exchange_count) },
			(_, index) => `worked-group-${index + 1}`,
		);
		return (
			<div className="capacity-worked">
				<div className="group-blocks">
					{groups.map((group) => (
						<i key={group}>1000 ml → 1 l</i>
					))}
				</div>
				{stage >= 3 && (
					<strong>
						{response.result_litres} l {response.result_millilitres} ml
					</strong>
				)}
			</div>
		);
	}
	if (response.kind === "capacity_arithmetic")
		return (
			<div className="capacity-worked">
				<CapacityWorkingTable game={game} demo={response} demoStage={stage} />
				{stage >= 4 && (
					<strong>
						{response.result_litres} l{" "}
						{String(response.result_millilitres).padStart(3, "0")} ml
					</strong>
				)}
			</div>
		);
	if (response.kind === "capacity_delivery") {
		const visible = taggedValues(
			response.selected_containers_ml.slice(0, stage),
		);
		return (
			<div className="capacity-worked">
				<img
					src="/curriculum/game/G5-AREA-MAT-11/water-delivery-cart.png"
					alt=""
				/>
				<div className="group-blocks">
					{visible.map((entry) => (
						<i key={entry.key}>{entry.value} ml</i>
					))}
				</div>
				{stage >= example.steps_si.length && (
					<strong>{formatCapacity(response.delivered_total_ml)}</strong>
				)}
			</div>
		);
	}
	return null;
}

function taggedValues(values: number[]) {
	const seen = new Map<number, number>();
	return values.map((value) => {
		const occurrence = (seen.get(value) ?? 0) + 1;
		seen.set(value, occurrence);
		return { value, key: `${value}-${occurrence}` };
	});
}
