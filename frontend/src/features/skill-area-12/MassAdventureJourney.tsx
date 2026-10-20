// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ConstructedResponse, ExperimentCondition, MassAdventureWorkedExample, PresentationManifest, SupportView } from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import { adaptiveGameProgressStage, AdventureProgress } from "../mobile-learning-flow/AdventureProgress";
import { AdventureBackButton, SuccessCelebration } from "../mobile-learning-flow/AdventureShared";
import { balanceDifference, balanceDirection, canonicalMassArithmetic, denominationCounts, formatMass, splitMass, type MassArithmeticResponse } from "./massLogic";
import { MASS_GAMES, MASS_SKILLS } from "./manifest";
import "./mass-adventure.css";

type Step = "chapters" | "question" | "support" | "withdrawing" | "feedback" | "result";
type Evidence = { correction?: boolean; exchange?: boolean; overshoot?: boolean };

export function MassAdventureJourney({ api, learnerId, condition, reducedMotion, onBack, onFailure }: {
	api: Pick<LearningFlowClient, "open" | "answerBefore" | "completeSupport" | "withdrawSupport" | "presentAfter" | "answerAfter">;
	learnerId: string; condition: ExperimentCondition; reducedMotion: boolean; onBack(): void; onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("chapters"), [skillId, setSkillId] = useState<string | null>(null), [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null), [support, setSupport] = useState<SupportView | null>(null), [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false), [feedbackColumn, setFeedbackColumn] = useState<string | null>(null), [busy, setBusy] = useState(false), [supportStage, setSupportStage] = useState(0);
	const [completed, setCompleted] = useState<string[]>([]), [startedAt, setStartedAt] = useState(Date.now()), [moves, setMoves] = useState(0), [corrections, setCorrections] = useState(0), [exchanges, setExchanges] = useState(0), [overshoots, setOvershoots] = useState(0);
	const [pending, setPending] = useState<{ episode: string; support: string; manifest: string } | null>(null); const lock = useRef(false);
	const index = Math.max(0, MASS_SKILLS.findIndex((skill) => skill.id === skillId)); const active = MASS_SKILLS[index];
	const run = useCallback(async <T,>(job: () => Promise<T>) => { setBusy(true); try { return await job(); } catch (error) { onFailure(error); return undefined; } finally { setBusy(false); } }, [onFailure]);
	const reset = useCallback(() => { setResponse(null); setStartedAt(Date.now()); setMoves(0); setCorrections(0); setExchanges(0); setOvershoots(0); }, []);

	useEffect(() => {
		if (step !== "withdrawing" || !pending) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() => api.withdrawSupport(pending.episode, { request_id: crypto.randomUUID(), support_revision_id: pending.support, manifest_revision_id: pending.manifest, all_support_removed: true, answer_revealing_state_cleared: true, input_handlers_cleared: true }, crypto.randomUUID()));
			if (!withdrawn || cancelled) return;
			const next = await run(() => api.presentAfter(pending.episode, crypto.randomUUID()));
			if (!next || cancelled) return;
			setManifest(next.manifest); setSupport(null); setPending(null); reset(); setStep("question");
		})();
		return () => { cancelled = true; };
	}, [api, pending, reset, run, step]);

	const openSkill = async (id: string) => {
		if (lock.current) return; lock.current = true;
		const opened = await run(() => api.open({ learner_id: learnerId, session_id: crypto.randomUUID(), grade: 5, medium: "si", condition, environment: "development", allow_draft: true, area_id: "G5-AREA-MAT-12", atomic_skill_id: id }, crypto.randomUUID()));
		lock.current = false; if (!opened) return;
		setSkillId(id); setEpisodeId(opened.episode_id); setManifest(opened.manifest); setSupport(null); setCorrect(false); reset(); setStep("question");
	};
	const record = (value: ConstructedResponse | null, evidence?: Evidence) => { setResponse(value); setMoves((count) => count + 1); if (evidence?.correction) setCorrections((count) => count + 1); if (evidence?.exchange) setExchanges((count) => count + 1); if (evidence?.overshoot) setOvershoots((count) => count + 1); };
	const confirm = async () => {
		if (!episodeId || !manifest || !response || lock.current) return; lock.current = true;
		const body = { constructed_response: { ...response, presentation_id: manifest.presentation_id, item_revision_id: manifest.revision_id, interaction_version: "constructed-response-v1" as const }, response_time_ms: reducedMotion ? null : Date.now() - startedAt, interaction_summary: { move_count: moves, correction_count: corrections, first_action_ms: 0, active_time_ms: reducedMotion ? 0 : Date.now() - startedAt, attempt_count: 1, working_cell_count: response.kind === "mass_arithmetic" || response.kind === "mass_market_mission" ? 4 : 0, exchange_count: exchanges, overshoot_count: overshoots } };
		const next = await run(() => manifest.measurement_role === "unsupported_after" ? api.answerAfter(episodeId, body, crypto.randomUUID()) : api.answerBefore(episodeId, body, crypto.randomUUID())); lock.current = false; if (!next) return;
		if (!next.server_score || next.server_score.presentation_id !== manifest.presentation_id || next.server_score.item_revision_id !== manifest.revision_id) { onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST")); return; }
		setCorrect(next.server_score.correct === true); setFeedbackColumn(next.server_score.feedback_column ?? null);
		if (next.status === "support_active" && next.support) { setSupport(next.support); setSupportStage(0); setStep("support"); } else setStep("feedback");
	};
	const finishSupport = async () => {
		if (!episodeId || !support || support.game_manifest.schema_version === "half-set-manifest-v1") return;
		const game = support.game_manifest; if (supportStage < game.required_actions) return;
		const done = await run(() => api.completeSupport(episodeId, { duration_ms: Date.now() - startedAt, steps_viewed: Math.max(1, supportStage), manifest_revision_id: game.revision_id, interaction_summary: { completed: true, renderer_id: game.renderer_id, parallel_example_id: game.parallel_example_id, support_actions: supportStage } }, crypto.randomUUID()));
		if (!done) return; setPending({ episode: episodeId, support: support.revision_id, manifest: game.revision_id }); setSupport(null); setResponse(null); setStep("withdrawing");
	};
	const advance = () => {
		if (!skillId) return; if (!correct) { void openSkill(skillId); return; }
		const nextDone = completed.includes(skillId) ? completed : [...completed, skillId]; setCompleted(nextDone);
		if (index < 4) void openSkill(MASS_SKILLS[index + 1].id); else setStep(nextDone.length === 5 ? "result" : "chapters");
	};

	return <main className="mass-adventure" data-reduced-motion={reducedMotion || undefined}>
		<header className="mass-header"><AdventureBackButton onClick={step === "chapters" ? onBack : () => setStep("chapters")} /><h1>බර මැනීම</h1></header>
		{step === "chapters" ? <section className="mass-game-list" aria-label="බර මැනීමේ ක්‍රීඩා">{MASS_GAMES.map((game) => <button className="mass-game-card" key={game.id} onClick={() => { const first = MASS_SKILLS.find((skill) => skill.chapter === game.id); if (first) void openSkill(first.id); }}><img src={game.asset} alt="" /><span><strong>{game.title}</strong><small>{game.challengeLabel} · {game.difficulty}</small></span></button>)}</section> : <section className="mass-play">
			<AdventureProgress stage={adaptiveGameProgressStage(step, manifest?.measurement_role)} activityCount={5} currentActivity={index + 1} completedActivities={completed.length} />
			<p className="mass-position">ක්‍රියාකාරකම {index + 1}/5 · {active?.name}</p>
			{step === "question" && manifest?.game && <><h2>{manifest.prompt_si}</h2><MassActivity key={manifest.revision_id} game={manifest.game as Record<string, unknown>} onResponse={record} /><button className="mass-primary" disabled={busy || !response} onClick={confirm}>තහවුරු කරන්න</button></>}
			{step === "support" && support && <MassSupport support={support} stage={supportStage} onNext={() => setSupportStage((value) => value + 1)} onComplete={finishSupport} />}
			{step === "withdrawing" && <p role="status">පිළිතුරු සහිත සහාය ඉවත් කර නව ප්‍රශ්නය සූදානම් කරමින්…</p>}
			{step === "feedback" && <section className="mass-feedback"><h2>{correct ? "ක්‍රියාකාරකම සම්පූර්ණයි!" : `${feedbackName(feedbackColumn)} නැවත බලමු.`}</h2><button className="mass-primary" onClick={advance}>{correct ? index === 4 ? "අවසන් කරන්න" : "ඊළඟ ක්‍රියාකාරකම" : "නැවත උත්සාහ කරන්න"}</button></section>}
			{step === "result" && <section className="mass-feedback"><SuccessCelebration /><h2>බර මැනීමේ ක්‍රියාකාරකම් 5ම සම්පූර්ණයි!</h2><button className="mass-primary" onClick={() => setStep("chapters")}>ක්‍රීඩා බලන්න</button></section>}
		</section>}
	</main>;
}

