// biome-ignore-all lint/a11y/useButtonType: application controls do not submit forms.
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { ChildEpisodeResponse, ConstructedResponse, ExperimentCondition, PresentationManifest, SupportView } from "../mobile-learning-flow/api/generated";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import { AdventureBackButton, GameSuccessScreen } from "../mobile-learning-flow/AdventureShared";
import { AdventureProgress, adaptiveGameProgressStage } from "../mobile-learning-flow/AdventureProgress";
import { SupportRoundFrame } from "../mobile-learning-flow/SupportRoundFrame";
import { TIME_GAMES, TIME_SKILLS, type TimeChapter } from "./manifest";
import { analogClockResponse, arithmeticResponse, conversionResponse, elapsedResponse, unitMatchResponse } from "./timeLogic";
import "./time-adventure.css";

type Step = "chapters" | "question" | "feedback" | "support" | "withdrawing" | "result";
const CLOCK_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

export function TimeAdventureJourney({ api, learnerId, condition, reducedMotion, onBack, onFailure }: {
	api: GameApi;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("chapters");
	const [chapter, setChapter] = useState<TimeChapter | null>(null);
	const [skillId, setSkillId] = useState<string | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
	const [busy, setBusy] = useState(false);
	const [actions, setActions] = useState(0);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [moves, setMoves] = useState(0);
	const [attempts, setAttempts] = useState<Record<string, number>>({});
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{ episodeId: string; supportRevisionId: string; manifestRevisionId: string } | null>(null);
	const inFlight = useRef(false);
	const skills = useMemo(() => TIME_SKILLS.filter((item) => item.chapter === chapter), [chapter]);
	const challengeIndex = Math.max(0, skills.findIndex((item) => item.id === skillId));
	const chapterIndex = TIME_GAMES.findIndex((game) => game.id === chapter);
	const reset = useCallback(() => { setResponse(null); setMoves(0); setStartedAt(Date.now()); }, []);
	const run = useCallback(async <T,>(operation: () => Promise<T>) => {
		setBusy(true);
		try { return await operation(); } catch (error) { onFailure(error); return undefined; } finally { setBusy(false); }
	}, [onFailure]);

	useEffect(() => {
		if (step !== "withdrawing" || !pendingWithdrawal) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() => api.withdrawSupport(pendingWithdrawal.episodeId, {
				request_id: crypto.randomUUID(), support_revision_id: pendingWithdrawal.supportRevisionId,
				manifest_revision_id: pendingWithdrawal.manifestRevisionId, all_support_removed: true,
				answer_revealing_state_cleared: true, input_handlers_cleared: true,
			}, crypto.randomUUID()));
			if (!withdrawn || cancelled) return;
			const next = await run(() => api.presentAfter(pendingWithdrawal.episodeId, crypto.randomUUID()));
			if (!next || cancelled) return;
			setManifest(next.manifest); setSupport(null); setPendingWithdrawal(null); reset(); setStep("question");
		})();
		return () => { cancelled = true; };
	}, [api, pendingWithdrawal, reset, run, step]);

	const openSkill = async (nextSkill: string, nextChapter: TimeChapter) => {
		if (inFlight.current) return;
		inFlight.current = true;
		const opened = await run(() => api.open({ learner_id: learnerId, session_id: crypto.randomUUID(), grade: 5, medium: "si", condition, environment: "development", allow_draft: true, area_id: "G5-AREA-MAT-07", atomic_skill_id: nextSkill }, crypto.randomUUID()));
		inFlight.current = false;
		if (!opened) return;
		setChapter(nextChapter); setSkillId(nextSkill); setEpisodeId(opened.episode_id); setManifest(opened.manifest); setSupport(null); setCorrect(false); reset(); setStep("question");
	};

	const record = (next: ConstructedResponse) => { setResponse(next); setMoves((value) => value + 1); };
	const confirm = async () => {
		if (!episodeId || !manifest || !response || inFlight.current) return;
		inFlight.current = true;
		const body = { constructed_response: { ...response, presentation_id: manifest.presentation_id, item_revision_id: manifest.revision_id, interaction_version: "constructed-response-v1" as const }, response_time_ms: Date.now() - startedAt, interaction_summary: { move_count: moves, correction_count: 0, first_action_ms: 0, active_time_ms: Date.now() - startedAt, attempt_count: (skillId ? attempts[skillId] ?? 0 : 0) + 1, evidence_quality: 0.8, all_objects_placed: true } };
		const next = await run(() => manifest.measurement_role === "unsupported_after" ? api.answerAfter(episodeId, body, crypto.randomUUID()) : api.answerBefore(episodeId, body, crypto.randomUUID()));
		inFlight.current = false;
		if (!next) return;
		if (!next.server_score || next.server_score.presentation_id !== manifest.presentation_id || next.server_score.item_revision_id !== manifest.revision_id) { onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST")); return; }
		const isCorrect = next.server_score.correct === true;
		setCorrect(isCorrect);
		if (!isCorrect && skillId) setAttempts((current) => ({ ...current, [skillId]: (current[skillId] ?? 0) + 1 }));
		if (next.status === "support_active" && next.support) { setSupport(next.support); setActions(0); setStep("support"); } else setStep("feedback");
	};

	const finishSupport = async () => {
		if (!episodeId || !support || (support.game_manifest.schema_version !== "support-round-v1" && actions < Number((support.game_manifest as { required_actions?: number }).required_actions ?? 1))) return;
		const completed = await run(() => api.completeSupport(episodeId, { duration_ms: Date.now() - startedAt, steps_viewed: Math.min(8, Math.max(1, actions)), manifest_revision_id: support.game_manifest.revision_id, interaction_summary: { completed: true, action_count: actions, exact_failed_activity: true } }, crypto.randomUUID()));
		if (completed) advanceSupport(completed);
	};
	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) { setPendingWithdrawal({ episodeId: next.episode_id, supportRevisionId: next.support_round.support_revision_id, manifestRevisionId: next.support_round.manifest_revision_id }); setResponse(null); setSupport(null); setStep("withdrawing"); return; }
		if (next.support) { setSupport(next.support); setActions(0); reset(); }
	};
	const answerSupport = async () => {
		const submit = api.answerSupported; const game = support?.game_manifest;
		if (!submit || !episodeId || !response || !game || game.schema_version !== "support-round-v1" || !game.activity) return; const activity = game.activity;
		const next = await run(() => submit(episodeId, { constructed_response: { ...response, presentation_id: activity.presentation_id, item_revision_id: activity.revision_id, interaction_version: "constructed-response-v1" }, response_time_ms: Date.now() - startedAt, interaction_summary: { move_count: moves } }, crypto.randomUUID()));
		if (next) advanceSupport(next);
	};

	const continueAfterFeedback = () => {
		if (!correct || !chapter) { reset(); setStep("question"); return; }
		if (challengeIndex + 1 < skills.length) void openSkill(skills[challengeIndex + 1].id, chapter); else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => { if (step === "feedback" && correct) continueAfterFeedback(); }, [step, correct]);

	return <main className="time-adventure" data-reduced-motion={reducedMotion || undefined}>
		<header className="time-header"><AdventureBackButton onClick={step === "chapters" ? onBack : () => setStep("chapters")} /><h1>කාලය</h1></header>
		{step === "chapters" ? <section className="time-game-list" aria-label="කාල ක්‍රීඩා">{TIME_GAMES.map((game) => <button className="time-game-card" key={game.id} onClick={() => { const first = TIME_SKILLS.find((item) => item.chapter === game.id); if (first) void openSkill(first.id, game.id); }}><img src={game.asset} alt="" /><span><strong>{game.title}</strong><small>අභියෝග {game.challengeCount}ක් · {game.difficulty}</small></span></button>)}</section> :
		<section className="time-play-shell game-play-surface"><AdventureProgress stage={adaptiveGameProgressStage(step, manifest?.measurement_role)} />
			{chapter && <p className="time-position">ක්‍රීඩාව {chapterIndex + 1} · අභියෝගය {challengeIndex + 1}/{skills.length}</p>}
			{step === "question" && manifest?.game && <><h2>{manifest.prompt_si}</h2><TimeActivity key={manifest.revision_id} game={manifest.game as Record<string, unknown>} onResponse={record} /><button className="time-primary" disabled={busy || !response} onClick={confirm}>තහවුරු කරන්න</button></>}
			{step === "support" && support && (support.game_manifest.schema_version === "support-round-v1" ? <SupportRoundFrame support={support} busy={busy} onViewComplete={() => void finishSupport()} renderActivity={(activity) => <TimeActivity key={activity.revision_id} game={activity.game} onResponse={record} />}>
				{support.game_manifest.stage_kind !== "view" && <button className="time-primary" disabled={busy || !response} onClick={() => void answerSupport()}>තහවුරු කරන්න</button>}
			</SupportRoundFrame> : <TimeSupport support={support} actions={actions} onAction={() => setActions((value) => value + 1)} onComplete={finishSupport} />)}
			{step === "withdrawing" && <p className="time-status" role="status">සහාය ඉවත් කර නව ප්‍රශ්නය සූදානම් කරමින්…</p>}
			{step === "feedback" && !correct && <div className="time-feedback"><h2>නැවත බලමු.</h2><button className="time-primary" onClick={continueAfterFeedback}>නැවත උත්සාහ කරන්න</button></div>}
			{step === "result" && chapter && <GameSuccessScreen gameNumber={chapterIndex + 1} gameCount={TIME_GAMES.length} onContinue={() => { const next = TIME_GAMES[chapterIndex + 1]; if (!next) { setStep("chapters"); return; } const first = TIME_SKILLS.find((item) => item.chapter === next.id); if (first) void openSkill(first.id, next.id); }} />}
		</section>}
	</main>;
}

