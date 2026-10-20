// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
	ConstructedResponse,
	ExperimentCondition,
	MoneyAdventureWorkedExample,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import {
	adaptiveGameProgressStage,
	AdventureProgress,
} from "../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../mobile-learning-flow/AdventureShared";
import {
	canonicalMoneyArithmetic,
	calculateLineTotals,
	DENOMINATIONS,
	denominationCounts,
	denominationTotal,
	formatMoney,
	splitMoney,
	type MoneyArithmeticResponse,
} from "./moneyLogic";
import { MONEY_GAMES, MONEY_SKILLS } from "./manifest";
import "./money-adventure.css";

type Step = "chapters" | "question" | "support" | "withdrawing" | "feedback" | "result";

export function MoneyAdventureJourney({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: {
	api: Pick<LearningFlowClient, "open" | "answerBefore" | "completeSupport" | "withdrawSupport" | "presentAfter" | "answerAfter">;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("chapters");
	const [skillId, setSkillId] = useState<string | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
	const [feedbackColumn, setFeedbackColumn] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [supportStage, setSupportStage] = useState(0);
	const [completed, setCompleted] = useState<string[]>([]);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [moves, setMoves] = useState(0);
	const [corrections, setCorrections] = useState(0);
	const [exchanges, setExchanges] = useState(0);
	const [overshoots, setOvershoots] = useState(0);
	const [pending, setPending] = useState<{ episode: string; support: string; manifest: string } | null>(null);
	const lock = useRef(false);
	const index = Math.max(0, MONEY_SKILLS.findIndex((skill) => skill.id === skillId));
	const active = MONEY_SKILLS[index];
	const activeGameIndex = MONEY_GAMES.findIndex((game) => game.id === active?.chapter);

	const run = useCallback(async <T,>(job: () => Promise<T>) => {
		setBusy(true);
		try { return await job(); }
		catch (error) { onFailure(error); return undefined; }
		finally { setBusy(false); }
	}, [onFailure]);
	const reset = useCallback(() => {
		setResponse(null); setStartedAt(Date.now()); setMoves(0); setCorrections(0); setExchanges(0); setOvershoots(0);
	}, []);

	useEffect(() => {
		if (step !== "withdrawing" || !pending) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() => api.withdrawSupport(pending.episode, {
				request_id: crypto.randomUUID(), support_revision_id: pending.support,
				manifest_revision_id: pending.manifest, all_support_removed: true,
				answer_revealing_state_cleared: true, input_handlers_cleared: true,
			}, crypto.randomUUID()));
			if (!withdrawn || cancelled) return;
			const next = await run(() => api.presentAfter(pending.episode, crypto.randomUUID()));
			if (!next || cancelled) return;
			setManifest(next.manifest); setSupport(null); setPending(null); reset(); setStep("question");
		})();
		return () => { cancelled = true; };
	}, [api, pending, reset, run, step]);

	const openSkill = async (id: string) => {
		if (lock.current) return;
		lock.current = true;
		const opened = await run(() => api.open({
			learner_id: learnerId, session_id: crypto.randomUUID(), grade: 5, medium: "si",
			condition, environment: "development", allow_draft: true,
			area_id: "G5-AREA-MAT-10", atomic_skill_id: id,
		}, crypto.randomUUID()));
		lock.current = false;
		if (!opened) return;
		setSkillId(id); setEpisodeId(opened.episode_id); setManifest(opened.manifest);
		setSupport(null); setCorrect(false); reset(); setStep("question");
	};
	const record = (value: ConstructedResponse | null, evidence?: { correction?: boolean; exchange?: boolean; overshoot?: boolean }) => {
		setResponse(value); setMoves((count) => count + 1);
		if (evidence?.correction) setCorrections((count) => count + 1);
		if (evidence?.exchange) setExchanges((count) => count + 1);
		if (evidence?.overshoot) setOvershoots((count) => count + 1);
	};
	const confirm = async () => {
		if (!episodeId || !manifest || !response || lock.current) return;
		lock.current = true;
		const body = {
			constructed_response: { ...response, presentation_id: manifest.presentation_id, item_revision_id: manifest.revision_id, interaction_version: "constructed-response-v1" as const },
			response_time_ms: reducedMotion ? null : Date.now() - startedAt,
			interaction_summary: {
				move_count: moves, correction_count: corrections, first_action_ms: 0,
				active_time_ms: reducedMotion ? 0 : Date.now() - startedAt, attempt_count: 1,
				working_cell_count: response.kind === "money_arithmetic" ? 4 : response.kind === "shopping_calculation" ? response.line_totals_in_cents.length + 2 : 0,
				exchange_count: exchanges, overshoot_count: overshoots,
			},
		};
		const next = await run(() => manifest.measurement_role === "unsupported_after"
			? api.answerAfter(episodeId, body, crypto.randomUUID())
			: api.answerBefore(episodeId, body, crypto.randomUUID()));
		lock.current = false;
		if (!next) return;
		if (!next.server_score || next.server_score.presentation_id !== manifest.presentation_id || next.server_score.item_revision_id !== manifest.revision_id) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST")); return;
		}
		setCorrect(next.server_score.correct === true);
		setFeedbackColumn(next.server_score.feedback_column ?? null);
		if (next.status === "support_active" && next.support) {
			setSupport(next.support); setSupportStage(0); setStep("support");
		} else setStep("feedback");
	};
	const finishSupport = async () => {
		if (!episodeId || !support || support.game_manifest.schema_version === "half-set-manifest-v1") return;
		const game = support.game_manifest;
		if (supportStage < game.required_actions) return;
		const done = await run(() => api.completeSupport(episodeId, {
			duration_ms: Date.now() - startedAt, steps_viewed: Math.max(1, supportStage),
			manifest_revision_id: game.revision_id,
			interaction_summary: { completed: true, renderer_id: game.renderer_id, parallel_example_id: game.parallel_example_id, support_actions: supportStage },
		}, crypto.randomUUID()));
		if (!done) return;
		setPending({ episode: episodeId, support: support.revision_id, manifest: game.revision_id });
		setSupport(null); setResponse(null); setStep("withdrawing");
	};
	const advance = () => {
		if (!skillId) return;
		if (!correct) { void openSkill(skillId); return; }
		const nextDone = completed.includes(skillId) ? completed : [...completed, skillId];
		setCompleted(nextDone);
		const nextSkill = MONEY_SKILLS[index + 1];
		if (nextSkill?.chapter === active?.chapter) void openSkill(nextSkill.id);
		else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => { if (step === "feedback" && correct) advance(); }, [step, correct]);

	return <main className="money-adventure" data-reduced-motion={reducedMotion || undefined}>
		<header className="money-header">
			<AdventureBackButton onClick={step === "chapters" ? onBack : () => setStep("chapters")} />
			<h1>මුදල්</h1>
		</header>
		{step === "chapters" ? <section className="money-game-list" aria-label="මුදල් ක්‍රීඩා">
			{MONEY_GAMES.map((game) => <button className="money-game-card" key={game.id} onClick={() => {
				const first = MONEY_SKILLS.find((skill) => skill.chapter === game.id); if (first) void openSkill(first.id);
			}}><img src={game.asset} alt="" /><span><strong>{game.title}</strong><small>{game.challengeLabel} · {game.difficulty}</small></span></button>)}
		</section> : <section className="money-play">
			<AdventureProgress stage={adaptiveGameProgressStage(step, manifest?.measurement_role)} activityCount={5} currentActivity={index + 1} completedActivities={completed.length} />
			<p className="money-position">ක්‍රියාකාරකම {index + 1}/5 · {active?.name}</p>
			{step === "question" && manifest?.game && <>
				<h2>{manifest.prompt_si}</h2>
				<MoneyActivity key={manifest.revision_id} game={manifest.game as Record<string, unknown>} onResponse={record} />
				<button className="money-primary" disabled={busy || !response} onClick={confirm}>තහවුරු කරන්න</button>
			</>}
			{step === "support" && support && <MoneySupport support={support} stage={supportStage} onNext={() => setSupportStage((value) => value + 1)} onComplete={finishSupport} />}
			{step === "withdrawing" && <p role="status">පිළිතුරු සහිත සහාය ඉවත් කර නව ප්‍රශ්නය සූදානම් කරමින්…</p>}
			{step === "feedback" && !correct && <section className="money-feedback"><h2>{feedbackName(feedbackColumn)} නැවත බලමු.</h2><button className="money-primary" onClick={advance}>නැවත උත්සාහ කරන්න</button></section>}
			{step === "result" && <GameSuccessScreen gameNumber={activeGameIndex + 1} gameCount={MONEY_GAMES.length} onContinue={() => { const nextGame = MONEY_GAMES[activeGameIndex + 1]; const nextSkill = nextGame && MONEY_SKILLS.find((skill) => skill.chapter === nextGame.id); if (nextSkill) void openSkill(nextSkill.id); else setStep("chapters"); }} />}
		</section>}
	</main>;
}