function feedbackName(value: string | null) { return ({ instrument: "තරාදිය", balance: "සමබරතාව", conversion: "1000 g කාණ්ඩ", kilograms: "kg තීරුව", grams: "g තීරුව", delivery: "බෙදාහැරීම" } as Record<string, string>)[value ?? ""] ?? "ගණනය"; }

export function MassActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: Evidence): void }) {
	const kind = String(game.response_kind);
	if (kind === "mass_instrument") return <InstrumentActivity game={game} onResponse={onResponse} />;
	if (kind === "mass_balance") return <BalanceActivity game={game} onResponse={onResponse} />;
	if (kind === "mass_conversion") return <MassTransferMachine game={game} onResponse={onResponse} />;
	if (kind === "mass_arithmetic") return <MassWorkingTable game={game} onResponse={onResponse} />;
	return <MarketMission game={game} onResponse={onResponse} />;
}

const INSTRUMENT_META: Record<string, { label: string; placement: string }> = {
	two_pan_balance: { label: "තැටි දෙකේ තරාදිය", placement: "pan" }, spring_balance: { label: "දුනු තරාදිය", placement: "hook" }, dial_scale: { label: "කටු තරාදිය", placement: "tray" }, digital_scale: { label: "ඩිජිටල් තරාදිය", placement: "platform" }, platform_scale: { label: "ඉලෙක්ට්‍රොනික වේදිකා තරාදිය", placement: "platform" },
};
const OBJECT_LABELS: Record<string, string> = { "hanging-bag": "එල්ලා බර කරන බෑගය", "market-crate": "වෙළඳ පෙට්ටිය", "flour-bowl": "පිටි බඳුන", "small-parcel": "කුඩා පාර්සලය", "sealed-package": "මුද්‍රිත පැකේජය" };

function InstrumentActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: Evidence): void }) {
	const objectId = String(game.object_id), instruments = Array.isArray(game.instrument_types) ? game.instrument_types.map(String) : []; const [selected, setSelected] = useState<string | null>(null); const [trace, setTrace] = useState<string[]>([]);
	const place = (instrument: string) => { const placement = INSTRUMENT_META[instrument]?.placement ?? "platform"; const nextTrace = [...trace, `place:${objectId}:${instrument}:${placement}`]; setSelected(instrument); setTrace(nextTrace); onResponse({ kind: "mass_instrument", object_id: objectId, instrument_type: instrument, placement, interaction_trace: nextTrace }, { correction: trace.length > 0 }); };
	return <div className="instrument-workshop"><button className="weigh-object" draggable onDragStart={(event) => event.dataTransfer.setData("text/plain", objectId)} aria-label={`${OBJECT_LABELS[objectId] ?? objectId} තරාදියකට ගෙන යන්න`}><img src={objectId.includes("crate") ? "/curriculum/game/G5-AREA-MAT-12/market-produce-crate.png" : "/curriculum/game/G5-AREA-MAT-12/weighing-parcel.png"} alt="" /><strong>{OBJECT_LABELS[objectId] ?? objectId}</strong></button><div className="instrument-grid">{instruments.map((instrument) => <button className={selected === instrument ? "selected" : ""} key={instrument} onClick={() => place(instrument)} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); place(instrument); }} aria-pressed={selected === instrument}><InstrumentIcon type={instrument} /><strong>{INSTRUMENT_META[instrument]?.label ?? instrument}</strong></button>)}</div></div>;
}