export function AnalogueClock({ hour, minute }: { hour: number; minute: number }) {
	return <div className="analogue-clock" role="img" aria-label={`${hour}:${String(minute).padStart(2, "0")} වේලාව`}>
		{CLOCK_NUMBERS.map((number) => <span className="clock-number" style={{ "--i": number } as CSSProperties} key={`clock-${number}`}>{number}</span>)}
		<span className="clock-hand hour" style={{ transform: `rotate(${hour * 30 + minute / 2}deg)` }} /><span className="clock-hand minute" style={{ transform: `rotate(${minute * 6}deg)` }} /><span className="clock-pin" />
	</div>;
}

function Stepper({ label, value, min, max, step = 1, onChange }: { label: string; value: number; min: number; max: number; step?: number; onChange(value: number): void }) {
	return <div className="time-stepper"><span>{label}</span><div><button style={{ minWidth: 48, minHeight: 48 }} aria-label={`${label} අඩු කරන්න`} disabled={value <= min} onClick={() => onChange(Math.max(min, value - step))}>−</button><strong>{String(value).padStart(2, "0")}</strong><button style={{ minWidth: 48, minHeight: 48 }} aria-label={`${label} එකතු කරන්න`} disabled={value >= max} onClick={() => onChange(Math.min(max, value + step))}>+</button></div></div>;
}