function feedbackName(value: string | null) {
	return ({ denominations: "කාසි හා නෝට්ටු", total: "දැනට ඇති එකතුව", rupees: "රුපියල් තීරුව", cents: "සත තීරුව", shop: "වෙළඳසැල් පේළි" } as Record<string, string>)[value ?? ""] ?? "ගණනය";
}

function taggedDenominations(ids: string[]) {
	const seen = new Map<string, number>();
	return ids.map((id) => {
		const occurrence = (seen.get(id) ?? 0) + 1;
		seen.set(id, occurrence);
		return { id, key: `${id}-${occurrence}` };
	});
}

export function MoneyActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: { correction?: boolean; exchange?: boolean; overshoot?: boolean }): void }) {
	const kind = String(game.response_kind);
	if (kind === "currency_recognition") return <RecognitionActivity game={game} onResponse={onResponse} />;
	if (kind === "amount_construction") return <CompositionActivity game={game} onResponse={onResponse} />;
	if (kind === "money_arithmetic") return <MoneyWorkingTable game={game} onResponse={onResponse} />;
	return <ShopActivity game={game} onResponse={onResponse} />;
}

function CurrencyToken({ id, compact = false, onClick, selected }: { id: string; compact?: boolean; onClick?(): void; selected?: boolean }) {
	const token = DENOMINATIONS.find((item) => item.id === id);
	if (!token) return null;
	const Element = onClick ? "button" : "span";
	return <Element className={`currency-token ${token.type} ${compact ? "compact" : ""}`} aria-pressed={onClick ? selected : undefined} aria-label={`${token.label} ${token.type === "coin" ? "කාසිය" : "නෝට්ටුව"}`} onClick={onClick}>{token.label}</Element>;
}

function RecognitionActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: { correction?: boolean }): void }) {
	const tokens = Array.isArray(game.tokens) ? game.tokens as Array<{ denomination_id: string }> : [];
	const [selected, setSelected] = useState<string | null>(null);
	const [placed, setPlaced] = useState<Array<{ denomination_id: string; currency_type: "coin" | "note"; value_in_cents: number; ordered_position: number }>>([]);
	const place = (currencyType: "coin" | "note") => {
		if (!selected) return;
		const token = DENOMINATIONS.find((item) => item.id === selected); if (!token) return;
		const next = [...placed.filter((row) => row.denomination_id !== selected), { denomination_id: selected, currency_type: currencyType, value_in_cents: token.cents, ordered_position: placed.length }];
		setPlaced(next); setSelected(null);
		onResponse(next.length === tokens.length ? { kind: "currency_recognition", denomination_id: "all", currency_type: "mixed", value_in_cents: 0, ordered_position: 10, placements: next } : null);
	};
	return <div className="recognition-workspace">
		<p className="money-instruction">මුදල් කොටස තෝරා නිවැරදි තැටියට දමන්න. තැටිය තුළ අගය අනුපිළිවෙළට තබන්න.</p>
		<div className="token-bank">{tokens.filter((token) => !placed.some((row) => row.denomination_id === token.denomination_id)).map((token) => <CurrencyToken key={token.denomination_id} id={token.denomination_id} selected={selected === token.denomination_id} onClick={() => setSelected(token.denomination_id)} />)}</div>
		<div className="money-trays"><button aria-label="තෝරාගත් මුදල් කොටස කාසි තැටියට දමන්න" onClick={() => place("coin")}>කාසි තැටිය</button><button aria-label="තෝරාගත් මුදල් කොටස නෝට්ටු තැටියට දමන්න" onClick={() => place("note")}>නෝට්ටු තැටිය</button></div>
		<div className="placed-money" aria-live="polite">{placed.map((row) => <CurrencyToken compact key={row.denomination_id} id={row.denomination_id} onClick={() => { const next = placed.filter((item) => item.denomination_id !== row.denomination_id).map((item, index) => ({ ...item, ordered_position: index })); setPlaced(next); onResponse(null, { correction: true }); }} />)}</div>
	</div>;
}

function CompositionActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null, evidence?: { correction?: boolean; overshoot?: boolean }): void }) {
	const target = Number(game.target_in_cents);
	const ids = Array.isArray(game.denominations) ? game.denominations.map(String) : [];
	const [selected, setSelected] = useState<string[]>([]);
	const emit = (next: string[], correction = false) => {
		setSelected(next); const total = denominationTotal(next);
		onResponse(next.length ? { kind: "amount_construction", target_in_cents: target, selected_denominations: next, denomination_counts: denominationCounts(next), constructed_total_in_cents: total } : null, { correction, overshoot: total > target });
	};
	const total = denominationTotal(selected);
	return <div className="composition-workspace">
		<div className="purse-target"><img src="/curriculum/game/G5-AREA-MAT-10/money-purse.png" alt="" /><strong>ඉලක්කය: රු. {formatMoney(target)}</strong><span className={total > target ? "is-error" : total === target ? "is-complete" : ""}>දැනට: රු. {formatMoney(total)}</span><div className="purse-overlay">{taggedDenominations(selected).map((token) => <CurrencyToken compact key={token.key} id={token.id} />)}</div></div>
		<div className="token-bank">{ids.map((id) => <CurrencyToken key={id} id={id} onClick={() => emit([...selected, id])} />)}</div>
		<button className="money-secondary" disabled={!selected.length} onClick={() => emit(selected.slice(0, -1), true)}>අවසන් මුදල් කොටස ඉවත් කරන්න</button>
	</div>;
}