export function InstrumentIcon({ type }: { type: string }) {
	if (type === "spring_balance") return <span className="instrument-icon spring" aria-hidden="true"><i /><b>0 g</b></span>;
	if (type === "two_pan_balance") return <span className="instrument-icon mini-balance" aria-hidden="true"><i /><i /><b /></span>;
	if (type === "dial_scale") return <span className="instrument-icon dial" aria-hidden="true"><i /><b>g</b></span>;
	if (type === "digital_scale") return <span className="instrument-icon digital" aria-hidden="true"><i>0 g</i></span>;
	return <span className="instrument-icon platform" aria-hidden="true"><i /><b>0 kg</b></span>;
}

export function BalanceScale({ targetMassG, selectedMassesG, onMassDrop, onRemoveLast }: { targetMassG: number; selectedMassesG: number[]; onMassDrop?(value: number): void; onRemoveLast?(): void }) {
	const difference = balanceDifference(targetMassG, selectedMassesG); const direction = balanceDirection(targetMassG, selectedMassesG); const tilt = Math.max(-8, Math.min(8, (targetMassG - (targetMassG + difference)) / Math.max(targetMassG, 1) * 16));
	const status = direction === "balanced" ? "තරාදිය සමබරයි" : direction === "left_heavier" ? "වස්තුව ඇති වම් පැත්ත බර වැඩියි" : "සම්මත බර ඇති දකුණු පැත්ත බර වැඩියි";
	return <figure className={`balance-scale ${direction}`} aria-label={status}><div className="balance-readout" role="status">{status}</div><div className="balance-beam" style={{ transform: `rotate(${tilt}deg)` }}><div className="pan left-pan"><img src="/curriculum/game/G5-AREA-MAT-12/market-produce-crate.png" alt="" /><span>නොදන්නා බර</span></div><button className="pan right-pan" onClick={onRemoveLast} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const value = Number(event.dataTransfer.getData("text/mass")); if (value) onMassDrop?.(value); }} aria-label="සම්මත බර තැටිය. අවසන් බර ඉවත් කිරීමට තට්ටු කරන්න"><div>{taggedValues(selectedMassesG).map(({ value, key }) => <StandardMass value={value} key={key} compact />)}</div><span>{formatMass(selectedMassesG.reduce((sum, value) => sum + value, 0))}</span></button></div><div className="balance-support"><i /></div></figure>;
}

function BalanceActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: Evidence): void }) {
	const target = Number(game.target_mass_g), available = Array.isArray(game.available_masses_g) ? game.available_masses_g.map(Number) : []; const [selected, setSelected] = useState<number[]>([]);
	const emit = (next: number[], correction = false) => { const total = next.reduce((sum, value) => sum + value, 0), difference = total - target; setSelected(next); onResponse({ kind: "mass_balance", target_mass_g: target, selected_mass_denominations_g: next, denomination_counts: denominationCounts(next), selected_total_g: total, balance_difference_g: difference, balanced: difference === 0 }, { correction, overshoot: difference > 0 }); };
	return <div className="balance-workspace"><BalanceScale targetMassG={target} selectedMassesG={selected} onMassDrop={(value) => emit([...selected, value])} onRemoveLast={() => selected.length && emit(selected.slice(0, -1), true)} /><MassBank masses={available} onAdd={(value) => emit([...selected, value])} /><button className="mass-secondary" disabled={!selected.length} onClick={() => emit(selected.slice(0, -1), true)}>අවසන් බර ඉවත් කරන්න</button></div>;
}

function StandardMass({ value, compact = false }: { value: number; compact?: boolean }) { return <span className={`standard-mass ${value >= 1000 ? "kilogram" : "gram"} ${compact ? "compact" : ""}`} role="img" aria-label={value >= 1000 ? `${value / 1000} කිලෝග්‍රෑම් බර` : `${value} ග්‍රෑම් බර`}>{value >= 1000 ? `${value / 1000} kg` : `${value} g`}</span>; }
function MassBank({ masses, onAdd }: { masses: number[]; onAdd(value: number): void }) { return <fieldset className="mass-bank"><legend>සම්මත බර</legend>{masses.map((value) => <button key={value} draggable onDragStart={(event) => event.dataTransfer.setData("text/mass", String(value))} onClick={() => onAdd(value)} aria-label={`${value >= 1000 ? `${value / 1000} කිලෝග්‍රෑම්` : `${value} ග්‍රෑම්`} තැටියට දමන්න`}><StandardMass value={value} /></button>)}</fieldset>; }

