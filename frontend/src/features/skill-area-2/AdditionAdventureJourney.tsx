import {
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
	type CSSProperties,
} from "react";
import type {
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import {
	AdaptiveSupportActivity,
	SUPPORT_TYPE_LABELS,
} from "../mobile-learning-flow/AdaptiveSupportActivity";
import {
	adaptiveGameProgressStage,
	AdventureProgress,
} from "../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	SuccessCelebration,
} from "../mobile-learning-flow/AdventureShared";
import { expandedTerms } from "./additionLogic";
import {
	ADDITION_ASSET_ROOT,
	ADDITION_CHAPTERS,
	ADDITION_SKILLS,
	type AdditionChapter,
} from "./manifest";

type Step =
	| "chapters"
	| "skills"
	| "question"
	| "feedback"
	| "support"
	| "withdrawing"
	| "result";
type Evidence = {
	moves: number;
	corrections: number;
	carries: number;
	firstActionMs: number | null;
};

export function AdditionAdventureJourney({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: {
	api: Pick<
		LearningFlowClient,
		| "open"
		| "answerBefore"
		| "completeSupport"
		| "withdrawSupport"
		| "presentAfter"
		| "answerAfter"
	>;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("chapters");
	const [chapter, setChapter] = useState<AdditionChapter | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [evidence, setEvidence] = useState<Evidence>({
		moves: 0,
		corrections: 0,
		carries: 0,
		firstActionMs: null,
	});
	const [startedAt, setStartedAt] = useState(0);
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState("");
	const [answeredCorrectly, setAnsweredCorrectly] = useState(false);
	const [activeSkillId, setActiveSkillId] = useState<string | null>(null);
	const [failedAttempts, setFailedAttempts] = useState<Record<string, number>>(
		{},
	);
	const [supportActions, setSupportActions] = useState(0);
	const [supportComplete, setSupportComplete] = useState(false);
	const requestSequence = useRef(0);
	const requestInFlight = useRef(false);
	const openInFlight = useRef(false);
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{
		episodeId: string;
		requestId: string;
		supportRevisionId: string;
		manifestRevisionId: string;
	} | null>(null);
	const skills = useMemo(
		() => ADDITION_SKILLS.filter((skill) => skill.chapter === chapter),
		[chapter],
	);
	const progressStage = adaptiveGameProgressStage(
		step,
		manifest?.measurement_role,
	);
	const activeChallengeIndex = Math.max(
		0,
		skills.findIndex((skill) => skill.id === activeSkillId),
	);
	const activeChapterIndex = ADDITION_CHAPTERS.findIndex(
		(item) => item.id === chapter,
	);
	const isLastChallenge = activeChallengeIndex === skills.length - 1;
	const isLastChapter = activeChapterIndex === ADDITION_CHAPTERS.length - 1;
	const resetWork = useCallback(() => {
		setResponse(null);
		setEvidence({ moves: 0, corrections: 0, carries: 0, firstActionMs: null });
		setStartedAt(Date.now());
	}, []);
	const run = useCallback(
		async <T,>(operation: () => Promise<T>): Promise<T | undefined> => {
			setBusy(true);
			try {
				return await operation();
			} catch (error) {
				onFailure(error);
				return undefined;
			} finally {
				setBusy(false);
			}
		},
		[onFailure],
	);

	useEffect(() => {
		if (step !== "withdrawing" || !pendingWithdrawal) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() =>
				api.withdrawSupport(
					pendingWithdrawal.episodeId,
					{
						request_id: pendingWithdrawal.requestId,
						support_revision_id: pendingWithdrawal.supportRevisionId,
						manifest_revision_id: pendingWithdrawal.manifestRevisionId,
						all_support_removed: true,
						answer_revealing_state_cleared: true,
						input_handlers_cleared: true,
					},
					crypto.randomUUID(),
				),
			);
			if (!withdrawn || cancelled) return;
			const next = await run(() =>
				api.presentAfter(pendingWithdrawal.episodeId, crypto.randomUUID()),
			);
			if (!next || cancelled) return;
			setManifest(next.manifest);
			resetWork();
			setPendingWithdrawal(null);
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pendingWithdrawal, resetWork, run, step]);

	const openSkill = async (skillId: string) => {
		if (openInFlight.current) return;
		openInFlight.current = true;
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
					area_id: "G5-AREA-MAT-02",
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		openInFlight.current = false;
		if (!opened) return;
		setEpisodeId(opened.episode_id);
		setActiveSkillId(skillId);
		setManifest(opened.manifest);
		setSupport(null);
		setAnsweredCorrectly(false);
		resetWork();
		setStep("question");
	};
	const record = (
		next: ConstructedResponse | null,
		change: Partial<Evidence> = {},
	) => {
		setResponse(next);
		setEvidence((current) => ({
			moves: current.moves + 1,
			corrections: current.corrections + (change.corrections ?? 0),
			carries: current.carries + (change.carries ?? 0),
			firstActionMs:
				current.firstActionMs ?? Math.max(0, Date.now() - startedAt),
		}));
	};
	const answer = async () => {
		if (!episodeId || !manifest || !response || requestInFlight.current) return;
		requestInFlight.current = true;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			response_time_ms: Math.max(0, Date.now() - startedAt),
			interaction_summary: {
				move_count: evidence.moves,
				correction_count: evidence.corrections,
				carry_actions: evidence.carries,
				first_action_ms: evidence.firstActionMs ?? 0,
				active_time_ms: Math.max(0, Date.now() - startedAt),
				attempt_count: activeSkillId
					? (failedAttempts[activeSkillId] ?? 0) + 1
					: 1,
			},
		};
		const sequence = ++requestSequence.current;
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episodeId, body, crypto.randomUUID())
				: api.answerBefore(episodeId, body, crypto.randomUUID()),
		);
		requestInFlight.current = false;
		if (!next || sequence !== requestSequence.current) return;
		if (
			!next.server_score ||
			next.server_score.presentation_id !== manifest.presentation_id ||
			next.server_score.item_revision_id !== manifest.revision_id
		) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
			return;
		}
		const correct = next.server_score.correct === true;
		setAnsweredCorrectly(correct);
		setMessage(correct ? "ක්‍රියාව සම්පූර්ණයි!" : "නැවත බලමු.");
		if (activeSkillId) {
			setFailedAttempts((current) => {
				const updated = { ...current };
				if (correct) delete updated[activeSkillId];
				else if (manifest.measurement_role === "unsupported_before") {
					updated[activeSkillId] = (updated[activeSkillId] ?? 0) + 1;
				}
				return updated;
			});
		}
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
		}
		setStep(correct ? "result" : "feedback");
	};
	const advanceFeedback = () => {
		setResponse(null);
		if (support) {
			setSupportActions(0);
			setSupportComplete(false);
			setStep("support");
		} else setStep("result");
	};
	const openNextGame = () => {
		const nextChallenge = skills[activeChallengeIndex + 1];
		if (nextChallenge) {
			void openSkill(nextChallenge.id);
			return;
		}
		const nextChapter = ADDITION_CHAPTERS[activeChapterIndex + 1];
		if (!nextChapter) {
			setStep("chapters");
			return;
		}
		const nextSkill = ADDITION_SKILLS.find(
			(skill) => skill.chapter === nextChapter.id,
		);
		if (!nextSkill) {
			setStep("chapters");
			return;
		}
		setChapter(nextChapter.id);
		void openSkill(nextSkill.id);
	};
	const retryCurrentGame = () => {
		if (activeSkillId) void openSkill(activeSkillId);
		else setStep("chapters");
	};
	const finishSupport = async () => {
		if (!episodeId || !support) return;
		const game = support.game_manifest;
		if (game.schema_version === "half-set-manifest-v1") return;
		const completed = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: 1000,
					steps_viewed: Math.max(1, Math.min(8, evidence.moves || 1)),
					manifest_revision_id: game.revision_id,
					interaction_summary: {
						completed: true,
						renderer_id: game.renderer_id,
						parallel_example_id: game.parallel_example_id,
						support_actions: supportActions,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (!completed) return;
		setPendingWithdrawal({
			episodeId,
			requestId: crypto.randomUUID(),
			supportRevisionId: support.revision_id,
			manifestRevisionId: game.revision_id,
		});
		setSupport(null);
		setStep("withdrawing");
	};

	return (
		<section
			className="learning-adventure addition-adventure"
			data-addition-step={step}
			data-episode-id={episodeId ?? undefined}
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="adventure-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>එකතු කිරීම</h1>
			</header>
			{step === "chapters" && (
				<div className="adventure-cards">
					{ADDITION_CHAPTERS.map((item, index) => (
						<button
							type="button"
							key={item.id}
							style={
								{
									"--card-tone": [
										"#54CBAB",
										"#32A9E6",
										"#FED136",
										"#F47FA5",
										"#57558F",
									][index],
								} as CSSProperties
							}
							onClick={() => {
								const first = ADDITION_SKILLS.find(
									(skill) => skill.chapter === item.id,
								);
								if (!first) return;
								setChapter(item.id);
								void openSkill(first.id);
							}}
						>
							<img src={item.asset} alt="" />
							<span>
								<strong>{item.title}</strong>
								<small>
									අභියෝග{" "}
									{
										ADDITION_SKILLS.filter((skill) => skill.chapter === item.id)
											.length
									}
									ක් · {item.difficulty}
								</small>
							</span>
						</button>
					))}
				</div>
			)}
			{(step === "question" || step === "feedback") && manifest && chapter && (
				<div className="adventure-play">
					<AdventureProgress
						stage={progressStage}
						activityCount={skills.length}
					/>
					<p className="game-round-label">
						ක්‍රීඩාව {activeChapterIndex + 1} · අභියෝගය {activeChallengeIndex + 1}/
						{skills.length}
					</p>
					<p className="independent-badge">තනිවම අතින් ගොඩනඟන්න</p>
					<h2>{manifest.prompt_si}</h2>
					<div
						aria-disabled={step === "feedback"}
						style={step === "feedback" ? { pointerEvents: "none" } : undefined}
					>
						<AdditionMechanic
							key={manifest.revision_id}
							chapter={chapter}
							game={manifest.game ?? {}}
							onChange={record}
						/>
					</div>
					{step === "feedback" && <h3 role="status">{message}</h3>}
					<button
						type="button"
						className="primary-action"
						disabled={step === "question" && (!response || busy)}
						onClick={step === "feedback" ? advanceFeedback : answer}
					>
						{step === "feedback"
							? support
								? "උදව්ව බලන්න"
								: "ඊළඟට"
							: "තහවුරු කරන්න"}
					</button>
				</div>
			)}
			{step === "support" && support && chapter && (
				<div className="adventure-play" data-support-visible="true">
					<AdventureProgress
						stage={progressStage}
						activityCount={skills.length}
					/>
					<p
						className="support-badge"
						data-support-type={support.scaffold_type}
					>
						උදව් වර්ගය: {SUPPORT_TYPE_LABELS[support.scaffold_type]}
					</p>
					<h2>{support.title_si}</h2>
					{support.body_si.map((line) => (
						<p key={line}>{line}</p>
					))}
					{support.game_manifest.schema_version !== "half-set-manifest-v1" &&
						support.game_manifest.schema_version !==
							"classroom-action-support-v1" && (
							<AdaptiveSupportActivity
								manifest={support.game_manifest}
								onProgress={(actions, complete) => {
									setSupportActions(actions);
									setSupportComplete(complete);
								}}
							/>
						)}
					<button
						type="button"
						className="primary-action"
						disabled={busy || !supportComplete}
						onClick={finishSupport}
					>
						උදව්ව අවසන් කරන්න
					</button>
				</div>
			)}
			{step === "withdrawing" && (
				<div className="adventure-result" role="status">
					<AdventureProgress
						stage={progressStage}
						activityCount={skills.length}
					/>
					<h2>උදව් සම්පූර්ණයෙන් ඉවත් කරමින්…</h2>
					<p>අලුත් ස්වාධීන ක්‍රියාව සූදානම් කරමු.</p>
				</div>
			)}
			{step === "result" && (
				<div
					className={`adventure-result${answeredCorrectly ? " is-success" : ""}`}
					data-answer-result={answeredCorrectly ? "correct" : "incorrect"}
				>
					<AdventureProgress
						stage={progressStage}
						activityCount={skills.length}
					/>
					{answeredCorrectly && <SuccessCelebration />}
					<h2>
						{answeredCorrectly
							? isLastChallenge
								? `${ADDITION_CHAPTERS[activeChapterIndex]?.title ?? "ක්‍රීඩාව"} සම්පූර්ණයි!`
								: `අභියෝගය ${activeChallengeIndex + 1} සම්පූර්ණයි!`
							: message}
					</h2>
					<p>
						{answeredCorrectly
							? isLastChallenge
								? isLastChapter
									? "සියලු එකතු කිරීමේ අභියෝග අවසන්. තරු ඔබටයි!"
									: "මෙම ක්‍රීඩාවේ අභියෝග අවසන්. ඊළඟ ක්‍රීඩාවට යමු."
								: "නියමයි! දැන් ඊළඟ අභියෝගයට යමු."
							: "තවම නිවැරදි නැහැ. වෙනස් උදව්වක් සමඟ නැවත උත්සාහ කරමු."}
					</p>
					<button
						type="button"
						className="primary-action"
						onClick={answeredCorrectly ? openNextGame : retryCurrentGame}
					>
						{answeredCorrectly
							? !isLastChallenge
								? "ඊළඟ අභියෝගය"
								: isLastChapter
									? "ක්‍රීඩා තේරීමට"
									: "ඊළඟ ක්‍රීඩාව"
							: "නැවත උත්සාහ කරන්න"}
					</button>
				</div>
			)}
		</section>
	);
}

