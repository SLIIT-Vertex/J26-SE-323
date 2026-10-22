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
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	RomanAdventureWorkedExample,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import {
	EMOJI_LABELS,
	ROMAN_ASSET_ROOT,
	ROMAN_GAMES,
	ROMAN_SKILLS,
} from "./manifest";
import { arithmeticResponse, emojiResponse, matchResponse } from "./romanLogic";
import "./roman-adventure.css";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
export function RomanAdventureJourney({
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
		[skillId, setSkillId] = useState<string | null>(null),
		[episodeId, setEpisodeId] = useState<string | null>(null),
		[manifest, setManifest] = useState<PresentationManifest | null>(null),
		[support, setSupport] = useState<SupportView | null>(null),
		[response, setResponse] = useState<ConstructedResponse | null>(null),
		[correct, setCorrect] = useState(false),
		[feedback, setFeedback] = useState<string | null>(null),
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
			ROMAN_SKILLS.findIndex((s) => s.id === skillId),
		),
		active = ROMAN_SKILLS[index];
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
					area_id: "G5-AREA-MAT-16",
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
		setMoves((v) => v + 1);
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
				working_cell_count:
					response.kind === "emoji_quantity_to_roman"
						? response.counted_indices.length
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
		if (!episodeId || !support) return;
		const game = support.game_manifest;
		if (game.schema_version === "half-set-manifest-v1") return;
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
		const submit = api.answerSupported,
			game = support?.game_manifest,
			activity =
				game?.schema_version === "support-round-v1" ? game.activity : null;
		if (
			!submit ||
			!episodeId ||
			!response ||
			!game ||
			game.schema_version !== "support-round-v1" ||
			!activity
		)
			return;
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
		if (!skillId || !correct)
			return skillId ? void openSkill(skillId) : undefined;
		const done = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(done);
		setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) advance();
	}, [step, correct]);
	return (
		<main
			className="roman-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="roman-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<h1>රෝම සංඛ්‍යාංක</h1>
			</header>
			{step === "games" ? (
				<section className="roman-game-list" aria-label="රෝම සංඛ්‍යාංක ක්‍රීඩා">
					{ROMAN_GAMES.map((game, i) => (
						<button
							className="roman-game-card"
							key={game.id}
							onClick={() => void openSkill(ROMAN_SKILLS[i].id)}
						>
							<img src={`${ROMAN_ASSET_ROOT}/${game.asset}`} alt="" />
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
				<section className="roman-play game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={3}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="roman-position">
						ක්‍රියාකාරකම {index + 1}/3 · {active?.name}
					</p>
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<RomanActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="roman-primary"
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
									<RomanActivity
										key={activity.revision_id}
										game={activity.game}
										onResponse={record}
									/>
								)}
							>
								{support.game_manifest.stage_kind !== "view" && (
									<button
										className="roman-primary"
										disabled={busy || !response}
										onClick={() => void answerSupport()}
									>
										තහවුරු කරන්න
									</button>
								)}
							</SupportRoundFrame>
						) : (
							<RomanSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((v) => v + 1)}
								onComplete={finishSupport}
							/>
						))}{" "}
					{step === "withdrawing" && (
						<p role="status">පිළිතුරු සහිත සහාය ඉවත් කර අලුත් ප්‍රශ්නය සූදානම් කරමින්…</p>
					)}
					{step === "feedback" && !correct && (
						<section className="roman-feedback">
							<h2>{`${feedbackLabel(feedback)} නැවත බලමු.`}</h2>
							<button className="roman-primary" onClick={advance}>
								නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={index + 1}
							gameCount={ROMAN_GAMES.length}
							onContinue={() =>
								index < ROMAN_SKILLS.length - 1
									? void openSkill(ROMAN_SKILLS[index + 1].id)
									: setStep("games")
							}
						/>
					)}
				</section>
			)}
		</main>
	);
}
function feedbackLabel(value: string | null) {
	return value?.includes("count")
		? "ඉමෝජි ගණන"
		: value?.includes("symbol")
			? "රෝම සංකේත අනුපිළිවෙළ"
			: value?.includes("match")
				? "ගැළපීම"
				: "ගණිත පියවර";
}
export function RomanActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const kind = String(game.response_kind);
	if (kind === "roman_numeral_match")
		return <RomanMatchBridge game={game} onResponse={onResponse} />;
	if (kind === "emoji_quantity_to_roman")
		return <EmojiCounterGroup game={game} onResponse={onResponse} />;
	return <RomanArithmeticWorkspace game={game} onResponse={onResponse} />;
}
function RomanMatchBridge({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const values = list(game.arabic_values).map(Number),
		tiles = list(game.roman_tiles),
		[selected, setSelected] = useState<number | null>(null),
		[matches, setMatches] = useState<Record<number, string>>({}),
		[trace, setTrace] = useState<string[]>([]),
		[revisions, setRevisions] = useState(0);
	const place = (roman: string) => {
		if (selected === null) return;
		const revision = matches[selected] ? revisions + 1 : revisions,
			next = { ...matches, [selected]: roman },
			nextTrace = [...trace, `match:${selected}:${roman}`];
		setMatches(next);
		setTrace(nextTrace);
		setRevisions(revision);
		setSelected(null);
		onResponse(
			matchResponse(String(game.round_id), values, next, nextTrace, revision),
		);
	};
	return (
		<div
			className="roman-bridge"
			style={{
				backgroundImage: `url(${ROMAN_ASSET_ROOT}/roman-arch-frame.png)`,
			}}
		>
			<section aria-label="අරාබි අංක">
				{values.map((value) => (
					<button
						className={selected === value ? "selected" : ""}
						aria-pressed={selected === value}
						onClick={() => setSelected(value)}
						key={value}
					>
						{value}
						<small>{matches[value] && `→ ${matches[value]}`}</small>
					</button>
				))}
			</section>
			<section aria-label="රෝම සංඛ්‍යා">
				{tiles.map((roman) => (
					<button
						className="roman-tile"
						disabled={selected === null}
						onClick={() => place(roman)}
						key={roman}
					>
						{roman}
					</button>
				))}
			</section>
		</div>
	);
}
export function RomanSymbolBank({
	symbols,
	onAdd,
	onRemove,
}: {
	symbols: string[];
	onAdd(symbol: string): void;
	onRemove(): void;
}) {
	const keyboard = (event: React.KeyboardEvent<HTMLFieldSetElement>) => {
		const key = event.key.toLowerCase();
		if (["i", "v", "x"].includes(key)) {
			event.preventDefault();
			onAdd(key);
		} else if (event.key === "Backspace") {
			event.preventDefault();
			onRemove();
		}
	};
	return (
		<fieldset className="symbol-builder" onKeyDown={keyboard}>
			<legend>රෝම සංකේත යතුරු පුවරුව</legend>
			<div
				className="answer-rail"
				role="status"
				aria-label="ගොඩනැගූ රෝම සංඛ්‍යාව"
				aria-live="polite"
			>
				{symbols.length ? (
					symbols.map((s, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: each position is a distinct symbol slot.
						<span key={`${s}-${i}`}>{s}</span>
					))
				) : (
					<b>?</b>
				)}
			</div>
			<div className="symbol-bank">
				{["i", "v", "x"].map((s) => (
					<button
						aria-label={`${s} සංකේතය එකතු කරන්න`}
						onClick={() => onAdd(s)}
						key={s}
					>
						{s}
					</button>
				))}
				<button aria-label="අවසන් සංකේතය ඉවත් කරන්න" onClick={onRemove}>
					⌫
				</button>
			</div>
		</fieldset>
	);
}
function EmojiCounterGroup({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const quantity = Number(game.quantity),
		[counted, setCounted] = useState<number[]>([]),
		[symbols, setSymbols] = useState<string[]>([]),
		[trace, setTrace] = useState<string[]>([]),
		[revisions, setRevisions] = useState(0);
	const emit = (
		nextCount = counted,
		nextSymbols = symbols,
		nextTrace = trace,
		nextRevisions = revisions,
	) =>
		onResponse(
			emojiResponse(
				String(game.group_id),
				String(game.emoji_id),
				quantity,
				nextCount,
				nextSymbols,
				nextTrace,
				nextRevisions,
			),
		);
	const toggle = (i: number) => {
		const on = counted.includes(i),
			next = on
				? counted.filter((v) => v !== i)
				: [...counted, i].sort((a, b) => a - b),
			nextTrace = [...trace, `count:${i}:${on ? "off" : "on"}`];
		setCounted(next);
		setTrace(nextTrace);
		setRevisions((v) => v + (on ? 1 : 0));
		emit(next, symbols, nextTrace, revisions + (on ? 1 : 0));
	};
	const add = (s: string) => {
		const next = [...symbols, s],
			nextTrace = [...trace, `symbol:${s}`];
		setSymbols(next);
		setTrace(nextTrace);
		emit(counted, next, nextTrace, revisions);
	};
	const remove = () => {
		if (!symbols.length) return;
		const next = symbols.slice(0, -1),
			nextTrace = [...trace, "symbol:remove"];
		setSymbols(next);
		setTrace(nextTrace);
		setRevisions((v) => v + 1);
		emit(counted, next, nextTrace, revisions + 1);
	};
	return (
		<div className="emoji-workshop">
			<p className="count-display">
				ගණන් කළා: <strong>{counted.length}</strong>
			</p>
			<div className="emoji-grid">
				{Array.from({ length: quantity }, (_, i) => (
					<button
						className={counted.includes(i) ? "counted" : ""}
						aria-pressed={counted.includes(i)}
						aria-label={`${EMOJI_LABELS[String(game.emoji_id)] ?? "ඉමෝජිය"} ${i + 1} ගණන් කරන්න`}
						onClick={() => toggle(i)}
						// biome-ignore lint/suspicious/noArrayIndexKey: generated objects have stable ordinal identities.
						key={i}
					>
						{String(game.emoji_symbol)}
					</button>
				))}
			</div>
			<RomanSymbolBank symbols={symbols} onAdd={add} onRemove={remove} />
		</div>
	);
}
function RomanArithmeticWorkspace({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [symbols, setSymbols] = useState<string[]>([]),
		[trace, setTrace] = useState<string[]>([]),
		[revisions, setRevisions] = useState(0),
		left = String(game.left_roman),
		right = String(game.right_roman),
		operation = String(game.operation) as "add" | "subtract";
	const emit = (next: string[], nextTrace: string[], rev: number) =>
		onResponse(
			arithmeticResponse(
				String(game.problem_id),
				left,
				operation,
				right,
				next,
				nextTrace,
				rev,
			),
		);
	const add = (s: string) => {
		const next = [...symbols, s],
			t = [...trace, `symbol:${s}`];
		setSymbols(next);
		setTrace(t);
		emit(next, t, revisions);
	};
	const remove = () => {
		if (!symbols.length) return;
		const next = symbols.slice(0, -1),
			t = [...trace, "symbol:remove"],
			r = revisions + 1;
		setSymbols(next);
		setTrace(t);
		setRevisions(r);
		emit(next, t, r);
	};
	return (
		<div
			className="roman-calc"
			style={{
				backgroundImage: `url(${ROMAN_ASSET_ROOT}/roman-scroll-panel.png)`,
			}}
		>
			<div
				className="roman-expression"
				role="math"
				aria-label="විසඳිය යුතු රෝම සංඛ්‍යා ගැටලුව"
			>
				<span>{left}</span>
				<b>{operation === "add" ? "+" : "−"}</b>
				<span>{right}</span>
				<b>=</b>
			</div>
			<RomanSymbolBank symbols={symbols} onAdd={add} onRemove={remove} />
		</div>
	);
}
function RomanSupport({
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
	if (support.game_manifest.schema_version !== "roman-adventure-support-v1")
		return null;
	const manifest = support.game_manifest,
		example = manifest.worked_example,
		visual = manifest.scaffold_type === "visual_guidance";
	return (
		<section className="roman-support">
			<p>{support.title_si}</p>
			<h2>{example.prompt_si}</h2>
			{visual ? (
				<div className="roman-cue">
					<strong>i = 1</strong>
					<strong>v = 5</strong>
					<strong>x = 10</strong>
				</div>
			) : (
				<RomanWorkedDemo example={example} stage={stage} />
			)}
			<ol>
				{example.steps_si.map((text, i) => (
					<li className={i < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="roman-primary"
				onClick={stage < manifest.required_actions ? onNext : onComplete}
			>
				{stage < manifest.required_actions ? "ඊළඟ පියවර" : "දැන් මම කරමි"}
			</button>
		</section>
	);
}
export function RomanWorkedDemo({
	example,
	stage,
}: {
	example: RomanAdventureWorkedExample;
	stage: number;
}) {
	const response = example.correct_response;
	if (!response) return null;
	if (response.kind === "roman_numeral_match")
		return (
			<div className="worked-roman">
				{response.matches.map((m, i) => (
					<span key={m.arabic_value}>
						{m.arabic_value} {stage > i / 2 ? `→ ${m.selected_roman}` : "→ ?"}
					</span>
				))}
			</div>
		);
	if (response.kind === "emoji_quantity_to_roman")
		return (
			<div className="worked-emoji">
				<div>
					{Array.from({ length: response.quantity }, (_, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: demonstration objects have stable ordinal identities.
						<span className={stage > 0 ? "shown" : ""} key={i}>
							{String(example.game.emoji_symbol)}
						</span>
					))}
				</div>
				{stage > 1 && (
					<strong>
						{response.quantity} → {response.final_roman}
					</strong>
				)}
			</div>
		);
	if (response.kind === "roman_arithmetic")
		return (
			<div className="worked-calc">
				<strong>
					{response.left_roman} {response.operation === "add" ? "+" : "−"}{" "}
					{response.right_roman}
				</strong>
				{stage > 0 && (
					<span>
						{response.left_value_work}{" "}
						{response.operation === "add" ? "+" : "−"}{" "}
						{response.right_value_work}
					</span>
				)}
				{stage > 2 && (
					<b>
						= {response.final_value} = {response.final_roman}
					</b>
				)}
			</div>
		);
	return null;
}
function list(value: unknown): string[] {
	return Array.isArray(value) ? value.map(String) : [];
}