function MassTransferMachine({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: Evidence): void }) {
	const total = Number(game.source_total_g), complete = Math.floor(total / 1000); const [exchanges, setExchanges] = useState(0); const remaining = total - exchanges * 1000;
	const transfer = () => { const next = Math.min(complete, exchanges + 1); setExchanges(next); onResponse({ kind: "mass_conversion", source_kilograms: Number(game.source_kilograms), source_grams: Number(game.source_grams), source_total_g: total, result_kilograms: next, result_grams: total - next * 1000, exchange_count: next }, { exchange: true }); };
	const groups = Array.from({ length: complete }, (_, index) => `group-${index + 1}`); const kilograms = Array.from({ length: exchanges }, (_, index) => `kg-${index + 1}`);
	return <div className="mass-machine"><div className="gram-chamber"><span>g කුටිය</span><strong>{remaining} g</strong><div className="mass-groups">{groups.map((group, index) => <i className={index < exchanges ? "moved" : ""} key={group}>1000 g</i>)}</div></div><button className="exchange-arrow" disabled={exchanges >= complete} onClick={transfer}>1000 g → 1 kg</button><div className="kg-blocks" role="img" aria-label={`කිලෝග්‍රෑම් කොටස් ${exchanges}`}>{kilograms.map((key) => <StandardMass value={1000} key={key} />)}<strong>{exchanges} kg</strong></div></div>;
}

