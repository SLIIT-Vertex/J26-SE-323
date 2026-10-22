// biome-ignore-all lint/a11y/useButtonType: game buttons do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
	ConstructedResponse,
	ChildEpisodeResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	canonicalDistanceArithmetic,
	formatMetres,
	type DistanceArithmeticResponse,
} from "./distanceLogic";
import { DISTANCE_GAMES, DISTANCE_SKILLS } from "./manifest";
import "./distance-adventure.css";

type Step =
	| "chapters"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
export function DistanceAdventureJourney({
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
		[episodeId, setEpisodeId] = useState<string | null>(null),
		[manifest, setManifest] = useState<PresentationManifest | null>(null),
		[support, setSupport] = useState<SupportView | null>(null),
		[response, setResponse] = useState<ConstructedResponse | null>(null),
		[correct, setCorrect] = useState(false),
		[feedbackColumn, setFeedbackColumn] = useState<string | null>(null),
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
	const lock = useRef(false);
	const index = Math.max(
		0,
		DISTANCE_SKILLS.findIndex((s) => s.id === skillId),
	);
	const active = DISTANCE_SKILLS[index];
	const activeGameIndex = DISTANCE_GAMES.findIndex((game) => game.id === active?.chapter);
	const run = useCallback(
		async <T,>(job: () => Promise<T>) => {
			setBusy(true);
			try {
				return await job();
			} catch (e) {
				onFailure(e);
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
					area_id: "G5-AREA-MAT-09",
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
		setMoves((n) => n + 1);
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
				correction_count: 0,
				first_action_ms: 0,
				active_time_ms: reducedMotion ? 0 : Date.now() - startedAt,
				attempt_count: 1,
				working_cell_count: response.kind.includes("distance") ? 4 : 2,
				exchange_count:
					"exchange_or_regrouping_used" in response &&
					response.exchange_or_regrouping_used
						? 1
						: 0,
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
		const gm = support.game_manifest;
		if (gm.schema_version !== "support-round-v1" && supportStage < gm.required_actions) return;
		const done = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Date.now() - startedAt,
					steps_viewed: Math.max(1, supportStage),
					manifest_revision_id: gm.revision_id,
					interaction_summary: {
						completed: true,
						renderer_id: gm.renderer_id,
						parallel_example_id: gm.parallel_example_id,
						support_actions: supportStage,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (done) advanceSupport(done);
	};
	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) { setPending({ episode: next.episode_id, support: next.support_round.support_revision_id, manifest: next.support_round.manifest_revision_id }); setSupport(null); setResponse(null); setStep("withdrawing"); return; }
		if (next.support) { setSupport(next.support); setSupportStage(0); reset(); }
	};
	const answerSupport = async () => {
		const submit = api.answerSupported; const gm = support?.game_manifest;
		if (!submit || !episodeId || !response || !gm || gm.schema_version !== "support-round-v1" || !gm.activity) return; const activity = gm.activity;
		const next = await run(() => submit(episodeId, { constructed_response: { ...response, presentation_id: activity.presentation_id, item_revision_id: activity.revision_id, interaction_version: "constructed-response-v1" }, response_time_ms: Math.max(0, Date.now() - startedAt), interaction_summary: { move_count: moves } }, crypto.randomUUID()));
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
		const nextSkill = DISTANCE_SKILLS[index + 1];
		if (nextSkill?.chapter === active?.chapter) void openSkill(nextSkill.id);
		else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) advance();
	}, [step, correct]);
	return (
		<main
			className="distance-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="distance-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<div>
					<h1>දිග හා දුර</h1>
				</div>
			</header>
			{step === "chapters" ? (
				<section className="distance-game-list" aria-label="දුර ක්‍රීඩා">
					{DISTANCE_GAMES.map((g) => (
						<button
							className="distance-game-card"
							key={g.id}
							onClick={() => {
								const first = DISTANCE_SKILLS.find((s) => s.chapter === g.id);
								if (first) void openSkill(first.id);
							}}
						>
							<img src={g.asset} alt="" />
							<span>
								<strong>{g.title}</strong>
								<small>
									අභියෝග {g.challengeCount}ක් · {g.difficulty}
								</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="distance-play game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={5}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="distance-position">
						ක්‍රියාකාරකම {index + 1}/5 · {active?.name}
					</p>
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<DistanceActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="distance-primary"
								disabled={busy || !response}
								onClick={confirm}
							>
								තහවුරු කරන්න
							</button>
						</>
					)}
					{step === "support" && support && (
						support.game_manifest.schema_version === "support-round-v1" ? <SupportRoundFrame support={support} busy={busy} onViewComplete={() => void finishSupport()} renderActivity={(activity) => <DistanceActivity key={activity.revision_id} game={activity.game} onResponse={record} />}>
							{support.game_manifest.stage_kind !== "view" && <button type="button" className="distance-primary" disabled={busy || !response} onClick={() => void answerSupport()}>තහවුරු කරන්න</button>}
						</SupportRoundFrame> : <DistanceSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((v) => v + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p role="status">පිළිතුරු සහිත සහාය ඉවත් කර නව ප්‍රශ්නය සූදානම් කරමින්…</p>
					)}
					{step === "feedback" && !correct && (
						<section className="distance-feedback">
							<h2>
								{`${feedbackColumn === "kilometres" ? "km" : feedbackColumn === "conversion" ? "ඒකක මාරුව" : "m තීරුව"} නැවත බලමු.`}
							</h2>
							<button className="distance-primary" onClick={advance}>
								සහාය සමඟ නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={activeGameIndex + 1}
							gameCount={DISTANCE_GAMES.length}
							onContinue={() => {
								const nextGame = DISTANCE_GAMES[activeGameIndex + 1];
								const nextSkill = nextGame && DISTANCE_SKILLS.find((item) => item.chapter === nextGame.id);
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

function NumberPad({
	onDigit,
	onClear,
}: {
	onDigit(digit: number): void;
	onClear(): void;
}) {
	return (
		<fieldset className="distance-keypad">
			<legend className="sr-only">අංක යතුරු පුවරුව</legend>
			{[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map((n) => (
				<button key={n} aria-label={`අංක ${n}`} onClick={() => onDigit(n)}>
					{n}
				</button>
			))}
			<button aria-label="තෝරාගත් කොටුව හිස් කරන්න" onClick={onClear}>
				⌫
			</button>
		</fieldset>
	);
}
type Field = "subtotal" | "exchange" | "resultKm" | "resultM";
export function CompoundDistanceTable({
	game,
	onComplete,
	demo,
	reveal = true,
}: {
	game: Record<string, unknown>;
	onComplete?(response: DistanceArithmeticResponse | null): void;
	demo?: DistanceArithmeticResponse;
	reveal?: boolean;
}) {
	const operation = String(game.operation) as "add" | "subtract";
	const leftKm = Number(game.left_kilometres),
		leftM = Number(game.left_metres),
		rightKm = Number(game.right_kilometres),
		rightM = Number(game.right_metres);
	const [active, setActive] = useState<Field>("subtotal"),
		[values, setValues] = useState<Record<Field, number | null>>({
			subtotal: null,
			exchange: null,
			resultKm: null,
			resultM: null,
		});
	const expected = demo && reveal ? demo : null;
	const emit = (next: Record<Field, number | null>) => {
		setValues(next);
		if (!onComplete || Object.values(next).some((v) => v === null))
			return onComplete?.(null);
		const canonical = canonicalDistanceArithmetic(
			operation,
			leftKm,
			leftM,
			rightKm,
			rightM,
		);
		onComplete({
			...canonical,
			metre_subtotal_or_adjustment: next.subtotal as number,
			exchange_or_regrouping_used: (next.exchange as number) > 0,
			carried_or_borrowed_kilometres: next.exchange as number,
			result_kilometres: next.resultKm as number,
			result_metres: next.resultM as number,
		});
	};
	const display = (field: Field) =>
		expected
			? {
					subtotal: expected.metre_subtotal_or_adjustment,
					exchange: expected.carried_or_borrowed_kilometres,
					resultKm: expected.result_kilometres,
					resultM: expected.result_metres,
				}[field]
			: values[field];
	const write = (digit: number, clear = false) => {
		if (expected) return;
		const max = active === "exchange" ? 1 : active === "resultM" ? 3 : 4;
		emit({
			...values,
			[active]: clear
				? null
				: Number(`${values[active] ?? ""}${digit}`.slice(-max)),
		});
	};
	const nextField: Record<Field, Field> = {
		subtotal: "exchange",
		exchange: "resultM",
		resultM: "resultKm",
		resultKm: "resultKm",
	};
	const prompt: Record<Field, string> = {
		subtotal:
			operation === "add"
				? "පළමුව m තීරුව එකතු කරන්න."
				: "අවශ්‍ය නම් 1 km = 1000 m ණයට ගෙන m අඩු කරන්න.",
		exchange:
			operation === "add"
				? "1000 m කණ්ඩායමක් තිබේ නම් 1 km ලෙස මාරු කරන්න."
				: "ණයට ගත් km ගණන ලියන්න.",
		resultM: "පිළිතුරේ m කොටස ලියන්න.",
		resultKm: "අවසানে km තීරුව ගණනය කරන්න.",
	};
	return (
		<fieldset
			className="compound-workspace"
			onKeyDown={(e) => {
				if (/^[0-9]$/.test(e.key)) write(Number(e.key));
				if (e.key === "Backspace") write(0, true);
			}}
		>
			<legend className="sr-only">කිලෝමීටර් මීටර් ලිඛිත වගුව</legend>
			{!expected && (
				<p className="distance-step-prompt" role="status">
					{prompt[active]}
				</p>
			)}
			<table className="compound-table">
				<thead>
					<tr>
						<th>ක්‍රියාව</th>
						<th>km</th>
						<th>m</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<th>පළමු දුර</th>
						<td>{leftKm}</td>
						<td>{formatMetres(leftM)}</td>
					</tr>
					<tr>
						<th>{operation === "add" ? "+" : "−"} දෙවන දුර</th>
						<td>{rightKm}</td>
						<td>{formatMetres(rightM)}</td>
					</tr>
					<tr className="exchange-row">
						<th>හුවමාරුව</th>
						<td>
							<Cell
								label="හුවමාරු කළ km ගණන"
								field="exchange"
								active={active}
								value={display("exchange")}
								select={setActive}
							/>
						</td>
						<td>
							<Cell
								label="m ගණනය හෝ සකස් කළ m"
								field="subtotal"
								active={active}
								value={display("subtotal")}
								select={setActive}
							/>
						</td>
					</tr>
					<tr className="answer-row">
						<th>පිළිතුර</th>
						<td>
							<Cell
								label="අවසාන km"
								field="resultKm"
								active={active}
								value={display("resultKm")}
								select={setActive}
							/>
						</td>
						<td>
							<Cell
								label="අවසාන m"
								field="resultM"
								active={active}
								value={display("resultM")}
								select={setActive}
							/>
						</td>
					</tr>
				</tbody>
			</table>
			{!expected && (
				<>
					<NumberPad onDigit={write} onClear={() => write(0, true)} />
					<button
						className="distance-next-cell"
						onClick={() => setActive(nextField[active])}
					>
						ඊළඟ කොටුව →
					</button>
				</>
			)}
			<p className="exchange-note">1000 m ⇄ 1 km</p>
		</fieldset>
	);
}
function Cell({
	label,
	field,
	active,
	value,
	select,
}: {
	label: string;
	field: Field;
	active: Field;
	value: number | null;
	select(field: Field): void;
}) {
	return (
		<button
			style={{ minWidth: 48, minHeight: 48 }}
			className={`distance-cell ${active === field ? "selected" : ""}`}
			aria-label={label}
			aria-pressed={active === field}
			onClick={() => select(field)}
		>
			{value ?? "?"}
		</button>
	);
}

export function DistanceActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const kind = String(game.response_kind);
	if (kind === "unit_relationship")
		return <UnitBridge onResponse={onResponse} />;
	if (kind === "distance_conversion")
		return (
			<ConversionActivity
				total={Number(game.source_value)}
				onResponse={onResponse}
			/>
		);
	const story = kind === "distance_story";
	if (story)
		return <StoryDistanceActivity game={game} onResponse={onResponse} />;
	return (
		<div className="distance-story">
			<img
				className="distance-story-asset"
				src="/curriculum/game/G5-AREA-MAT-09/distance-journey-bus.png"
				alt=""
			/>
			<CompoundDistanceTable
				game={game}
				onComplete={(working) => {
					if (!working) return onResponse(null);
					onResponse(working);
				}}
			/>
		</div>
	);
}
function StoryDistanceActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [operation, setOperation] = useState<"add" | "subtract" | null>(null);
	return (
		<div className="distance-story">
			<div className="story-sequence">
				<b>කතාව</b>
				<span>→</span>
				<b>ගණිත ක්‍රියාව</b>
				<span>→</span>
				<b>km/m වගුව</b>
				<span>→</span>
				<b>පිළිතුර</b>
			</div>
			<fieldset className="story-operations">
				<legend className="sr-only">කතාවට ගැළපෙන ක්‍රියාව</legend>
				<button
					aria-pressed={operation === "add"}
					onClick={() => {
						setOperation("add");
						onResponse(null);
					}}
				>
					එකතු කරන්න +
				</button>
				<button
					aria-pressed={operation === "subtract"}
					onClick={() => {
						setOperation("subtract");
						onResponse(null);
					}}
				>
					අඩු කරන්න −
				</button>
			</fieldset>
			{operation && (
				<CompoundDistanceTable
					game={{ ...game, operation }}
					onComplete={(working) => {
						if (!working) return onResponse(null);
						onResponse({
							kind: "distance_story",
							problem_id: String(game.problem_id),
							operation,
							working_steps: working,
							result_kilometres: working.result_kilometres,
							result_metres: working.result_metres,
							contextual_answer: `${game.context_mode}:${working.result_kilometres}:${working.result_metres}`,
						});
					}}
				/>
			)}
		</div>
	);
}
function UnitBridge({
	onResponse,
}: {
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [selected, setSelected] = useState<string[]>([]);
	const choose = (label: string) => {
		const next = selected.includes(label) ? selected : [...selected, label];
		setSelected(next);
		onResponse(
			next.length === 4
				? {
						kind: "unit_relationship",
						left_unit: "km",
						right_unit: "m",
						conversion_factor: 1000,
						placements: ["1 km", "1000 m", "1 m", "100 cm"],
					}
				: null,
		);
	};
	return (
		<section className="unit-bridge">
			<button
				aria-pressed={selected.includes("1 km")}
				onClick={() => choose("1 km")}
			>
				1 km
			</button>
			<span>⇄</span>
			<button
				aria-pressed={selected.includes("1000 m")}
				onClick={() => choose("1000 m")}
			>
				1000 m
			</button>
			<span>⇄</span>
			<div className="centimetre-bridge">
				<button
					aria-pressed={selected.includes("1 m")}
					onClick={() => choose("1 m")}
				>
					1 m
				</button>
				<span>=</span>
				<button
					aria-pressed={selected.includes("100 cm")}
					onClick={() => choose("100 cm")}
				>
					100 cm
				</button>
			</div>
		</section>
	);
}
function ConversionActivity({
	total,
	onResponse,
}: {
	total: number;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [active, setActive] = useState<"km" | "m">("km"),
		[km, setKm] = useState<number | null>(null),
		[m, setM] = useState<number | null>(null);
	const emit = (nextKm: number | null, nextM: number | null) => {
		setKm(nextKm);
		setM(nextM);
		onResponse(
			nextKm === null || nextM === null
				? null
				: {
						kind: "distance_conversion",
						source_value: total,
						source_unit: "m",
						kilometres: nextKm,
						metres: nextM,
						total_metres: nextKm * 1000 + nextM,
						formal_metres: String(nextM).padStart(3, "0"),
					},
		);
	};
	const write = (d: number, clear = false) =>
		active === "km"
			? emit(clear ? null : Number(`${km ?? ""}${d}`.slice(-3)), m)
			: emit(km, clear ? null : Number(`${m ?? ""}${d}`.slice(-3)));
	return (
		<section className="conversion-workspace">
			<img
				className="distance-marker-asset"
				src="/curriculum/game/G5-AREA-MAT-09/distance-marker.png"
				alt=""
			/>
			<div
				className="thousand-blocks"
				role="img"
				aria-label={`${total} මීටර්, 1000 බැගින් කණ්ඩායම් කරන්න`}
			>
				<b>{total} m</b>
				<span>1000 m බැගින් km බවට</span>
			</div>
			<div className="conversion-cells">
				<button
					className={active === "km" ? "selected" : ""}
					aria-label="කිලෝමීටර් ගණන"
					onClick={() => setActive("km")}
				>
					{km ?? "?"} km
				</button>
				<button
					className={active === "m" ? "selected" : ""}
					aria-label="ඉතිරි මීටර් ඉලක්කම් තුනකින්"
					onClick={() => setActive("m")}
				>
					{m === null ? "???" : formatMetres(m)} m
				</button>
			</div>
			<NumberPad onDigit={write} onClear={() => write(0, true)} />
		</section>
	);
}
function DistanceSupport({
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
		support.game_manifest.schema_version === "half-set-manifest-v1" ||
		support.game_manifest.schema_version === "support-round-v1"
	)
		return null;
	const gm = support.game_manifest;
	const example = gm.worked_example;
	const answer = example.correct_response;
	const arithmetic =
		answer?.kind === "distance_arithmetic"
			? answer
			: answer?.kind === "distance_story"
				? answer.working_steps
				: null;
	return (
		<section className="distance-support">
			<p>{support.title_si}</p>
			<h2>{example.prompt_si}</h2>
			{arithmetic ? (
				<CompoundDistanceTable
					game={example.game as Record<string, unknown>}
					demo={arithmetic}
					reveal={stage > 0}
				/>
			) : stage > 0 && answer?.kind === "distance_conversion" ? (
				<div className="distance-demo">
					<b>{answer.source_value} m</b>
					<span>→ 1000 m බැගින් කණ්ඩායම් →</span>
					<strong>
						{answer.kilometres} km {answer.formal_metres} m
					</strong>
				</div>
			) : stage > 0 && answer?.kind === "unit_relationship" ? (
				<div className="distance-demo">
					<strong>1 km = 1000 m</strong>
					<span>සහ</span>
					<strong>1 m = 100 cm</strong>
				</div>
			) : (
				<div className="focus-cue">
					{gm.focus_column === "kilometres"
						? "km"
						: gm.focus_column === "conversion"
							? "km ⇄ m"
							: "m"}{" "}
					තීරුව බලන්න
				</div>
			)}
			<ol>
				{example.steps_si.map((line, i) => (
					<li className={i < stage ? "done" : ""} key={line}>
						{line}
					</li>
				))}
			</ol>
			<button
				className="distance-primary"
				onClick={stage < gm.required_actions ? onNext : onComplete}
			>
				{stage < gm.required_actions ? "ඊළඟ පියවර" : "දැන් මම කරමි"}
			</button>
		</section>
	);
}