export function TimeActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse): void }) {
	const kind = String(game.response_kind);
	const [hour, setHour] = useState(kind === "analog_clock" ? 1 : 0);
	const [minute, setMinute] = useState(0);
	const leftOptions = Array.isArray(game.left_options) ? game.left_options as Array<[number, string]> : [];
	const rightOptions = Array.isArray(game.right_options) ? game.right_options as Array<[number, string]> : [];
	const [matches, setMatches] = useState<number[]>(Array(leftOptions.length).fill(-1));
	const emitTime = (nextHour: number, nextMinute: number) => {
		if (kind === "analog_clock") onResponse(analogClockResponse(nextHour, nextMinute));
		else if (kind === "time_conversion") onResponse(conversionResponse(nextHour, nextMinute));
		else if (kind === "elapsed_time") onResponse(elapsedResponse(nextHour, nextMinute));
		else onResponse(arithmeticResponse(nextHour, nextMinute, true));
	};
	if (kind === "time_unit_match") return <div className="unit-match-grid">{leftOptions.map((row, index) => <div className="unit-match" key={`${row[0]}-${row[1]}`}><span>{row[0]} {unitName(row[1])}</span><span aria-hidden="true">=</span><select aria-label={`${row[0]} ${unitName(row[1])} සඳහා ගැළපෙන සම්බන්ධතාව තෝරන්න`} value={matches[index]} onChange={(event) => { const next = [...matches]; next[index] = Number(event.target.value); setMatches(next); onResponse(unitMatchResponse(next)); }}><option value={-1}>තෝරන්න</option>{rightOptions.map((target, targetIndex) => <option value={targetIndex} key={`${target[0]}-${target[1]}`}>{target[0]} {unitName(target[1])}</option>)}</select></div>)}</div>;
	const sourceHour = Number(game.source_hour ?? 0), sourceMinute = Number(game.source_minute ?? 0);
	return <div className="time-workbench">
		{kind === "analog_clock" && <AnalogueClock hour={hour} minute={minute} />}
		{kind === "time_conversion" && <div className="source-time"><AnalogueClock hour={sourceHour} minute={sourceMinute} /><strong>{game.period === "am" ? "පෙ.ව." : "ප.ව."}</strong></div>}
		{kind === "elapsed_time" && <div className="time-route"><TimeBadge label="ආරම්භය" hour={Number(game.start_hour)} minute={Number(game.start_minute)} /><img src="/curriculum/game/G5-AREA-MAT-07/time-journey-bus.png" alt="" /><TimeBadge label="අවසානය" hour={Number(game.end_hour)} minute={Number(game.end_minute)} /></div>}
		{kind === "time_arithmetic" && <TimeTable game={game} />}
		<div className="time-controls"><Stepper label={kind === "time_conversion" ? "පැය 24" : "පැය"} value={hour} min={kind === "analog_clock" ? 1 : 0} max={kind === "analog_clock" ? 12 : 23} onChange={(value) => { setHour(value); emitTime(value, minute); }} /><Stepper label="මිනිත්තු" value={minute} min={0} max={55} step={5} onChange={(value) => { setMinute(value); emitTime(hour, value); }} /></div>
	</div>;
}