function AdditionMechanic({
	chapter,
	game,
	onChange,
}: {
	chapter: AdditionChapter;
	game: Record<string, unknown>;
	onChange(
		response: ConstructedResponse | null,
		evidence?: Partial<Evidence>,
	): void;
}) {
	if (chapter === "fruit_catch")
		return <FruitCatch game={game} onChange={onChange} />;
	if (chapter === "tuk_tuk_journey")
		return <TukTuk game={game} onChange={onChange} />;
	if (chapter === "carrying_crane")
		return <CarryCrane game={game} onChange={onChange} />;
	if (chapter === "market_delivery_planner")
		return <MarketDelivery game={game} onChange={onChange} />;
	return <FestivalTable game={game} onChange={onChange} />;
}

function NumberInput({
	label,
	value,
	onValue,
}: {
	label: string;
	value: string;
	onValue(value: string): void;
}) {
	return (
		<label className="numeric-builder">
			<span>{label}</span>
			<input
				type="number"
				inputMode="numeric"
				min="0"
				max="999999"
				value={value}
				onChange={(event) => onValue(event.target.value)}
			/>
		</label>
	);
}

function tagValues(values: number[]) {
	const occurrences = new Map<number, number>();
	return values.map((value, index) => {
		const occurrence = (occurrences.get(value) ?? 0) + 1;
		occurrences.set(value, occurrence);
		return { id: `${value}-${occurrence}`, index, value };
	});
}