type MoneyField = "centWork" | "exchange" | "resultRupees" | "resultCents";
export function MoneyWorkingTable({ game, onResponse, demo, demoStage = 4 }: { game: Record<string, unknown>; onResponse?(response: ConstructedResponse | null, evidence?: { exchange?: boolean }): void; demo?: MoneyArithmeticResponse; demoStage?: number }) {
	const operation = String(game.operation) as "add" | "subtract";
	const left = Number(game.left_amount_in_cents), right = Number(game.right_amount_in_cents);
	const leftParts = splitMoney(left), rightParts = splitMoney(right);
	const [active, setActive] = useState<MoneyField>("centWork");
	const [values, setValues] = useState<Record<MoneyField, number | null>>({ centWork: null, exchange: null, resultRupees: null, resultCents: null });
	const [order, setOrder] = useState<MoneyField[]>([]);
	const expected = demo ?? null;
	const display = (field: MoneyField) => {
		if (!expected) return values[field];
		const revealAt: Record<MoneyField, number> = { centWork: 1, exchange: 2, resultCents: 3, resultRupees: 4 };
		if (demoStage < revealAt[field]) return null;
		return ({ centWork: expected.cent_subtotal_or_adjustment, exchange: expected.carried_or_borrowed_rupees, resultRupees: expected.result_rupees, resultCents: expected.result_cents })[field];
	};
	const emit = (next: Record<MoneyField, number | null>, nextOrder: MoneyField[], exchange = false) => {
		setValues(next); setOrder(nextOrder);
		if (!onResponse || Object.values(next).some((value) => value === null)) return onResponse?.(null, { exchange });
		const canonical = canonicalMoneyArithmetic(operation, left, right);
		const stepByField: Record<MoneyField, string> = {
			centWork: operation === "add" ? `cents:${leftParts.cents}+${rightParts.cents}=${next.centWork}` : `cents:${next.centWork}-${rightParts.cents}=${next.resultCents}`,
			exchange: operation === "add" ? `carry:${next.exchange}` : `borrow:${next.exchange}`,
			resultCents: operation === "add" ? `cents-result:${next.resultCents}` : `adjust:${leftParts.rupees}->${leftParts.rupees - Number(next.exchange)}:${leftParts.cents}->${next.centWork}`,
			resultRupees: operation === "add" ? `rupees:${leftParts.rupees}+${rightParts.rupees}+${next.exchange}=${next.resultRupees}` : `rupees:${leftParts.rupees - Number(next.exchange)}-${rightParts.rupees}=${next.resultRupees}`,
		};
		let steps = nextOrder.map((field) => stepByField[field]);
		if (operation === "subtract" && nextOrder.join() === "exchange,centWork,resultCents,resultRupees") steps = canonical.working_steps.map((step, index) => [stepByField.exchange, stepByField.resultCents, stepByField.centWork, stepByField.resultRupees][index] ?? step);
		onResponse({ ...canonical, cent_subtotal_or_adjustment: Number(next.centWork), carried_or_borrowed_rupees: Number(next.exchange), exchange_used: Number(next.exchange) > 0, result_rupees: Number(next.resultRupees), result_cents: Number(next.resultCents), result_in_cents: Number(next.resultRupees) * 100 + Number(next.resultCents), working_steps: steps }, { exchange });
	};
	const write = (digit: number, clear = false) => {
		if (expected) return;
		const next = { ...values, [active]: clear ? null : Number(`${values[active] ?? ""}${digit}`.slice(-4)) };
		const nextOrder: MoneyField[] = clear ? order.filter((field) => field !== active) : order.includes(active) ? order : [...order, active];
		emit(next, nextOrder);
	};
	return <fieldset className="money-working" onKeyDown={(event) => { if (/^[0-9]$/.test(event.key)) write(Number(event.key)); if (event.key === "Backspace") write(0, true); }}>
		<legend className="sr-only">රුපියල් සහ සත ලිඛිත වගුව</legend>
		<table className="money-table"><thead><tr><th>ක්‍රියාව</th><th>රුපියල්</th><th>සත</th></tr></thead><tbody>
			<tr><th>පළමු මුදල</th><td>{leftParts.rupees}</td><td>{String(leftParts.cents).padStart(2, "0")}</td></tr>
			<tr><th>{operation === "add" ? "+" : "−"} දෙවන මුදල</th><td>{rightParts.rupees}</td><td>{String(rightParts.cents).padStart(2, "0")}</td></tr>
			<tr className="exchange-row"><th>හුවමාරුව</th><td><MoneyCell label="ගෙන ගිය හෝ ණයට ගත් රුපියල්" field="exchange" active={active} value={display("exchange")} select={setActive} /></td><td><MoneyCell label="සත එකතුව හෝ සකස් කළ සත" field="centWork" active={active} value={display("centWork")} select={setActive} /></td></tr>
			<tr className="answer-row"><th>පිළිතුර</th><td><MoneyCell label="අවසාන රුපියල්" field="resultRupees" active={active} value={display("resultRupees")} select={setActive} /></td><td><MoneyCell label="අවසාන සත" field="resultCents" active={active} value={display("resultCents")} select={setActive} twoDigits /></td></tr>
		</tbody></table>
		{!expected && <><button className="exchange-control" onClick={() => { const next = { ...values, exchange: 1 }; const nextOrder: MoneyField[] = order.includes("exchange") ? order : [...order, "exchange"]; emit(next, nextOrder, true); setActive("centWork"); }}>සත 100 ⇄ රුපියල් 1</button><NumberPad onDigit={write} onClear={() => write(0, true)} /><div className="field-navigation">{(["centWork", "exchange", "resultCents", "resultRupees"] as MoneyField[]).map((field) => <button aria-pressed={active === field} key={field} onClick={() => setActive(field)}>{({ centWork: "සත වැඩ", exchange: "හුවමාරුව", resultCents: "පිළිතුරු සත", resultRupees: "පිළිතුරු රුපියල්" })[field]}</button>)}</div></>}
		<p className="exchange-note">සත 100 = රුපියල් 1</p>
	</fieldset>;
}