type MassField = "gramWork" | "exchange" | "resultKg" | "resultG";
export function MassWorkingTable({ game, onResponse, demo, demoStage = 4 }: { game: Record<string, unknown>; onResponse?(response: ConstructedResponse | null, evidence?: Evidence): void; demo?: MassArithmeticResponse; demoStage?: number }) {
	const operation = String(game.operation) as "add" | "subtract"; const leftKg = Number(game.left_kilograms), leftG = Number(game.left_grams), rightKg = Number(game.right_kilograms), rightG = Number(game.right_grams);
	const [active, setActive] = useState<MassField>("gramWork"), [values, setValues] = useState<Record<MassField, number | null>>({ gramWork: null, exchange: null, resultKg: null, resultG: null }), [order, setOrder] = useState<MassField[]>([]);
	const display = (field: MassField) => { if (!demo) return values[field]; const revealAt: Record<MassField, number> = { gramWork: 1, exchange: 2, resultG: 3, resultKg: 4 }; if (demoStage < revealAt[field]) return null; return ({ gramWork: demo.gram_subtotal_or_adjustment, exchange: demo.carried_or_borrowed_kilograms, resultKg: demo.result_kilograms, resultG: demo.result_grams })[field]; };
	const emit = (next: Record<MassField, number | null>, nextOrder: MassField[], exchange = false) => { setValues(next); setOrder(nextOrder); if (!onResponse || Object.values(next).some((value) => value === null)) return onResponse?.(null, { exchange }); const canonical = canonicalMassArithmetic(operation, leftKg, leftG, rightKg, rightG); const stepByField: Record<MassField, string> = { gramWork: operation === "add" ? `g:${leftG}+${rightG}=${next.gramWork}` : `g:${next.gramWork}-${rightG}=${next.resultG}`, exchange: operation === "add" ? `carry:${next.exchange}` : `borrow:${next.exchange}`, resultG: operation === "add" ? `g-result:${next.resultG}` : `adjust:${leftKg}->${leftKg - Number(next.exchange)}:${leftG}->${next.gramWork}`, resultKg: operation === "add" ? `kg:${leftKg}+${rightKg}+${next.exchange}=${next.resultKg}` : `kg:${leftKg - Number(next.exchange)}-${rightKg}=${next.resultKg}` }; let steps = nextOrder.map((field) => stepByField[field]); if (operation === "subtract" && nextOrder.join() === "exchange,gramWork,resultG,resultKg") steps = [stepByField.exchange, stepByField.resultG, stepByField.gramWork, stepByField.resultKg]; onResponse({ ...canonical, gram_subtotal_or_adjustment: Number(next.gramWork), carried_or_borrowed_kilograms: Number(next.exchange), exchange_used: Number(next.exchange) > 0, working_steps: steps, result_kilograms: Number(next.resultKg), result_grams: Number(next.resultG) }, { exchange }); };
	const write = (digit: number, clear = false) => { if (demo) return; const next = { ...values, [active]: clear ? null : Number(`${values[active] ?? ""}${digit}`.slice(-4)) }; const nextOrder: MassField[] = clear ? order.filter((field) => field !== active) : order.includes(active) ? order : [...order, active]; emit(next, nextOrder); };
	return <fieldset className="mass-working" onKeyDown={(event) => { if (/^[0-9]$/.test(event.key)) write(Number(event.key)); if (event.key === "Backspace") write(0, true); }}><legend className="sr-only">කිලෝග්‍රෑම් සහ ග්‍රෑම් ලිඛිත වගුව</legend><table className="mass-table"><thead><tr><th>ක්‍රියාව</th><th>kg</th><th>g</th></tr></thead><tbody><tr><th>පළමු බර</th><td>{leftKg}</td><td>{String(leftG).padStart(3, "0")}</td></tr><tr><th>{operation === "add" ? "+" : "−"} දෙවන බර</th><td>{rightKg}</td><td>{String(rightG).padStart(3, "0")}</td></tr><tr className="exchange-row"><th>හුවමාරුව</th><td><MassCell label="ගෙන ගිය හෝ ණයට ගත් කිලෝග්‍රෑම්" field="exchange" active={active} value={display("exchange")} select={setActive} /></td><td><MassCell label="ග්‍රෑම් එකතුව හෝ සකස් කළ අගය" field="gramWork" active={active} value={display("gramWork")} select={setActive} /></td></tr><tr className="answer-row"><th>පිළිතුර</th><td><MassCell label="අවසාන කිලෝග්‍රෑම්" field="resultKg" active={active} value={display("resultKg")} select={setActive} /></td><td><MassCell label="අවසාන ග්‍රෑම්" field="resultG" active={active} value={display("resultG")} select={setActive} threeDigits /></td></tr></tbody></table>{!demo && <><button className="exchange-control" onClick={() => { const next = { ...values, exchange: 1 }; const nextOrder: MassField[] = order.includes("exchange") ? order : [...order, "exchange"]; emit(next, nextOrder, true); setActive("gramWork"); }}>1000 g ⇄ 1 kg</button><NumberPad onDigit={write} onClear={() => write(0, true)} /><div className="field-navigation">{(["gramWork", "exchange", "resultG", "resultKg"] as MassField[]).map((field) => <button aria-pressed={active === field} key={field} onClick={() => setActive(field)}>{({ gramWork: "g වැඩ", exchange: "හුවමාරුව", resultG: "පිළිතුරු g", resultKg: "පිළිතුරු kg" })[field]}</button>)}</div></>}<p className="exchange-note">1000 g = 1 kg</p></fieldset>;
}

function MassCell({ label, field, active, value, select, threeDigits }: { label: string; field: MassField; active: MassField; value: number | null; select(field: MassField): void; threeDigits?: boolean }) { return <button className={`mass-cell ${active === field ? "selected" : ""}`} style={{ minHeight: 48, minWidth: 48 }} aria-label={label} aria-pressed={active === field} onClick={() => select(field)}>{value === null ? "?" : threeDigits ? String(value).padStart(3, "0") : value}</button>; }
function NumberPad({ onDigit, onClear }: { onDigit(value: number): void; onClear(): void }) { return <fieldset className="mass-keypad"><legend className="sr-only">අංක යතුරු පුවරුව</legend>{[1,2,3,4,5,6,7,8,9,0].map((number) => <button aria-label={`අංක ${number}`} key={number} onClick={() => onDigit(number)}>{number}</button>)}<button aria-label="තෝරාගත් කොටුව හිස් කරන්න" onClick={onClear}>⌫</button></fieldset>; }