function FruitCatch({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse | null): void;
}) {
	const addends = (game.addends as number[] | undefined) ?? [8, 7];
	const [selected, setSelected] = useState<number[]>([]);
	const [total, setTotal] = useState("");
	const emit = (nextSelected: number[], nextTotal: string) =>
		onChange(
			nextSelected.length === addends.length && nextTotal !== ""
				? {
						kind: "combine_quantities",
						combined: true,
						total: Number(nextTotal),
					}
				: null,
		);
	const toggle = (index: number) => {
		const next = selected.includes(index)
			? selected.filter((value) => value !== index)
			: [...selected, index];
		setSelected(next);
		emit(next, total);
	};
	return (
		<div className="manipulation-board fruit-catch">
			<fieldset className="quantity-groups">
				<legend className="sr-only">එකතු කළ යුතු කාණ්ඩ</legend>
				{tagValues(addends).map(({ id, index, value }) => (
					<button
						type="button"
						key={id}
						aria-label={`${value} ඇති කාණ්ඩය එකතු කූඩයට දමන්න`}
						aria-pressed={selected.includes(index)}
						onClick={() => toggle(index)}
					>
						<img src={`${ADDITION_ASSET_ROOT}/fruit-tokens.png`} alt="" />
						<strong>{value}</strong>
					</button>
				))}
			</fieldset>
			<div
				className={
					selected.length === addends.length
						? "combine-zone is-filled"
						: "combine-zone"
				}
				role="status"
			>
				<img src={`${ADDITION_ASSET_ROOT}/empty-fruit-basket.png`} alt="" />
				<strong>
					{selected.length}/{addends.length}
				</strong>
			</div>
			<NumberInput
				label="එකතු කළ පළතුරු ගණන"
				value={total}
				onValue={(next) => {
					setTotal(next);
					emit(selected, next);
				}}
			/>
		</div>
	);
}