function MoneyCell({ label, field, active, value, select, twoDigits }: { label: string; field: MoneyField; active: MoneyField; value: number | null; select(field: MoneyField): void; twoDigits?: boolean }) {
	return <button style={{ minWidth: 48, minHeight: 48 }} className={`money-cell ${active === field ? "selected" : ""}`} aria-label={label} aria-pressed={active === field} onClick={() => select(field)}>{value === null ? "?" : twoDigits ? String(value).padStart(2, "0") : value}</button>;
}

function NumberPad({ onDigit, onClear }: { onDigit(value: number): void; onClear(): void }) {
	return <fieldset className="money-keypad"><legend className="sr-only">අංක යතුරු පුවරුව</legend>{[1,2,3,4,5,6,7,8,9,0].map((number) => <button aria-label={`අංක ${number}`} key={number} onClick={() => onDigit(number)}>{number}</button>)}<button aria-label="තෝරාගත් කොටුව හිස් කරන්න" onClick={onClear}>⌫</button></fieldset>;
}

function ShopActivity({ game, onResponse }: { game: Record<string, unknown>; onResponse(response: ConstructedResponse | null): void }) {
	type Product = { product_id: string; name_si: string; unit_price_in_cents: number };
	const products = Array.isArray(game.products) ? game.products as Product[] : [];
	const selected = Array.isArray(game.selected_products) ? game.selected_products.map(String) : [];
	const quantities = Array.isArray(game.quantities) ? game.quantities.map(Number) : [];
	const prices = selected.map((id) => products.find((product) => product.product_id === id)?.unit_price_in_cents ?? 0);
	const fieldNames = [...selected.map((_, index) => `line-${index}`), "total", "change"];
	const [active, setActive] = useState(fieldNames[0] ?? "total");
	const [values, setValues] = useState<Record<string, number | null>>(() => Object.fromEntries(fieldNames.map((field) => [field, null])));
	const [order, setOrder] = useState<string[]>([]);
	const write = (digit: number, clear = false) => {
		const next = { ...values, [active]: clear ? null : Number(`${values[active] ?? ""}${digit}`.slice(-7)) };
		const nextOrder = clear ? order.filter((field) => field !== active) : order.includes(active) ? order : [...order, active];
		setValues(next); setOrder(nextOrder);
		if (Object.values(next).some((value) => value === null)) return onResponse(null);
		const lines = selected.map((_, index) => Number(next[`line-${index}`]));
		const total = Number(next.total), paid = Number(game.amount_paid_in_cents), change = Number(next.change);
		const steps = nextOrder.map((field) => field.startsWith("line-") ? (() => { const index = Number(field.slice(5)); return `line:${selected[index]}:${prices[index]}x${quantities[index]}=${lines[index]}`; })() : field === "total" ? `total:${lines.join("+")}=${total}` : `change:${paid}-${total}=${change}`);
		onResponse({ kind: "shopping_calculation", problem_id: String(game.problem_id), selected_products: selected, quantities, unit_prices_in_cents: prices, line_totals_in_cents: lines, working_steps: steps, total_in_cents: total, amount_paid_in_cents: paid, change_in_cents: change, contextual_answer: `pay:${total}:change:${change}` });
	};
	return <div className="shop-workspace">
		<img className="shop-counter-art" src="/curriculum/game/G5-AREA-MAT-10/shop-counter.png" alt="" />
		<table className="price-table"><thead><tr><th>ද්‍රව්‍යය</th><th>රුපියල්</th><th>සත</th></tr></thead><tbody>{products.map((product) => { const money = splitMoney(product.unit_price_in_cents); return <tr key={product.product_id} className={selected.includes(product.product_id) ? "requested" : ""}><th>{product.name_si}</th><td>{money.rupees}</td><td>{String(money.cents).padStart(2, "0")}</td></tr>; })}</tbody></table>
		<div className="shopping-request">{selected.map((id, index) => <p key={id}><strong>{products.find((product) => product.product_id === id)?.name_si}</strong> × {quantities[index]}</p>)}</div>
		<div className="shop-working">{selected.map((id, index) => <button aria-pressed={active === `line-${index}`} key={id} onClick={() => setActive(`line-${index}`)}>{products.find((product) => product.product_id === id)?.name_si} පේළි එකතුව: {values[`line-${index}`] === null ? "?" : `රු. ${formatMoney(Number(values[`line-${index}`]))}`}</button>)}<button aria-pressed={active === "total"} onClick={() => setActive("total")}>මුළු මිල: {values.total === null ? "?" : `රු. ${formatMoney(Number(values.total))}`}</button><button aria-pressed={active === "change"} onClick={() => setActive("change")}>ඉතිරි මුදල: {values.change === null ? "?" : `රු. ${formatMoney(Number(values.change))}`}</button></div>
		<NumberPad onDigit={write} onClear={() => write(0, true)} />
		<p className="amount-paid">ගෙවූ මුදල: රු. {formatMoney(Number(game.amount_paid_in_cents))}</p>
	</div>;
}

