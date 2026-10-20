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
	GameSuccessScreen,
} from "../mobile-learning-flow/AdventureShared";
import {
	NUMBER_PATTERN_ASSET_ROOT,
	NUMBER_PATTERN_CHAPTERS,
	NUMBER_PATTERN_SKILLS,
	type NumberPatternChapter,
} from "./manifest";

type Step =
	| "chapters"
	| "question"
	| "feedback"
	| "support"
	| "withdrawing"
	| "result";
type Evidence = {
	moves: number;
	corrections: number;
	ruleChanges: number;
	operationChanges: number;
	firstActionMs: number | null;
};
const PATTERN_POSITION_KEYS = [
	"first",
	"second",
	"third",
	"fourth",
	"fifth",
	"sixth",
] as const;

export function NumberPatternJourney({
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
	const [chapter, setChapter] = useState<NumberPatternChapter | null>(null);
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
	const [evidence, setEvidence] = useState<Evidence>({
		moves: 0,
		corrections: 0,
		ruleChanges: 0,
		operationChanges: 0,
		firstActionMs: null,
	});
	const [failedAttempts, setFailedAttempts] = useState<Record<string, number>>(
		{},
	);
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
		() => NUMBER_PATTERN_SKILLS.filter((skill) => skill.chapter === chapter),
		[chapter],
	);
	const activeChallengeIndex = Math.max(
		0,
		skills.findIndex((skill) => skill.id === activeSkillId),
	);
	const activeChapterIndex = NUMBER_PATTERN_CHAPTERS.findIndex(
		(item) => item.id === chapter,
	);
	const isLastChallenge = activeChallengeIndex === skills.length - 1;
	const progressStage = adaptiveGameProgressStage(
		step,
		manifest?.measurement_role,
	);

	const resetWork = useCallback(() => {
		setResponse(null);
		setEvidence({
			moves: 0,
			corrections: 0,
			ruleChanges: 0,
			operationChanges: 0,
			firstActionMs: null,
		});
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
					area_id: "G5-AREA-MAT-03",
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
			moves: current.moves + 1,
			corrections: current.corrections + (change.corrections ?? 0),
			ruleChanges: current.ruleChanges + (change.ruleChanges ?? 0),
			operationChanges:
				current.operationChanges + (change.operationChanges ?? 0),
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
				rule_changes: evidence.ruleChanges,
				operation_changes: evidence.operationChanges,
				first_action_ms: evidence.firstActionMs ?? 0,
				active_time_ms: Math.max(0, Date.now() - startedAt),
				attempt_count: activeSkillId
					? (failedAttempts[activeSkillId] ?? 0) + 1
					: 1,
				completion_order_valid: true,
				evidence_quality: 0.8,
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
		setMessage(correct ? "" : "නැවත බලමු.");
		if (
			activeSkillId &&
			!correct &&
			manifest.measurement_role === "unsupported_before"
		)
			setFailedAttempts((current) => ({
				...current,
				[activeSkillId]: (current[activeSkillId] ?? 0) + 1,
			}));
		if (next.status === "support_active" && next.support)
			setSupport(next.support);
		if (correct && !isLastChallenge) {
			const nextChallenge = skills[activeChallengeIndex + 1];
			if (nextChallenge) {
				await openSkill(nextChallenge.id);
				return;
			}
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
		const nextChapter = NUMBER_PATTERN_CHAPTERS[activeChapterIndex + 1];
		if (!nextChapter) {
			setStep("chapters");
			return;
		}
		const nextSkill = NUMBER_PATTERN_SKILLS.find(
			(skill) => skill.chapter === nextChapter.id,
		);
		if (nextSkill) void openSkill(nextSkill.id, nextChapter.id);
	};

	return (
		<section
			className="learning-adventure number-pattern-adventure"
			data-episode-id={episodeId ?? undefined}
			data-pattern-step={step}
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="adventure-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>සංඛ්‍යා රටා</h1>
			</header>
			{step === "chapters" && (
				<div className="adventure-cards pattern-chapter-cards">
					{NUMBER_PATTERN_CHAPTERS.map((item, index) => {
						const count = NUMBER_PATTERN_SKILLS.filter(
							(skill) => skill.chapter === item.id,
						).length;
						return (
							<button
								type="button"
								key={item.id}
								style={
									{
										"--card-tone": ["#54CBAB", "#32A9E6", "#7B61E8"][index],
									} as CSSProperties
								}
								onClick={() => {
									const first = NUMBER_PATTERN_SKILLS.find(
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
					<AdventureProgress
						stage={progressStage}
						activityCount={skills.length}
					/>
					<p className="game-round-label">
						ක්‍රීඩාව {activeChapterIndex + 1} · අභියෝගය {activeChallengeIndex + 1}/
						{skills.length}
					</p>
					<h2>{manifest.prompt_si}</h2>
					<div
						aria-disabled={step === "feedback"}
						style={step === "feedback" ? { pointerEvents: "none" } : undefined}
					>
						<PatternMechanic
							key={manifest.revision_id}
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
			{step === "support" && support && (
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
				</div>
			)}
			{step === "result" && (
				answeredCorrectly ? (
					<GameSuccessScreen gameNumber={activeChapterIndex + 1} gameCount={NUMBER_PATTERN_CHAPTERS.length} onContinue={advance} />
				) : (
					<div className="adventure-result" data-answer-result="incorrect">
						<AdventureProgress stage={progressStage} activityCount={skills.length} />
						<h2>{message}</h2>
						<button type="button" className="primary-action" onClick={() => activeSkillId && void openSkill(activeSkillId)}>නැවත උත්සාහ කරන්න</button>
					</div>
				)
			)}
		</section>
	);
}

export function PatternMechanic({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(
		response: ConstructedResponse | null,
		evidence?: Partial<Evidence>,
	): void;
}) {
	const visible = (game.visible_terms as Array<number | null> | undefined) ?? [
		1,
		3,
		5,
		null,
		null,
	];
	const operation = String(game.operation ?? "add");
	const missing =
		(game.missing_indices as number[] | undefined) ??
		visible
			.map((term, index) => (term == null ? index : -1))
			.filter((index) => index >= 0);
	const [selectedOperation, setSelectedOperation] = useState<
		"add" | "subtract" | null
	>(null);
	const [rule, setRule] = useState("");
	const [terms, setTerms] = useState(missing.map(() => ""));
	const emit = (
		nextOperation: "add" | "subtract" | null,
		nextRule: string,
		nextTerms: string[],
		evidence?: Partial<Evidence>,
	) => {
		if (!nextRule || !nextTerms.every(Boolean)) {
			onChange(null, evidence);
			return;
		}
		if (operation === "multiply")
			onChange(
				{
					kind: "constant_ratio_pattern",
					multiplier: Number(nextRule),
					completed_terms: nextTerms.map(Number),
				},
				evidence,
			);
		else if (nextOperation)
			onChange(
				{
					kind: "constant_difference_pattern",
					operation: nextOperation,
					difference: Number(nextRule),
					completed_terms: nextTerms.map(Number),
				},
				evidence,
			);
		else onChange(null, evidence);
	};
	const updateTerm = (position: number, value: string) => {
		const normalized = value.replace(/\D/g, "").slice(0, 4);
		const next = terms.map((term, index) =>
			index === position ? normalized : term,
		);
		setTerms(next);
		emit(selectedOperation, rule, next);
	};
	return (
		<div className="manipulation-board pattern-board">
			{game.chapter === "pattern_power_machine" && (
				<img
					className="pattern-machine"
					src={`${NUMBER_PATTERN_ASSET_ROOT}/pattern-rule-machine.png`}
					alt=""
				/>
			)}
			<fieldset className="pattern-rule-builder">
				<legend>රටාවේ රීතිය ගොඩනඟන්න</legend>
				{operation === "multiply" ? (
					<span className="pattern-fixed-operation" title="ගුණ කිරීම">
						×
					</span>
				) : (
					<div className="pattern-operation-buttons">
						<button
							type="button"
							aria-label="එකතු කිරීම තෝරන්න"
							aria-pressed={selectedOperation === "add"}
							onClick={() => {
								setSelectedOperation("add");
								emit("add", rule, terms, { operationChanges: 1 });
							}}
						>
							+
						</button>
						<button
							type="button"
							aria-label="අඩු කිරීම තෝරන්න"
							aria-pressed={selectedOperation === "subtract"}
							onClick={() => {
								setSelectedOperation("subtract");
								emit("subtract", rule, terms, { operationChanges: 1 });
							}}
						>
							−
						</button>
					</div>
				)}
				<label>
					<span>{operation === "multiply" ? "ගුණකය" : "පොදු අන්තරය"}</span>
					<input
						type="number"
						inputMode="numeric"
						min="1"
						max="10"
						value={rule}
						aria-label={
							operation === "multiply"
								? "ගුණකය ඇතුළත් කරන්න"
								: "පොදු අන්තරය ඇතුළත් කරන්න"
						}
						onChange={(event) => {
							const next = event.target.value.replace(/\D/g, "").slice(0, 2);
							setRule(next);
							emit(selectedOperation, next, terms, { ruleChanges: 1 });
						}}
					/>
				</label>
			</fieldset>
			<ol className="pattern-sequence" aria-label="සම්පූර්ණ කළ යුතු සංඛ්‍යා රටාව">
				{visible.map((term, index) => {
					const missingPosition = missing.indexOf(index);
					return (
						<li key={PATTERN_POSITION_KEYS[index]}>
							<div className="pattern-node">
								{term == null ? (
									<input
										type="number"
										inputMode="numeric"
										min="0"
										max="1000"
										value={terms[missingPosition] ?? ""}
										aria-label={`රටාවේ ${index + 1} වන ස්ථානය`}
										onChange={(event) =>
											updateTerm(missingPosition, event.target.value)
										}
									/>
								) : (
									<strong>{term}</strong>
								)}
							</div>
							{index < visible.length - 1 && (
								<span className="pattern-arrow" aria-hidden="true">
									→
								</span>
							)}
						</li>
					);
				})}
			</ol>
		</div>
	);
}
