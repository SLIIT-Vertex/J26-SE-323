import {
	Fragment,
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
import {
	SUBTRACTION_CHAPTERS,
	SUBTRACTION_SKILLS,
	exchangeLabel,
	resultDigitLabel,
	type SubtractionChapter,
} from "./manifest";
import {
	adjacent,
	applyExchanges,
	digitsOf,
	type Exchange,
} from "./subtractionLogic";

type Step =
	| "chapters"
	| "question"
	| "feedback"
	| "support"
	| "withdrawing"
	| "result";
type Evidence = {
	digitEntries: number;
	exchanges: number;
	invalidExchanges: number;
	corrections: number;
	cleared: number;
	operationChanges: number;
	storyReorders: number;
	alignmentCorrections: number;
	startedFromOnes: boolean;
	firstActionMs: number | null;
};
type Quantity = { source: "first" | "second"; label_si: string; value: number };

const emptyEvidence = (): Evidence => ({
	digitEntries: 0,
	exchanges: 0,
	invalidExchanges: 0,
	corrections: 0,
	cleared: 0,
	operationChanges: 0,
	storyReorders: 0,
	alignmentCorrections: 0,
	startedFromOnes: true,
	firstActionMs: null,
});

export function SubtractionAdventureJourney({
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
	const [chapter, setChapter] = useState<SubtractionChapter | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [activeSkillId, setActiveSkillId] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState("");
	const [answeredCorrectly, setAnsweredCorrectly] = useState(false);
	const [startedAt, setStartedAt] = useState(0);
	const [supportActions, setSupportActions] = useState(0);
	const [supportComplete, setSupportComplete] = useState(false);
	const [evidence, setEvidence] = useState<Evidence>(emptyEvidence);
	const [failedAttempts, setFailedAttempts] = useState<Record<string, number>>({});
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{
		episodeId: string;
		requestId: string;
		supportRevisionId: string;
		manifestRevisionId: string;
	} | null>(null);
	const requestInFlight = useRef(false);
	const openInFlight = useRef(false);
	const requestSequence = useRef(0);
	const skills = useMemo(
		() => SUBTRACTION_SKILLS.filter((skill) => skill.chapter === chapter),
		[chapter],
	);
	const activeChallengeIndex = Math.max(
		0,
		skills.findIndex((skill) => skill.id === activeSkillId),
	);
	const activeChapterIndex = SUBTRACTION_CHAPTERS.findIndex(
		(item) => item.id === chapter,
	);
	const isLastChallenge = activeChallengeIndex === skills.length - 1;
	const isLastChapter = activeChapterIndex === SUBTRACTION_CHAPTERS.length - 1;
	const progressStage = adaptiveGameProgressStage(
		step,
		manifest?.measurement_role,
	);
	const resetWork = useCallback(() => {
		setResponse(null);
		setEvidence(emptyEvidence());
		setStartedAt(Date.now());
		setMessage("");
		setSupportActions(0);
		setSupportComplete(false);
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
			setSupport(null);
			resetWork();
			setPendingWithdrawal(null);
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pendingWithdrawal, resetWork, run, step]);

	const openSkill = async (skillId: string, selectedChapter = chapter) => {
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
					area_id: "G5-AREA-MAT-04",
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		openInFlight.current = false;
		if (!opened) return;
		if (selectedChapter) setChapter(selectedChapter);
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
			...current,
			digitEntries: current.digitEntries + (change.digitEntries ?? 0),
			exchanges: current.exchanges + (change.exchanges ?? 0),
			invalidExchanges: current.invalidExchanges + (change.invalidExchanges ?? 0),
			corrections: current.corrections + (change.corrections ?? 0),
			cleared: current.cleared + (change.cleared ?? 0),
			operationChanges: current.operationChanges + (change.operationChanges ?? 0),
			storyReorders: current.storyReorders + (change.storyReorders ?? 0),
			alignmentCorrections:
				current.alignmentCorrections + (change.alignmentCorrections ?? 0),
			startedFromOnes: change.startedFromOnes ?? current.startedFromOnes,
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
			response_time_ms: reducedMotion
				? null
				: Math.max(0, Date.now() - startedAt),
			interaction_summary: {
				digit_entry_count: evidence.digitEntries,
				exchange_count: evidence.exchanges,
				invalid_exchange_count: evidence.invalidExchanges,
				column_corrections: evidence.corrections,
				cleared_digits: evidence.cleared,
				operation_changes: evidence.operationChanges,
				story_reorder_count: evidence.storyReorders,
				started_from_ones: evidence.startedFromOnes,
				completion_order_consistent:
					evidence.startedFromOnes && evidence.alignmentCorrections === 0,
				first_action_ms: evidence.firstActionMs ?? 0,
				active_time_ms: reducedMotion
					? 0
					: Math.max(0, Date.now() - startedAt),
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
		if (
			activeSkillId &&
			!correct &&
			manifest.measurement_role === "unsupported_before"
		) {
			setFailedAttempts((current) => ({
				...current,
				[activeSkillId]: (current[activeSkillId] ?? 0) + 1,
			}));
		}
		if (next.status === "support_active" && next.support) setSupport(next.support);
		else setSupport(null);
		setStep(next.status === "support_active" ? "feedback" : "result");
	};
	const advanceFeedback = () => {
		if (support) {
			setSupportActions(0);
			setSupportComplete(false);
			setStep("support");
		} else setStep("result");
	};
	const finishSupport = async () => {
		if (
			!episodeId ||
			!support ||
			support.game_manifest.schema_version === "half-set-manifest-v1"
		)
			return;
		const game = support.game_manifest;
		const completed = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Math.max(1000, Date.now() - startedAt),
					steps_viewed: Math.max(1, Math.min(8, supportActions)),
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
		setResponse(null);
		setStep("withdrawing");
	};
	const advance = () => {
		const nextChallenge = skills[activeChallengeIndex + 1];
		if (nextChallenge) {
			void openSkill(nextChallenge.id);
			return;
		}
		const nextChapter = SUBTRACTION_CHAPTERS[activeChapterIndex + 1];
		if (!nextChapter) {
			setStep("chapters");
			return;
		}
		const nextSkill = SUBTRACTION_SKILLS.find(
			(skill) => skill.chapter === nextChapter.id,
		);
		if (nextSkill) void openSkill(nextSkill.id, nextChapter.id);
	};

	return (
		<section
			className="learning-adventure subtraction-adventure"
			data-episode-id={episodeId ?? undefined}
			data-subtraction-step={step}
			data-skill-id={activeSkillId ?? undefined}
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="adventure-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>අඩු කිරීම</h1>
			</header>
			{step === "chapters" && (
				<div className="adventure-cards subtraction-chapter-cards">
					{SUBTRACTION_CHAPTERS.map((item, index) => {
						const count = SUBTRACTION_SKILLS.filter(
							(skill) => skill.chapter === item.id,
						).length;
						return (
							<button
								type="button"
								key={item.id}
								style={{ "--card-tone": ["#54CBAB", "#E6A23C", "#7B61E8"][index] } as CSSProperties}
								onClick={() => {
									const first = SUBTRACTION_SKILLS.find(
										(skill) => skill.chapter === item.id,
									);
									if (first) void openSkill(first.id, item.id);
								}}
							>
								<img src={item.asset} alt="" />
								<span>
									<strong>{item.title}</strong>
									<small>
										අභියෝග {count}ක් · {item.difficulty}
									</small>
								</span>
							</button>
						);
					})}
				</div>
			)}
			{(step === "question" || step === "feedback") && manifest && chapter && (
				<div className="adventure-play">
					<AdventureProgress stage={progressStage} activityCount={skills.length} />
					<p className="game-round-label">
						ක්‍රීඩාව {activeChapterIndex + 1} · අභියෝගය {activeChallengeIndex + 1}/
						{skills.length}
					</p>
					<p className="independent-badge">තනිවම අඩු කිරීම ගොඩනඟන්න</p>
					<h2>{manifest.prompt_si}</h2>
					<div
						aria-disabled={step === "feedback"}
						style={step === "feedback" ? { pointerEvents: "none" } : undefined}
					>
						<SubtractionMechanic
							key={manifest.revision_id}
							game={manifest.game ?? {}}
							reducedMotion={reducedMotion}
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
			{step === "support" && support && (
				<div className="adventure-play" data-support-visible="true">
					<AdventureProgress stage={progressStage} activityCount={skills.length} />
					<p className="support-badge" data-support-type={support.scaffold_type}>
						උදව් වර්ගය: {SUPPORT_TYPE_LABELS[support.scaffold_type]}
					</p>
					<h2>{support.title_si}</h2>
					{support.body_si.map((line) => (
						<p key={line}>{line}</p>
					))}
					{support.game_manifest.schema_version !== "half-set-manifest-v1" && (
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
					<AdventureProgress stage={progressStage} activityCount={skills.length} />
					<h2>උදව් සම්පූර්ණයෙන් ඉවත් කරමින්…</h2>
				</div>
			)}
			{step === "result" && (
				<div
					className={`adventure-result${answeredCorrectly ? " is-success" : ""}`}
					data-answer-result={answeredCorrectly ? "correct" : "incorrect"}
				>
					<AdventureProgress stage={progressStage} activityCount={skills.length} />
					{answeredCorrectly && isLastChallenge && <SuccessCelebration />}
					<h2>
						{answeredCorrectly
							? isLastChallenge
								? `${SUBTRACTION_CHAPTERS[activeChapterIndex]?.title} සම්පූර්ණයි!`
								: `අභියෝගය ${activeChallengeIndex + 1} සම්පූර්ණයි!`
							: message}
					</h2>
					<button
						type="button"
						className="primary-action"
						onClick={
							answeredCorrectly
								? advance
								: () => activeSkillId && void openSkill(activeSkillId)
						}
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

export function SubtractionMechanic({
	game,
	reducedMotion,
	onChange,
}: {
	game: Record<string, unknown>;
	reducedMotion: boolean;
	onChange(response: ConstructedResponse | null, evidence?: Partial<Evidence>): void;
}) {
	const places = (game.places as string[] | undefined) ?? ["hundreds", "tens", "ones"];
	const labels = (game.place_labels_si as string[] | undefined) ?? places;
	const quantities = game.quantities as Quantity[] | undefined;
	const expanded = game.representation === "expanded";
	const width = Number(game.width ?? places.length);
	const [source, setSource] = useState<string | null>(null);
	const [destination, setDestination] = useState<string | null>(null);
	const [exchanges, setExchanges] = useState<Exchange[]>([]);
	const [digits, setDigits] = useState(places.map(() => ""));
	const [minuendSource, setMinuendSource] = useState<"first" | "second" | null>(null);
	const [subtrahendSource, setSubtrahendSource] = useState<"first" | "second" | null>(null);
	const [terms, setTerms] = useState({
		minuend: places.map(() => ""),
		subtrahend: places.map(() => ""),
		adjusted: places.map(() => ""),
		result: places.map(() => ""),
	});
	const [finalResult, setFinalResult] = useState("");
	const [notice, setNotice] = useState("");
	const [moving, setMoving] = useState<Exchange | null>(null);
	const storyReady = !quantities || (minuendSource !== null && subtrahendSource !== null && minuendSource !== subtrahendSource);
	const placed = quantities
		? {
				minuend: quantities.find((item) => item.source === minuendSource)?.value,
				subtrahend: quantities.find((item) => item.source === subtrahendSource)?.value,
			}
		: { minuend: Number(game.minuend), subtrahend: Number(game.subtrahend) };
	const minuendDigits =
		placed.minuend == null ? places.map(() => null) : digitsOf(placed.minuend, width);
	const subtrahendDigits =
		placed.subtrahend == null ? places.map(() => null) : digitsOf(placed.subtrahend, width);
	const adjusted = applyExchanges(
		minuendDigits.map((digit) => digit ?? 0),
		places,
		exchanges,
	);

	const emitColumn = (
		nextDigits: string[],
		nextExchanges: Exchange[],
		evidence?: Partial<Evidence>,
	) => {
		if (!nextDigits.every((digit) => digit !== "")) {
			onChange(null, evidence);
			return;
		}
		onChange(
			{
				kind: "column_subtraction",
				result_digits: nextDigits.map(Number),
				exchanges: nextExchanges,
			},
			evidence,
		);
	};
	const emitExpanded = (
		next: typeof terms,
		nextResult: string,
		evidence?: Partial<Evidence>,
	) => {
		const rows = [next.minuend, next.subtrahend, next.adjusted, next.result];
		if (!nextResult || rows.some((row) => row.some((value) => value === ""))) {
			onChange(null, evidence);
			return;
		}
		onChange(
			{
				kind: "expanded_subtraction",
				minuend_terms: next.minuend.map(Number),
				subtrahend_terms: next.subtrahend.map(Number),
				adjusted_minuend_terms: next.adjusted.map(Number),
				result_terms: next.result.map(Number),
				result: Number(nextResult),
			},
			evidence,
		);
	};
	const emitStory = (
		nextDigits: string[],
		nextMinuend: "first" | "second" | null,
		nextSubtrahend: "first" | "second" | null,
		evidence?: Partial<Evidence>,
	) => {
		const relationship = game.relationship;
		if (
			relationship !== "difference_between" &&
			relationship !== "how_many_more"
		) {
			onChange(null, evidence);
			return;
		}
		if (
			!nextMinuend ||
			!nextSubtrahend ||
			nextMinuend === nextSubtrahend ||
			nextDigits.some((digit) => digit === "")
		) {
			onChange(null, evidence);
			return;
		}
		onChange(
			{
				kind: "difference_story",
				relationship,
				minuend_source: nextMinuend,
				subtrahend_source: nextSubtrahend,
				result_digits: nextDigits.map(Number),
				result: Number(nextDigits.join("")),
			},
			evidence,
		);
	};

	const performExchange = () => {
		if (!source || !destination || !adjacent(places, source, destination)) {
			setNotice("ඒ තීරු දෙක අතර හුවමාරු කළ නොහැක.");
			onChange(null, { invalidExchanges: 1 });
			return;
		}
		const sourceIndex = places.indexOf(source);
		if (adjusted[sourceIndex] <= 0) {
			setNotice("ඒ තීරුවෙන් ගෙන ඒමට ඉඩක් නැත.");
			onChange(null, { invalidExchanges: 1 });
			return;
		}
		const next = [
			...exchanges,
			{
				from_place: source as Exchange["from_place"],
				to_place: destination as Exchange["to_place"],
			},
		];
		setExchanges(next);
		setMoving(next[next.length - 1] ?? null);
		setNotice(
			reducedMotion
				? `${labels[sourceIndex]} තැනින් එකක් අඩු වී ${labels[places.indexOf(destination)]} තැනට දහයක් එක් විය.`
				: "හුවමාරුව සිදු විය.",
		);
		setSource(null);
		setDestination(null);
		if (quantities) emitStory(digits, minuendSource, subtrahendSource, { exchanges: 1 });
		else emitColumn(digits, next, { exchanges: 1 });
	};

	return (
		<div
			className="manipulation-board subtraction-board"
			data-kind={expanded ? "expanded" : quantities ? "story" : "column"}
			data-reduced-motion={reducedMotion || undefined}
		>
			{quantities && (
				<div className="story-scene">
					{quantities.map((quantity) => (
						<article key={quantity.source} className="story-quantity" data-source={quantity.source}>
							<img src={String(game.asset ?? "")} alt="" />
							<p>{quantity.label_si}</p>
							<strong>{quantity.value}</strong>
							<button
								type="button"
								className="touch-target story-minuend"
								aria-pressed={minuendSource === quantity.source}
								onClick={() => {
									setMinuendSource(quantity.source);
									emitStory(digits, quantity.source, subtrahendSource, {
										storyReorders: 1,
									});
								}}
							>
								විශාල සංඛ්‍යාව ලෙස තබන්න
							</button>
							<button
								type="button"
								className="touch-target story-subtrahend"
								aria-pressed={subtrahendSource === quantity.source}
								onClick={() => {
									setSubtrahendSource(quantity.source);
									emitStory(digits, minuendSource, quantity.source, {
										storyReorders: 1,
									});
								}}
							>
								කුඩා සංඛ්‍යාව ලෙස තබන්න
							</button>
						</article>
					))}
				</div>
			)}
			{expanded ? (
				<fieldset className="expanded-working">
					<legend className="sr-only">විහිදුණු ආකාරයෙන් අඩු කිරීම</legend>
					<p className="expanded-operands">
						{String(game.minuend)} − {String(game.subtrahend)}
					</p>
					{(
						[
							["minuend", "අඩු කරන සංඛ්‍යාව"],
							["subtrahend", "අඩු වන සංඛ්‍යාව"],
							["adjusted", "හුවමාරුවෙන් පසු"],
							["result", "වෙනස"],
						] as const
					).map(([row, legend]) => (
						<fieldset key={row} className="expanded-row" data-row={row}>
							<legend>{legend}</legend>
							<div className="expanded-terms">
								{places.map((place, index) => (
									<Fragment key={place}>
										{index > 0 ? (
											<span className="expanded-plus" aria-hidden="true">
												+
											</span>
										) : null}
										<label>
											<span>{labels[index]}</span>
											<input
												className="touch-target"
												inputMode="numeric"
												value={terms[row][index]}
												aria-label={`${legend} ${labels[index]} තැන`}
												onChange={(event) => {
													const value = event.target.value
														.replace(/\D/g, "")
														.slice(0, 5);
													const next = {
														...terms,
														[row]: terms[row].map((current, termIndex) =>
															termIndex === index ? value : current,
														),
													};
													setTerms(next);
													emitExpanded(next, finalResult, { digitEntries: 1 });
												}}
											/>
										</label>
									</Fragment>
								))}
							</div>
						</fieldset>
					))}
					<label className="expanded-final">
						<span>අවසාන සංඛ්‍යාව</span>
						<input
							className="touch-target expanded-result"
							inputMode="numeric"
							aria-label="අවසාන පිළිතුර ඇතුළත් කරන්න"
							value={finalResult}
							onChange={(event) => {
								const value = event.target.value.replace(/\D/g, "").slice(0, width);
								setFinalResult(value);
								emitExpanded(terms, value, { digitEntries: 1 });
							}}
						/>
					</label>
				</fieldset>
			) : (
				storyReady && (
					<div className="column-working">
						<table className="subtraction-table">
							<caption>ස්ථාන අගය අඩු කිරීමේ පුවරුව</caption>
							<thead>
								<tr>
									{places.map((place, index) => (
										<th key={place} scope="col">
											{labels[index]}
										</th>
									))}
								</tr>
							</thead>
							<tbody>
								<tr className="adjusted-digits">
									{adjusted.map((digit, index) => (
										<td key={places[index]}>
											{exchanges.length > 0 && digit !== minuendDigits[index] ? (
												<strong className={moving && !reducedMotion ? "exchange-token is-moving" : "exchange-token"}>
													{digit}
												</strong>
											) : null}
										</td>
									))}
								</tr>
								<tr>
									{minuendDigits.map((digit, index) => (
										<td key={places[index]}>
											<strong>{digit ?? ""}</strong>
										</td>
									))}
								</tr>
								<tr>
									{subtrahendDigits.map((digit, index) => (
										<td key={places[index]}>
											{index === 0 ? <span aria-hidden="true">− </span> : null}
											<strong>{digit ?? ""}</strong>
										</td>
									))}
								</tr>
								<tr className="result-digits">
									{places.map((place, index) => (
										<td key={place}>
											<input
												className="touch-target result-digit"
												data-place={place}
												inputMode="numeric"
												maxLength={2}
												aria-label={resultDigitLabel(place)}
												value={digits[index]}
												onChange={(event) => {
													const value = event.target.value.replace(/\D/g, "").slice(0, 1);
													const next = digits.map((digit, digitIndex) =>
														digitIndex === index ? value : digit,
													);
													setDigits(next);
													const firstFilled = next.findIndex((digit) => digit !== "");
													const startedFromOnes =
														firstFilled === -1 || firstFilled === next.length - 1;
													if (quantities) {
														emitStory(next, minuendSource, subtrahendSource, {
															digitEntries: 1,
															startedFromOnes,
														});
													} else emitColumn(next, exchanges, { digitEntries: 1, startedFromOnes });
												}}
											/>
										</td>
									))}
								</tr>
							</tbody>
						</table>
						<fieldset className="exchange-controls">
							<legend>හුවමාරුව තෝරන්න</legend>
							<div>
								{places.slice(0, -1).map((place) => (
									<button
										key={place}
										type="button"
										className="touch-target exchange-source"
										data-place={place}
										aria-pressed={source === place}
										onClick={() => setSource(place)}
									>
										{labels[places.indexOf(place)]}
									</button>
								))}
							</div>
							<div>
								{places.slice(1).map((place) => (
									<button
										key={place}
										type="button"
										className="touch-target exchange-destination"
										data-place={place}
										aria-pressed={destination === place}
										onClick={() => setDestination(place)}
									>
										{labels[places.indexOf(place)]}
									</button>
								))}
							</div>
							<button
								type="button"
								className="touch-target exchange-apply"
								aria-label={
									source && destination
										? exchangeLabel(source, destination)
										: "දහය තැනින් එකක් ගෙන එක තැනට දහයක් එක් කරන්න"
								}
								onClick={performExchange}
							>
								හුවමාරුව කරන්න
							</button>
							<button
								type="button"
								className="touch-target"
								onClick={() => {
									setExchanges([]);
									setMoving(null);
									setNotice("");
									if (quantities) emitStory(digits, minuendSource, subtrahendSource, { cleared: 1 });
									else emitColumn(digits, [], { cleared: 1 });
								}}
							>
								හුවමාරුව අහෝසි කරන්න
							</button>
						</fieldset>
						{notice && (
							<p role="status" className="exchange-status">
								{notice}
							</p>
						)}
					</div>
				)
			)}
		</div>
	);
}