function MoneyVisualCue({ game }: { game: Record<string, unknown> }) {
	const kind = String(game.response_kind);
	if (kind === "currency_recognition") {
		const tokens = Array.isArray(game.tokens)
			? (game.tokens as Array<{ denomination_id: string }>).slice(0, 2)
			: [];
		return <fieldset className="money-visual-cue"><legend className="sr-only">සසඳන මුදල් අගයන් සහ කාසි නෝට්ටු තැටි</legend>
			<div className="placed-money">{tokens.map((token) => <CurrencyToken compact key={token.denomination_id} id={token.denomination_id} />)}</div>
			<div className="money-trays"><span>කාසි තැටිය</span><span>නෝට්ටු තැටිය</span></div>
		</fieldset>;
	}
	if (kind === "amount_construction") {
		return <div className="money-visual-cue purse-target">
			<img src="/curriculum/game/G5-AREA-MAT-10/money-purse.png" alt="" />
			<strong>ඉලක්කය: රු. {formatMoney(Number(game.target_in_cents))}</strong>
			<span>දැනට ඇති එකතුව ඉලක්කයට වඩා අඩුද වැඩිද බලන්න.</span>
		</div>;
	}
	if (kind === "money_arithmetic") {
		const left = splitMoney(Number(game.left_amount_in_cents));
		const right = splitMoney(Number(game.right_amount_in_cents));
		return <div className="money-visual-cue">
			<table className="money-table cue-table"><thead><tr><th>ක්‍රියාව</th><th>රුපියල්</th><th className="cue-focus">සත</th></tr></thead><tbody>
				<tr><th>පළමු මුදල</th><td>{left.rupees}</td><td className="cue-focus">{String(left.cents).padStart(2, "0")}</td></tr>
				<tr><th>{game.operation === "add" ? "+" : "−"} දෙවන මුදල</th><td>{right.rupees}</td><td className="cue-focus">{String(right.cents).padStart(2, "0")}</td></tr>
				<tr className="answer-row"><th>පිළිතුර</th><td>?</td><td className="cue-focus">?</td></tr>
			</tbody></table>
		</div>;
	}
	const products = Array.isArray(game.products)
		? game.products as Array<{ product_id: string; name_si: string; unit_price_in_cents: number }>
		: [];
	const requested = new Set(Array.isArray(game.selected_products) ? game.selected_products.map(String) : []);
	return <fieldset className="money-visual-cue"><legend className="sr-only">ඉල්ලූ භාණ්ඩ මිල පේළි</legend>
		{products.filter((product) => requested.has(product.product_id)).map((product) => <p className="cue-shop-row" key={product.product_id}>
			<strong>{product.name_si}</strong><span>රු. {formatMoney(product.unit_price_in_cents)}</span><span>→ ගණනය පේළිය</span>
		</p>)}
	</fieldset>;
}

