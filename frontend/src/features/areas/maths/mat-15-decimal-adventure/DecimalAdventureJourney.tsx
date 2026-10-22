// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import {
	adaptiveGameProgressStage,
	AdventureProgress,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	decimalReadingResponse,
	decimalToFractionResponse,
	fractionToDecimalResponse,
	shadingResponse,
} from "./decimalLogic";
import { DECIMAL_ASSET_ROOT, DECIMAL_GAMES, DECIMAL_SKILLS } from "./manifest";
import "./decimal-adventure.css";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

function DecimalGuideImage({ alt }: { alt: string }) {
	const [failed, setFailed] = useState(false);

	if (failed)
		return (
			<span className="decimal-guide-fallback" aria-hidden="true">
				✦
			</span>
		);

	return (
		<img
			src={`${DECIMAL_ASSET_ROOT}/decimal-guide.png`}
			alt={alt}
			onError={() => setFailed(true)}
		/>
	);
}

export function DecimalAdventureJourney({
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
		DECIMAL_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = DECIMAL_SKILLS[index];
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
					area_id: "G5-AREA-MAT-15",
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
		setMoves((count) => count + 1);
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
					response.kind === "decimal_tenths_shading"
						? response.selected_count
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
		const nextDone = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(nextDone);
		setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) advance();
	}, [step, correct]);

	return (
		<main
			className="decimal-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="decimal-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>දශම</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="decimal-game-list" aria-label="දශම ක්‍රීඩා">
					{DECIMAL_GAMES.map((game, gameIndex) => (
						<button
							className="decimal-game-card"
							key={game.id}
							onClick={() => void openSkill(DECIMAL_SKILLS[gameIndex].id)}
						>
							<DecimalGuideImage alt="දශම මඟ පෙන්වන මිතුරිය" />
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
				<section className="decimal-play game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={4}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="decimal-position">
						ක්‍රියාකාරකම {index + 1}/4 · {active?.name}
					</p>
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<DecimalActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="decimal-primary"
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
									<DecimalActivity
										key={activity.revision_id}
										game={activity.game}
										onResponse={record}
									/>
								)}
							>
								{support.game_manifest.stage_kind !== "view" && (
									<button
										className="decimal-primary"
										disabled={busy || !response}
										onClick={() => void answerSupport()}
									>
										තහවුරු කරන්න
									</button>
								)}
							</SupportRoundFrame>
						) : (
							<DecimalSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						))}
					{step === "withdrawing" && (
						<p role="status">පිළිතුරු සහිත සහාය ඉවත් කර අලුත් දශම ප්‍රශ්නය සූදානම් කරමින්…</p>
					)}
					{step === "feedback" && !correct && (
						<section className="decimal-feedback">
							<h2>{`${feedbackLabel(feedback)} නැවත බලමු.`}</h2>
							<button className="decimal-primary" onClick={advance}>
								නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={index + 1}
							gameCount={DECIMAL_GAMES.length}
							onContinue={() =>
								index < DECIMAL_SKILLS.length - 1
									? void openSkill(DECIMAL_SKILLS[index + 1].id)
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
	if (value?.startsWith("decimal-")) return "දශමය කියවන ආකාරය";
	if (value === "tenths-parts") return "අඳුරු කළ කොටස් ගණන";
	if (value === "tenths-digit") return "දශම ලකුණට පසු කොටුව";
	return "ලවය සහ හරය";
}

export function DecimalActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const kind = String(game.response_kind);
	if (kind === "decimal_reading_match")
		return (
			<DecimalReadingMatcher
				decimalTenths={game.decimal_tenths as number[]}
				readingTiles={game.reading_tiles as ReadingTile[]}
				onResponse={onResponse}
			/>
		);
	if (kind === "decimal_tenths_shading")
		return (
			<ShadingActivity
				representation={game.representation as "rectangle" | "circle"}
				decimalTenths={Number(game.decimal_tenths)}
				onResponse={onResponse}
			/>
		);
	if (kind === "tenths_fraction_to_decimal")
		return (
			<FractionToDecimalActivity
				numerator={Number(game.numerator)}
				onResponse={onResponse}
			/>
		);
	return (
		<DecimalToFractionActivity
			decimalTenths={Number(game.decimal_tenths)}
			onResponse={onResponse}
		/>
	);
}

type ReadingTile = { reading_id: string; label_si: string };

export function DecimalReadingMatcher({
	decimalTenths,
	readingTiles,
	onResponse,
}: {
	decimalTenths: number[];
	readingTiles: ReadingTile[];
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [active, setActive] = useState<number | null>(null);
	const [matches, setMatches] = useState<Record<number, string>>({});
	const [trace, setTrace] = useState<string[]>([]);
	const [revisions, setRevisions] = useState(0);
	const match = (readingId: string) => {
		if (active === null) return;
		const correction = Boolean(
			matches[active] && matches[active] !== readingId,
		);
		const next = { ...matches, [active]: readingId };
		const nextTrace = [...trace, `match:${active}:${readingId}`];
		setMatches(next);
		setTrace(nextTrace);
		setActive(null);
		if (correction) setRevisions((count) => count + 1);
		onResponse(
			decimalReadingResponse(
				decimalTenths,
				next,
				nextTrace,
				revisions + Number(correction),
			) as ConstructedResponse | null,
		);
	};
	return (
		<div className="decimal-matcher">
			<section>
				<h3>1. දශමය තෝරන්න</h3>
				<div className="decimal-tile-grid">
					{decimalTenths.map((digit) => (
						<button
							className={
								active === digit ? "selected" : matches[digit] ? "matched" : ""
							}
							aria-pressed={active === digit}
							key={digit}
							onClick={() => setActive(digit)}
						>
							0.<strong>{digit}</strong>
						</button>
					))}
				</div>
			</section>
			<section>
				<h3>2. කියවීම ගළපන්න</h3>
				<div className="reading-tile-grid">
					{readingTiles.map((tile) => (
						<button
							disabled={active === null}
							key={tile.reading_id}
							onClick={() => match(tile.reading_id)}
						>
							{tile.label_si}
						</button>
					))}
				</div>
			</section>
		</div>
	);
}

function ShadingActivity({
	representation,
	decimalTenths,
	onResponse,
}: {
	representation: "rectangle" | "circle";
	decimalTenths: number;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [selected, setSelected] = useState<number[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const [revisions, setRevisions] = useState(0);
	const toggle = (index: number) => {
		const wasSelected = selected.includes(index);
		const next = wasSelected
			? selected.filter((part) => part !== index)
			: [...selected, index];
		const nextTrace = [
			...trace,
			`toggle:${index}:${wasSelected ? "off" : "on"}`,
		];
		setSelected(next);
		setTrace(nextTrace);
		if (wasSelected) setRevisions((count) => count + 1);
		onResponse(
			shadingResponse(
				representation,
				decimalTenths,
				next,
				nextTrace,
				revisions + Number(wasSelected),
			) as ConstructedResponse,
		);
	};
	return (
		<div className="shading-activity">
			<div className="decimal-sequence">
				<strong>0.{decimalTenths}</strong>
				<span>→</span>
				<span>සමාන කොටස් 10</span>
				<span>→</span>
				<span>අඳුරු කළ කොටස් {selected.length}</span>
			</div>
			{representation === "rectangle" ? (
				<TenthsFrame selected={selected} onToggle={toggle} />
			) : (
				<TenthsCircle selected={selected} onToggle={toggle} />
			)}
		</div>
	);
}

export function TenthsFrame({
	selected,
	onToggle,
	disabled = false,
}: {
	selected: number[];
	onToggle(index: number): void;
	disabled?: boolean;
}) {
	return (
		<fieldset className="tenths-frame">
			<legend className="sr-only">සමාන කොටස් දහයක සෘජුකෝණාස්‍රය</legend>
			{TENTH_PARTS.map((partNumber) => {
				const index = partNumber - 1;
				return (
					<button
						style={{ minWidth: 48, minHeight: 48 }}
						className={selected.includes(index) ? "shaded" : ""}
						aria-label={`කොටස ${index + 1}${selected.includes(index) ? " අඳුරු කර ඇත" : " අඳුරු කර නැත"}`}
						aria-pressed={selected.includes(index)}
						disabled={disabled}
						key={partNumber}
						onClick={() => onToggle(index)}
					/>
				);
			})}
		</fieldset>
	);
}

const TENTH_PARTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

function sectorPath(index: number) {
	const start = ((index * 36 - 90) * Math.PI) / 180,
		end = (((index + 1) * 36 - 90) * Math.PI) / 180;
	const point = (angle: number) =>
		`${120 + 100 * Math.cos(angle)} ${120 + 100 * Math.sin(angle)}`;
	return `M 120 120 L ${point(start)} A 100 100 0 0 1 ${point(end)} Z`;
}

export function TenthsCircle({
	selected,
	onToggle,
	disabled = false,
}: {
	selected: number[];
	onToggle(index: number): void;
	disabled?: boolean;
}) {
	return (
		<fieldset className="tenths-circle-wrap">
			<legend className="sr-only">සමාන කොටස් දහයක වෘත්තය</legend>
			<svg className="tenths-circle" viewBox="0 0 240 240" aria-hidden="true">
				{TENTH_PARTS.map((partNumber) => {
					const index = partNumber - 1;
					return (
						<path
							d={sectorPath(index)}
							className={selected.includes(index) ? "shaded" : ""}
							key={partNumber}
						/>
					);
				})}
			</svg>
			<div className="tenths-circle-controls">
				{TENTH_PARTS.map((partNumber) => {
					const index = partNumber - 1;
					const angle = ((index * 36 - 72) * Math.PI) / 180;
					return (
						<button
							style={{
								minWidth: 48,
								minHeight: 48,
								left: `${50 + 34 * Math.cos(angle)}%`,
								top: `${50 + 34 * Math.sin(angle)}%`,
							}}
							aria-label={`වෘත්ත කොටස ${partNumber}${selected.includes(index) ? " අඳුරු කර ඇත" : " අඳුරු කර නැත"}`}
							aria-pressed={selected.includes(index)}
							disabled={disabled}
							key={partNumber}
							onClick={() => onToggle(index)}
						/>
					);
				})}
			</div>
		</fieldset>
	);
}

export function FractionDisplay({
	numerator,
	denominator,
	numeratorContent,
	denominatorContent,
}: {
	numerator?: number;
	denominator?: number;
	numeratorContent?: React.ReactNode;
	denominatorContent?: React.ReactNode;
}) {
	return (
		<span
			className="fraction-display"
			role="img"
			aria-label={`${numerator ?? "හිස්"} බෙදීම ${denominator ?? "හිස්"}`}
		>
			<span className="fraction-numerator">
				{numeratorContent ?? numerator}
			</span>
			<span className="fraction-bar" aria-hidden="true" />
			<span className="fraction-denominator">
				{denominatorContent ?? denominator}
			</span>
		</span>
	);
}

function FractionToDecimalActivity({
	numerator,
	onResponse,
}: {
	numerator: number;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [digit, setDigit] = useState("");
	const [trace, setTrace] = useState<string[]>([]);
	const enter = (value: string) => {
		if (!/^[1-9]$/.test(value)) return;
		const nextTrace = [...trace, `tenths:${value}`];
		setDigit(value);
		setTrace(nextTrace);
		onResponse(
			fractionToDecimalResponse(
				numerator,
				value,
				nextTrace,
			) as ConstructedResponse,
		);
	};
	return (
		<fieldset
			className="conversion-equation"
			onKeyDown={(event) => {
				if (/^[1-9]$/.test(event.key)) enter(event.key);
				if (event.key === "Backspace" || event.key === "Delete") {
					setDigit("");
					onResponse(null);
				}
			}}
		>
			<legend className="sr-only">දහයෙන් කොටස දශමයක් කරන්න</legend>
			<div className="equation-row">
				<FractionDisplay numerator={numerator} denominator={10} />
				<span>=</span>
				<DecimalInput value={digit} />
			</div>
			<NumericKeypad
				onDigit={enter}
				onClear={() => {
					setDigit("");
					onResponse(null);
				}}
				digits={[1, 2, 3, 4, 5, 6, 7, 8, 9]}
			/>
		</fieldset>
	);
}

export function DecimalInput({
	value,
	disabled = false,
}: {
	value: string;
	disabled?: boolean;
}) {
	return (
		<span className="decimal-input">
			<span>0</span>
			<span className="decimal-point">.</span>
			<button
				style={{ minWidth: 48, minHeight: 48 }}
				disabled={disabled}
				aria-label="දශම ලකුණට පසු ඉලක්කම"
				onClick={() => {}}
			>
				{value || "?"}
			</button>
		</span>
	);
}

function DecimalToFractionActivity({
	decimalTenths,
	onResponse,
}: {
	decimalTenths: number;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [active, setActive] = useState<"numerator" | "denominator">(
		"numerator",
	);
	const [numerator, setNumerator] = useState("");
	const [denominator, setDenominator] = useState("");
	const [order, setOrder] = useState<Array<"numerator" | "denominator">>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const enter = (digit: string) => {
		if (!/^\d$/.test(digit)) return;
		const nextNumerator = active === "numerator" ? digit : numerator;
		const nextDenominator =
			active === "denominator"
				? `${denominator}${digit}`.slice(0, 2)
				: denominator;
		const nextOrder = order.includes(active) ? order : [...order, active];
		const nextTrace = [
			...trace,
			`${active}:${active === "numerator" ? nextNumerator : nextDenominator}`,
		];
		setNumerator(nextNumerator);
		setDenominator(nextDenominator);
		setOrder(nextOrder);
		setTrace(nextTrace);
		onResponse(
			decimalToFractionResponse(
				decimalTenths,
				nextNumerator,
				nextDenominator,
				nextOrder,
				nextTrace,
			) as ConstructedResponse | null,
		);
	};
	const clear = () => {
		if (active === "numerator") setNumerator("");
		else setDenominator("");
		onResponse(null);
	};
	return (
		<fieldset
			className="conversion-equation"
			onKeyDown={(event) => {
				if (/^\d$/.test(event.key)) enter(event.key);
				if (event.key === "Backspace" || event.key === "Delete") clear();
			}}
		>
			<legend className="sr-only">දශමය දහයෙන් කොටසක් කරන්න</legend>
			<div className="equation-row">
				<strong className="fixed-decimal">0.{decimalTenths}</strong>
				<span>=</span>
				<FractionInput
					numerator={numerator}
					denominator={denominator}
					active={active}
					onActivate={setActive}
				/>
			</div>
			<NumericKeypad
				onDigit={enter}
				onClear={clear}
				digits={[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}
			/>
		</fieldset>
	);
}

export function FractionInput({
	numerator,
	denominator,
	active,
	onActivate,
	disabled = false,
}: {
	numerator: string;
	denominator: string;
	active: "numerator" | "denominator";
	onActivate(value: "numerator" | "denominator"): void;
	disabled?: boolean;
}) {
	return (
		<FractionDisplay
			numeratorContent={
				<button
					style={{ minWidth: 48, minHeight: 48 }}
					className={active === "numerator" ? "selected" : ""}
					aria-label="ලවය ඇතුළත් කරන්න"
					aria-pressed={active === "numerator"}
					disabled={disabled}
					onClick={() => onActivate("numerator")}
				>
					{numerator || "?"}
				</button>
			}
			denominatorContent={
				<button
					style={{ minWidth: 48, minHeight: 48 }}
					className={active === "denominator" ? "selected" : ""}
					aria-label="හරය ඇතුළත් කරන්න"
					aria-pressed={active === "denominator"}
					disabled={disabled}
					onClick={() => onActivate("denominator")}
				>
					{denominator || "?"}
				</button>
			}
		/>
	);
}

export function NumericKeypad({
	digits,
	onDigit,
	onClear,
}: {
	digits: number[];
	onDigit(value: string): void;
	onClear(): void;
}) {
	return (
		<fieldset className="decimal-keypad">
			<legend className="sr-only">අංක යතුරු පුවරුව</legend>
			{digits.map((digit) => (
				<button
					style={{ minWidth: 48, minHeight: 48 }}
					aria-label={`අංක ${digit}`}
					key={digit}
					onClick={() => onDigit(String(digit))}
				>
					{digit}
				</button>
			))}
			<button
				style={{ minWidth: 48, minHeight: 48 }}
				aria-label="තෝරාගත් පිළිතුර හිස් කරන්න"
				onClick={onClear}
			>
				⌫
			</button>
		</fieldset>
	);
}

function DecimalSupport({
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
	if (support.game_manifest.schema_version !== "decimal-adventure-support-v1")
		return null;
	const manifest = support.game_manifest;
	const visualOnly = manifest.scaffold_type === "visual_guidance";
	return (
		<section className="decimal-support">
			<p className="support-type">{support.title_si}</p>
			<h2>{manifest.worked_example.prompt_si}</h2>
			<DecimalWorkedDemo
				example={manifest.worked_example}
				stage={visualOnly ? 0 : stage}
				visualOnly={visualOnly}
			/>
			<ol>
				{manifest.worked_example.steps_si.map((line, index) => (
					<li className={index < stage ? "done" : ""} key={line}>
						{line}
					</li>
				))}
			</ol>
			{stage < manifest.required_actions ? (
				<button className="decimal-primary" onClick={onNext}>
					{visualOnly ? "ඉඟිය බැලුවා" : "ඊළඟ පියවර"}
				</button>
			) : (
				<button className="decimal-primary" onClick={onComplete}>
					සහාය ඉවත් කර නැවත උත්සාහ කරන්න
				</button>
			)}
		</section>
	);
}

type WorkedExample = {
	prompt_si: string;
	game: Record<string, unknown>;
	correct_response: Record<string, unknown> | null;
	steps_si: string[];
};

export function DecimalWorkedDemo({
	example,
	stage,
	visualOnly = false,
}: {
	example: WorkedExample;
	stage: number;
	visualOnly?: boolean;
}) {
	const game = example.game,
		response = example.correct_response,
		kind = String(game.response_kind);
	if (visualOnly)
		return (
			<div className="decimal-visual-cue">
				<DecimalGuideImage alt="හිස් පිළිතුරු තැන පෙන්වන දශම මඟ පෙන්වන මිතුරිය" />
				<strong>
					{kind === "decimal_tenths_shading"
						? "සමාන කොටස් 10"
						: kind.includes("fraction")
							? "ලවය ↔ දශම ස්ථානය"
							: "0 .  දහයෙන් ඉලක්කම"}
				</strong>
			</div>
		);
	if (kind === "decimal_reading_match")
		return (
			<div className="worked-matches">
				{(
					(response?.matches as Array<{
						decimal_tenths: number;
						reading_id: string;
					}>) ?? []
				)
					.slice(0, Math.max(1, stage + 1))
					.map((row) => (
						<p key={row.decimal_tenths}>
							<strong>0.{row.decimal_tenths}</strong> →{" "}
							{
								((game.reading_tiles as ReadingTile[]) ?? []).find(
									(tile) => tile.reading_id === row.reading_id,
								)?.label_si
							}
						</p>
					))}
			</div>
		);
	if (kind === "decimal_tenths_shading") {
		const selected = (
			(response?.selected_part_indices as number[]) ?? []
		).slice(0, Math.max(1, stage * 3));
		return (
			<div className="worked-shading">
				{game.representation === "circle" ? (
					<TenthsCircle selected={selected} onToggle={() => {}} disabled />
				) : (
					<TenthsFrame selected={selected} onToggle={() => {}} disabled />
				)}
				<p>
					<FractionDisplay
						numerator={Number(game.decimal_tenths)}
						denominator={10}
					/>{" "}
					= <strong>0.{Number(game.decimal_tenths)}</strong>
				</p>
			</div>
		);
	}
	if (kind === "tenths_fraction_to_decimal")
		return (
			<div className="equation-row">
				<FractionDisplay numerator={Number(game.numerator)} denominator={10} />
				<span>=</span>
				<DecimalInput
					value={stage > 1 ? String(game.numerator) : ""}
					disabled
				/>
			</div>
		);
	return (
		<div className="equation-row">
			<strong className="fixed-decimal">0.{Number(game.decimal_tenths)}</strong>
			<span>=</span>
			<FractionInput
				numerator={stage > 0 ? String(game.decimal_tenths) : ""}
				denominator={stage > 1 ? "10" : ""}
				active="numerator"
				onActivate={() => {}}
				disabled
			/>
		</div>
	);
}