function TukTuk({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse | null): void;
}) {
	const start = Number(game.start ?? 82);
	const stops = (game.stops as number[] | undefined) ?? [12, 24, 16];
	const [totals, setTotals] = useState(stops.map(() => ""));
	const update = (index: number, value: string) => {
		const next = totals.map((current, at) => (at === index ? value : current));
		setTotals(next);
		onChange(
			next.every((item) => item !== "")
				? { kind: "route_progression", totals: next.map(Number) }
				: null,
		);
	};
	return (
		<div className="manipulation-board tuk-route">
			<div className="route-hero" aria-hidden="true">
				<img src={`${ADDITION_ASSET_ROOT}/tuk-tuk.png`} alt="" />
				<img
					src={`${ADDITION_ASSET_ROOT}/addition-trail-landmarks.png`}
					alt=""
				/>
			</div>
			<ol className="addition-route" aria-label="සමුච්චිත එකතු කිරීමේ මාර්ගය">
				<li className="route-start">
					<span>ආරම්භය</span>
					<strong>{start}</strong>
				</li>
				{stops.map((value, index) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: stop order is the mathematical route identity.
					<li key={`${value}-${index}`} className="route-node">
						<span className="route-addend">+{value}</span>
						<label>
							<span className="sr-only">නැවතුම {index + 1} සමුච්චිත එකතුව</span>
							<input
								type="number"
								inputMode="numeric"
								aria-label={`නැවතුම ${index + 1} සමුච්චිත එකතුව`}
								value={totals[index]}
								onChange={(event) => update(index, event.target.value)}
							/>
						</label>
					</li>
				))}
			</ol>
		</div>
	);
}