function MoneySupport({ support, stage, onNext, onComplete }: { support: SupportView; stage: number; onNext(): void; onComplete(): void }) {
	if (support.game_manifest.schema_version !== "money-adventure-support-v1") return null;
	const manifest = support.game_manifest;
	const example = manifest.worked_example;
	return <section className="money-support"><p className="support-type">{support.title_si}</p><h2>{example.prompt_si}</h2>{manifest.scaffold_type === "visual_guidance" ? <MoneyVisualCue game={example.game as Record<string, unknown>} /> : <MoneyWorkedDemo example={example} stage={stage} />}<ol>{example.steps_si.map((text, index) => <li className={index < stage ? "done" : ""} key={text}>{text}</li>)}</ol><button className="money-primary" onClick={stage < manifest.required_actions ? onNext : onComplete}>{stage < manifest.required_actions ? "ඊළඟ පියවර" : "දැන් මම කරමි"}</button></section>;
}

export function MoneyWorkedDemo({ example, stage }: { example: MoneyAdventureWorkedExample; stage: number }) {
	const response = example.correct_response;
	const game = example.game as Record<string, unknown>;
	if (!response) return null;
	if (response.kind === "currency_recognition") return <div className="worked-money"><div className="placed-money">{response.placements.slice(0, stage * 4).map((row) => <CurrencyToken compact key={row.denomination_id} id={row.denomination_id} />)}</div></div>;
	if (response.kind === "amount_construction") { const visible = response.selected_denominations.slice(0, stage); const running = denominationTotal(visible); return <div className="worked-money"><img src="/curriculum/game/G5-AREA-MAT-10/money-purse.png" alt="" /><div className="placed-money">{taggedDenominations(visible).map((token) => <CurrencyToken compact key={token.key} id={token.id} />)}</div><strong>දැනට: රු. {formatMoney(running)}</strong>{stage >= example.steps_si.length && <b>තවත් වලංගු සංයෝජන තිබිය හැක.</b>}</div>; }
	if (response.kind === "money_arithmetic") return <div className="worked-money"><MoneyWorkingTable game={game} demo={response} demoStage={stage} />{stage >= 4 && <strong>රු. {formatMoney(response.result_in_cents)}</strong>}</div>;
	if (response.kind === "shopping_calculation") { const visibleLines = stage === 0 ? 0 : stage === 1 ? 1 : response.selected_products.length; return <div className="worked-money"><div className="shop-working">{response.selected_products.slice(0, visibleLines).map((productId, index) => <p key={productId}>පේළිය {index + 1}: රු. {formatMoney(response.line_totals_in_cents[index])}</p>)}{stage >= 3 && <p>මුළු මිල: රු. {formatMoney(response.total_in_cents)}</p>}{stage >= 4 && <p>ඉතිරිය: රු. {formatMoney(response.change_in_cents)}</p>}</div></div>; }
	return null;
}

export const representativeShopLines = (prices: number[], quantities: number[]) => calculateLineTotals(prices, quantities);