function TimeBadge({ label, hour, minute }: { label: string; hour: number; minute: number }) { return <div className="time-badge"><small>{label}</small><strong>{hour}:{String(minute).padStart(2, "0")}</strong></div>; }
function TimeTable({ game }: { game: Record<string, unknown> }) { return <table className="time-table"><thead><tr><th>පැය</th><th>මිනිත්තු</th></tr></thead><tbody><tr><td>{Number(game.left_hours)}</td><td>{Number(game.left_minutes)}</td></tr><tr><td>{game.operation === "add" ? "+" : "−"} {Number(game.right_hours)}</td><td>{Number(game.right_minutes)}</td></tr><tr><td>?</td><td>?</td></tr></tbody></table>; }
function unitName(value: string) { return ({ seconds: "තත්පර", minutes: "මිනිත්තු", hours: "පැය", days: "දින", weeks: "සති", months: "මාස", years: "අවුරුදු", ordinary_years: "සාමාන්‍ය අවුරුද්ද", leap_years: "අධික අවුරුද්ද" } as Record<string, string>)[value] ?? value; }

type WorkedExample = {
	prompt_si?: string;
	steps_si?: string[];
	game?: Record<string, unknown>;
	correct_response?: Record<string, unknown> | null;
};

function clockText(hour: number, minute: number) { return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`; }

export function TimeWorkedDemo({ example, stage }: { example?: WorkedExample; stage: number }) {
	const game = example?.game ?? {};
	const answer = example?.correct_response;
	if (!answer) return <div className="worked-demo visual-cue"><span className="demo-pulse" aria-hidden="true">●</span><strong>වර්ණයෙන් පෙන්වන කොටස මුලින් බලන්න.</strong></div>;
	const kind = String(game.response_kind ?? answer.kind ?? "");
	if (kind === "time_unit_match") {
		const left = Array.isArray(game.left_options) ? game.left_options as Array<[number, string]> : [];
		const right = Array.isArray(game.right_options) ? game.right_options as Array<[number, string]> : [];
		const matches = Array.isArray(answer.matches) ? answer.matches as number[] : [];
		return <div className="worked-demo demo-matches">{left.map((item, index) => { const target = right[matches[index]]; return target && index < stage ? <div className="demo-equation" key={`${item[0]}-${item[1]}`}><strong>{item[0]} {unitName(item[1])}</strong><span aria-hidden="true">→</span><strong>{target[0]} {unitName(target[1])}</strong></div> : null; })}</div>;
	}
	if (kind === "analog_clock") {
		const hour = Number(answer.hour), minute = Number(answer.minute);
		return <div className="worked-demo demo-clock"><AnalogueClock hour={hour} minute={stage > 1 ? minute : 0} />{stage > 1 && <strong className="answer-chip">{clockText(hour, minute)}</strong>}</div>;
	}
	if (kind === "time_conversion") {
		const sourceHour = Number(game.source_hour), sourceMinute = Number(game.source_minute), hour24 = Number(answer.hour24);
		return <div className="worked-demo demo-transform"><TimeBadge label={game.period === "am" ? "පෙ.ව." : "ප.ව."} hour={sourceHour} minute={sourceMinute} /><span className={stage > 1 ? "demo-arrow revealed" : "demo-arrow"} aria-hidden="true">→</span>{stage > 1 && <TimeBadge label="පැය 24" hour={hour24} minute={Number(answer.minute)} />}</div>;
	}
	if (kind === "elapsed_time") {
		return <div className="worked-demo"><div className="demo-route"><TimeBadge label="ආරම්භය" hour={Number(game.start_hour)} minute={Number(game.start_minute)} /><div className="jump-track">{stage > 0 && <span>+ {Number(answer.hours)} පැය</span>}{stage > 1 && <span>+ {Number(answer.minutes)} මිනිත්තු</span>}</div><TimeBadge label="අවසානය" hour={Number(game.end_hour)} minute={Number(game.end_minute)} /></div>{stage > 1 && <strong className="answer-chip">{Number(answer.hours)} පැය {Number(answer.minutes)} මිනිත්තු</strong>}</div>;
	}
	const operation = game.operation === "add" ? "+" : "−";
	return <div className="worked-demo demo-arithmetic"><TimeTable game={game} />{stage > 0 && <div className="regroup-visual"><span>60 මිනිත්තු</span><span aria-hidden="true">⇄</span><span>පැය 1</span></div>}{stage > 1 && <strong className="answer-chip">{operation} → {Number(answer.hours)} පැය {Number(answer.minutes)} මිනිත්තු</strong>}</div>;
}

function TimeSupport({ support, actions, onAction, onComplete }: { support: SupportView; actions: number; onAction(): void; onComplete(): void }) {
	const manifest = support.game_manifest as { required_actions?: number; worked_example?: WorkedExample };
	const required = Number(manifest.required_actions ?? 1), steps = manifest.worked_example?.steps_si ?? support.body_si;
	return <div className="time-support"><p className="support-type">{support.title_si}</p><h2>{manifest.worked_example?.prompt_si}</h2><TimeWorkedDemo example={manifest.worked_example} stage={actions} /><ol>{steps.map((text, index) => <li className={index < actions ? "done" : ""} key={text}>{text}</li>)}</ol><button className="time-primary" onClick={actions < required ? onAction : onComplete}>{actions < required ? "ඊළඟ පියවර" : "දැන් මම කරමි"}</button></div>;
}