function CarryCrane({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(
		response: ConstructedResponse | null,
		evidence?: Partial<Evidence>,
	): void;
}) {
	const addends = (game.addends as number[] | undefined) ?? [2678, 1456];
	const placeLabels = ["දස දහස්", "දහස්", "සිය", "දහය", "එක"];
	const [carryValues, setCarryValues] = useState([0, 0, 0, 0, 0]);
	const [digits, setDigits] = useState(["", "", "", "", ""]);
	const emit = (
		nextCarries: number[],
		nextDigits: string[],
		evidence?: Partial<Evidence>,
	) => {
		const completed = nextDigits.every((digit, index) =>
			index === 0 ? digit === "" || /^\d$/.test(digit) : /^\d$/.test(digit),
		);
		const rendered = nextDigits.join("");
		onChange(
			completed && rendered !== ""
				? {
						kind: "regroup_carry",
						total: Number(rendered),
						carry_count: nextCarries.filter((value) => value > 0).length,
						aligned: true,
					}
				: null,
			evidence,
		);
	};
	const updateDigit = (index: number, value: string) => {
		const normalized = value.replace(/\D/g, "").slice(-1);
		const next = digits.map((digit, at) => (at === index ? normalized : digit));
		setDigits(next);
		emit(carryValues, next);
	};
	const cycleCarry = (index: number) => {
		const next = carryValues.map((value, at) =>
			at === index ? (value + 1) % 3 : value,
		);
		setCarryValues(next);
		emit(next, digits, { carries: 1 });
	};
	return (
		<div className="manipulation-board carry-crane">
			<img
				className="carry-tray"
				src={`${ADDITION_ASSET_ROOT}/carry-exchange-tray.png`}
				alt=""
			/>
			<div className="column-addition-wrap">
				<table className="column-addition-table">
					<caption>ස්ථානීය අගය අනුව එකතු කිරීම</caption>
					<thead>
						<tr>
							{placeLabels.map((label) => (
								<th scope="col" key={label}>
									{label}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						<tr className="carry-row">
							{carryValues.map((value, index) => (
								<td key={placeLabels[index]}>
									<button
										type="button"
										onClick={() => cycleCarry(index)}
										aria-label={`${placeLabels[index]} තැනේ ගෙනයාම වෙනස් කරන්න`}
									>
										<img
											src={`${ADDITION_ASSET_ROOT}/carry-token.png`}
											alt=""
										/>
										<span>{value}</span>
									</button>
								</td>
							))}
						</tr>
						{addends.map((value, row) => (
							// biome-ignore lint/suspicious/noArrayIndexKey: addend rows preserve textbook order and can contain duplicates.
							<tr key={`${value}-${row}`}>
								{String(value)
									.padStart(5, "0")
									.split("")
									.map((digit, column) => (
										// biome-ignore lint/suspicious/noArrayIndexKey: place columns have fixed semantic positions.
										<td key={`${row}-${placeLabels[column]}`}>
											{column === 0 && digit === "0" ? "" : digit}
										</td>
									))}
							</tr>
						))}
						<tr className="answer-row">
							{digits.map((digit, index) => (
								<td key={placeLabels[index]}>
									<input
										value={digit}
										inputMode="numeric"
										onChange={(event) => updateDigit(index, event.target.value)}
										aria-label={`${placeLabels[index]} තැනේ පිළිතුරු ඉලක්කම`}
									/>
								</td>
							))}
						</tr>
					</tbody>
				</table>
			</div>
			<fieldset className="expanded-addends">
				<legend className="sr-only">විහිදුණු ආකාර</legend>
				{addends.map((value) => (
					<p key={value}>
						<strong>{value.toLocaleString("en-US")}</strong>
						<span>
							{expandedTerms(value)
								.map((term) => term.toLocaleString("en-US"))
								.join(" + ")}
						</span>
					</p>
				))}
			</fieldset>
		</div>
	);
}

function MarketDelivery({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse | null): void;
}) {
	const addends = (game.addends as number[] | undefined) ?? [225, 375];
	const [selected, setSelected] = useState<number[]>([]);
	const [total, setTotal] = useState("");
	const emit = (indices: number[], nextTotal: string) =>
		onChange(
			indices.length === addends.length && nextTotal !== ""
				? {
						kind: "cargo_loading",
						selected_indices: indices,
						total: Number(nextTotal),
					}
				: null,
		);
	const toggle = (index: number) => {
		const next = selected.includes(index)
			? selected.filter((value) => value !== index)
			: [...selected, index];
		setSelected(next);
		emit(next, total);
	};
	return (
		<div className="manipulation-board market-delivery">
			<div className="parcel-shelf">
				{tagValues(addends).map(({ id, index, value }) => (
					<button
						type="button"
						key={id}
						aria-pressed={selected.includes(index)}
						aria-label={`${value} කාණ්ඩය එකතු තැටියට දමන්න`}
						onClick={() => toggle(index)}
					>
						<img src={`${ADDITION_ASSET_ROOT}/cargo-parcel.png`} alt="" />
						{value}
					</button>
				))}
			</div>
			<div className="handcart">
				<img
					src={`${ADDITION_ASSET_ROOT}/delivery-handcart.png`}
					alt="බෙදාහැරීම් කරත්තය"
				/>
				<span>
					{selected.length}/{addends.length} පටවා ඇත
				</span>
			</div>
			<div className="story-addition-zones" aria-live="polite">
				{tagValues(addends).map(({ id, index, value }) => (
					<span
						className={selected.includes(index) ? "is-loaded" : ""}
						key={id}
					>
						{selected.includes(index) ? value : "?"}
					</span>
				))}
			</div>
			<NumberInput
				label="පටවා ඇති මුළු ප්‍රමාණය"
				value={total}
				onValue={(next) => {
					setTotal(next);
					emit(selected, next);
				}}
			/>
		</div>
	);
}

function FestivalTable({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse | null): void;
}) {
	const table = (game.table as number[][] | undefined) ?? [
		[120, 230, 340],
		[210, 320, 430],
		[310, 420, 530],
	];
	const rows = (game.row_labels as string[] | undefined) ?? ["අ", "ආ", "ඇ"];
	const columns = (game.column_labels as string[] | undefined) ?? [
		"1",
		"2",
		"3",
	];
	const [selected, setSelected] = useState<string[]>([]);
	const [total, setTotal] = useState("");
	const selectionCount = Number(game.selection_count ?? 3);
	const tableContext = String(game.table_context ?? "schools");
	const targetType = String(game.target_type ?? "row");
	const emit = (cells: string[], nextTotal: string) =>
		onChange(
			cells.length === selectionCount && nextTotal !== ""
				? {
						kind: "data_cell_selection",
						selected_cells: cells,
						total: Number(nextTotal),
					}
				: null,
		);
	const toggle = (id: string) => {
		const next = selected.includes(id)
			? selected.filter((cell) => cell !== id)
			: selected.length < selectionCount
				? [...selected, id]
				: selected;
		setSelected(next);
		emit(next, total);
	};
	return (
		<div className="manipulation-board festival-data">
			<table>
				<caption>
					{tableContext === "seedlings" ? "පැළ දත්ත වගුව" : "පාසල් ශිෂ්‍ය දත්ත වගුව"}
				</caption>
				<thead>
					<tr>
						<th scope="col">{tableContext === "seedlings" ? "මාසය" : "පාසල"}</th>
						{columns.map((label) => (
							<th scope="col" key={label}>
								{label}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{table.map((row, rowIndex) => (
						<tr key={rows[rowIndex]}>
							<th scope="row">
								{tableContext === "schools" && (
									<img
										src={`${ADDITION_ASSET_ROOT}/school-building-token-${["a", "b", "c"][rowIndex]}.png`}
										alt=""
									/>
								)}
								{rows[rowIndex]}
							</th>
							{row.map((value, columnIndex) => {
								const id = `r${rowIndex}c${columnIndex}`;
								return (
									<td key={id}>
										<button
											type="button"
											aria-pressed={selected.includes(id)}
											aria-label={`${rows[rowIndex]} ${columns[columnIndex]} අගය ${value} තෝරන්න`}
											onClick={() => toggle(id)}
										>
											{value}
										</button>
									</td>
								);
							})}
						</tr>
					))}
				</tbody>
			</table>
			<div className="table-calculation-tray" aria-live="polite">
				<img
					src={
						tableContext === "seedlings"
							? `${ADDITION_ASSET_ROOT}/festival-data-tokens.png`
							: `${ADDITION_ASSET_ROOT}/school-building-token-b.png`
					}
					alt=""
				/>
				<div>
					<small>
						{targetType === "maximum_row" ? "සසඳන පේළිය" : "තෝරාගත් අගයන්"}
					</small>
					<strong>
						{selected
							.map((id) => {
								const match = /^r(\d+)c(\d+)$/.exec(id);
								return match
									? table[Number(match[1])]?.[Number(match[2])]
									: null;
							})
							.filter((value) => value != null)
							.join(" + ") || "—"}
					</strong>
				</div>
			</div>
			<NumberInput
				label="තෝරාගත් සාක්ෂිවල ප්‍රතිඵලය"
				value={total}
				onValue={(next) => {
					setTotal(next);
					emit(selected, next);
				}}
			/>
		</div>
	);
}