function MarketMission({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: Evidence): void }) {
	const items = Array.isArray(game.item_ids) ? game.item_ids.map(String) : [], itemMasses = Array.isArray(game.item_masses_g) ? game.item_masses_g.map(Number) : [], available = Array.isArray(game.available_masses_g) ? game.available_masses_g.map(Number) : []; const total = itemMasses.reduce((sum, value) => sum + value, 0), capacity = Number(game.cart_capacity_g); const [selected, setSelected] = useState<number[]>([]); const [working, setWorking] = useState<MassArithmeticResponse | null>(null);
	const emit = (next: number[], nextWorking = working, correction = false) => { setSelected(next); setWorking(nextWorking); if (!nextWorking) return onResponse(null, { correction }); onResponse({ kind: "mass_market_mission", mission_id: String(game.mission_id), selected_items: items, item_masses_g: itemMasses, selected_standard_masses_g: next, operation: "add", working_steps: nextWorking.working_steps, total_mass_g: nextWorking.result_kilograms * 1000 + nextWorking.result_grams, result_kilograms: nextWorking.result_kilograms, result_grams: nextWorking.result_grams, remaining_capacity_g: capacity - (nextWorking.result_kilograms * 1000 + nextWorking.result_grams), contextual_answer: `load:${nextWorking.result_kilograms * 1000 + nextWorking.result_grams}:remaining:${capacity - (nextWorking.result_kilograms * 1000 + nextWorking.result_grams)}` }, { correction, overshoot: next.reduce((sum, value) => sum + value, 0) > total }); };
	const first = splitMass(itemMasses[0] ?? 0), second = splitMass(itemMasses[1] ?? 0);
	return <div className="market-mission"><div className="market-load"><img src="/curriculum/game/G5-AREA-MAT-12/market-produce-crate.png" alt="" /><strong>{formatMass(itemMasses[0] ?? 0)}</strong><img src="/curriculum/game/G5-AREA-MAT-12/weighing-parcel.png" alt="" /><strong>{formatMass(itemMasses[1] ?? 0)}</strong></div><p>රථ ධාරිතාව: {formatMass(capacity)} · තරාදි එකතුව: {formatMass(selected.reduce((sum, value) => sum + value, 0))}</p><MassBank masses={available} onAdd={(value) => emit([...selected, value])} /><button className="mass-secondary" disabled={!selected.length} onClick={() => emit(selected.slice(0, -1), working, true)}>අවසන් බර ඉවත් කරන්න</button><MassWorkingTable game={{ operation: "add", left_kilograms: first.kilograms, left_grams: first.grams, right_kilograms: second.kilograms, right_grams: second.grams }} onResponse={(value, evidence) => emit(selected, value?.kind === "mass_arithmetic" ? value : null, Boolean(evidence?.exchange))} /><img className="market-cart" src="/curriculum/game/G5-AREA-MAT-12/market-delivery-cart.png" alt="" /></div>;
}

function MassSupport({ support, stage, onNext, onComplete }: { support: SupportView; stage: number; onNext(): void; onComplete(): void }) {
	if (support.game_manifest.schema_version !== "mass-adventure-support-v1") return null; const manifest = support.game_manifest; const example = manifest.worked_example;
	return <section className="mass-support"><p className="support-type">{support.title_si}</p><h2>{example.prompt_si}</h2>{manifest.scaffold_type === "visual_guidance" ? <MassVisualCue game={example.game as Record<string, unknown>} /> : <MassWorkedDemo example={example} stage={stage} />}<ol>{example.steps_si.map((text, index) => <li className={index < stage ? "done" : ""} key={text}>{text}</li>)}</ol><button className="mass-primary" onClick={stage < manifest.required_actions ? onNext : onComplete}>{stage < manifest.required_actions ? "ඊළඟ පියවර" : "දැන් මම කරමි"}</button></section>;
}

function MassVisualCue({ game }: { game: Record<string, unknown> }) {
	const kind = String(game.response_kind);
	if (kind === "mass_instrument") return <div className="mass-visual-cue"><strong>{OBJECT_LABELS[String(game.object_id)]}</strong><span>→</span><strong>{instrumentFeature(String(game.object_id))}</strong></div>;
	if (kind === "mass_balance") return <div className="mass-visual-cue"><BalanceScale targetMassG={Number(game.target_mass_g)} selectedMassesG={[]} /></div>;
	if (kind === "mass_arithmetic") return <div className="mass-visual-cue"><table className="mass-table"><thead><tr><th>ක්‍රියාව</th><th>kg</th><th className="cue-focus">g</th></tr></thead><tbody><tr><th>පළමු බර</th><td>{String(game.left_kilograms)}</td><td className="cue-focus">{String(game.left_grams).padStart(3, "0")}</td></tr><tr><th>{game.operation === "add" ? "+" : "−"} දෙවන බර</th><td>{String(game.right_kilograms)}</td><td className="cue-focus">{String(game.right_grams).padStart(3, "0")}</td></tr></tbody></table></div>;
	return <div className="mass-visual-cue"><div className="mass-groups"><i>1000 g</i><i>1000 g</i></div><strong>{kind === "mass_market_mission" ? "භාණ්ඩ → kg/g වගුව" : "1000 g → 1 kg"}</strong></div>;
}

export function MassWorkedDemo({ example, stage }: { example: MassAdventureWorkedExample; stage: number }) {
	const response = example.correct_response; const game = example.game as Record<string, unknown>; if (!response) return null;
	if (response.kind === "mass_instrument") return <div className="mass-worked"><strong>{OBJECT_LABELS[response.object_id]}</strong><span>→</span><InstrumentIcon type={response.instrument_type} /><strong>{INSTRUMENT_META[response.instrument_type]?.label}</strong></div>;
	if (response.kind === "mass_balance") { const visible = response.selected_mass_denominations_g.slice(0, stage); return <div className="mass-worked"><BalanceScale targetMassG={response.target_mass_g} selectedMassesG={visible} />{stage >= example.steps_si.length && <><strong>{formatMass(response.selected_total_g)}</strong><small>වෙනත් නිවැරදි බර සංයෝජනද ඇත.</small></>}</div>; }
	if (response.kind === "mass_conversion") { const groups = Array.from({ length: Math.min(stage, response.exchange_count) }, (_, index) => `worked-${index + 1}`); return <div className="mass-worked"><div className="mass-groups">{groups.map((group) => <i key={group}>1000 g → 1 kg</i>)}</div>{stage >= 3 && <strong>{response.result_kilograms} kg {response.result_grams} g</strong>}</div>; }
	if (response.kind === "mass_arithmetic") return <div className="mass-worked"><MassWorkingTable game={game} demo={response} demoStage={stage} />{stage >= 4 && <strong>{response.result_kilograms} kg {String(response.result_grams).padStart(3, "0")} g</strong>}</div>;
	if (response.kind === "mass_market_mission") return <div className="mass-worked"><div className="market-load"><img src="/curriculum/game/G5-AREA-MAT-12/market-produce-crate.png" alt="" /><span>{formatMass(response.item_masses_g[0] ?? 0)}</span><img src="/curriculum/game/G5-AREA-MAT-12/weighing-parcel.png" alt="" /><span>{formatMass(response.item_masses_g[1] ?? 0)}</span></div>{stage >= 3 && <strong>{formatMass(response.total_mass_g)}</strong>}{stage >= 4 && <small>ඉතිරි ධාරිතාව: {formatMass(response.remaining_capacity_g)}</small>}</div>;
	return null;
}

function taggedValues(values: number[]) { const seen = new Map<number, number>(); return values.map((value) => { const occurrence = (seen.get(value) ?? 0) + 1; seen.set(value, occurrence); return { value, key: `${value}-${occurrence}` }; }); }
function instrumentFeature(objectId: string) { return ({ "hanging-bag": "එල්ලීමට හුක්කක් සොයන්න", "market-crate": "විශාල වේදිකාවක් සොයන්න", "flour-bowl": "බඳුන තැබිය හැකි තැටියක් සොයන්න", "small-parcel": "පාර්සලය තැබිය හැකි තැටියක් සොයන්න", "sealed-package": "සෘජු කියවීමක් ඇති වේදිකාවක් සොයන්න" } as Record<string, string>)[objectId] ?? "වස්තුව තැබිය හැකි කොටස සොයන්න"; }
