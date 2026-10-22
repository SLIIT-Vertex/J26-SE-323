// biome-ignore-all lint/a11y/useButtonType: application controls do not submit forms.
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
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	contextualRemainderInterpretation,
	type LongDivisionStep,
	writtenDivisionResponse,
	type WrittenDivisionResponse,
} from "./divisionLogic";
import { DIVISION_GAMES, DIVISION_SKILLS } from "./manifest";
import "./division-adventure.css";

type JourneyStep =
	| "chapters"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type DraftStep = {
	partial_dividend: number | null;
	quotient_digit: number | null;
	quotient_column: number | null;
	partial_product: number | null;
	subtraction_result: number | null;
	brought_down_digit: number | null;
};
type ActiveCell =
	| {
			kind: "step";
			step: number;
			field: keyof Omit<DraftStep, "quotient_column">;
			column?: number;
	  }
	| { kind: "final"; field: "quotient" | "remainder" };

export function DivisionAdventureJourney({
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
	const [step, setStep] = useState<JourneyStep>("chapters");
	const [skillId, setSkillId] = useState<string | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
	const [feedbackStep, setFeedbackStep] = useState<number | null>(null);
	const [busy, setBusy] = useState(false);
	const [moves, setMoves] = useState(0);
	const [firstActionMs, setFirstActionMs] = useState<number | null>(null);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [supportStage, setSupportStage] = useState(0);
	const [attempts, setAttempts] = useState<Record<string, number>>({});
	const [completedSkills, setCompletedSkills] = useState<string[]>([]);
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{
		episodeId: string;
		supportRevisionId: string;
		manifestRevisionId: string;
	} | null>(null);
	const inFlight = useRef(false);
	const activeIndex = Math.max(
		0,
		DIVISION_SKILLS.findIndex((item) => item.id === skillId),
	);
	const activeSkill = DIVISION_SKILLS[activeIndex];
	const activeGameIndex = DIVISION_GAMES.findIndex(
		(game) => game.id === activeSkill?.chapter,
	);
	const completedCount =
		DIVISION_SKILLS.findIndex((item) => !completedSkills.includes(item.id)) ===
		-1
			? DIVISION_SKILLS.length
			: DIVISION_SKILLS.findIndex((item) => !completedSkills.includes(item.id));
	const resetWork = useCallback(() => {
		setResponse(null);
		setMoves(0);
		setFirstActionMs(null);
		setStartedAt(Date.now());
	}, []);
	const run = useCallback(
		async <T,>(operation: () => Promise<T>) => {
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
						request_id: crypto.randomUUID(),
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
			setPendingWithdrawal(null);
			resetWork();
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pendingWithdrawal, resetWork, run, step]);

	const openSkill = async (nextSkillId: string) => {
		if (inFlight.current) return;
		inFlight.current = true;
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
					area_id: "G5-AREA-MAT-08",
					atomic_skill_id: nextSkillId,
				},
				crypto.randomUUID(),
			),
		);
		inFlight.current = false;
		if (!opened) return;
		setSkillId(nextSkillId);
		setEpisodeId(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setCorrect(false);
		setFeedbackStep(null);
		resetWork();
		setStep("question");
	};

	const record = (next: ConstructedResponse | null) => {
		setResponse(next);
		setMoves((value) => value + 1);
		setFirstActionMs((value) => value ?? Math.max(0, Date.now() - startedAt));
	};
	const confirm = async () => {
		if (!episodeId || !manifest || !response || inFlight.current) return;
		inFlight.current = true;
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
				move_count: moves,
				correction_count: 0,
				first_action_ms: firstActionMs ?? 0,
				active_time_ms: reducedMotion ? 0 : Math.max(0, Date.now() - startedAt),
				attempt_count: skillId ? (attempts[skillId] ?? 0) + 1 : 1,
				working_cell_count:
					response.kind === "equal_sharing"
						? response.group_quantities.length
						: response.kind === "written_division"
							? response.working_steps.length * 5
							: "written_working" in response
								? response.written_working.working_steps.length * 5
								: 0,
				bring_down_count:
					response.kind === "equal_sharing"
						? 0
						: response.kind === "written_division"
							? response.brought_down_digits.length
							: "written_working" in response
								? response.written_working.brought_down_digits.length
								: 0,
			},
		};
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episodeId, body, crypto.randomUUID())
				: api.answerBefore(episodeId, body, crypto.randomUUID()),
		);
		inFlight.current = false;
		if (!next) return;
		if (
			!next.server_score ||
			next.server_score.presentation_id !== manifest.presentation_id ||
			next.server_score.item_revision_id !== manifest.revision_id
		) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
			return;
		}
		const isCorrect = next.server_score.correct === true;
		setCorrect(isCorrect);
		setFeedbackStep(next.server_score.feedback_step_index ?? null);
		if (!isCorrect && skillId)
			setAttempts((current) => ({
				...current,
				[skillId]: (current[skillId] ?? 0) + 1,
			}));
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportStage(0);
			setStep("support");
		} else {
			setStep("feedback");
		}
	};

	const finishSupport = async () => {
		if (!episodeId || !support) return;
		const supportManifest = support.game_manifest;
		if (supportManifest.schema_version === "half-set-manifest-v1") return;
		if (
			supportManifest.schema_version !== "support-round-v1" &&
			supportStage < Number(supportManifest.required_actions)
		)
			return;
		const completed = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Math.max(0, Date.now() - startedAt),
					steps_viewed: Math.min(8, Math.max(1, supportStage)),
					manifest_revision_id: supportManifest.revision_id,
					interaction_summary: {
						completed: true,
						renderer_id: supportManifest.renderer_id,
						parallel_example_id: supportManifest.parallel_example_id,
						support_actions: supportStage,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (completed) advanceSupport(completed);
	};

	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) {
			setPendingWithdrawal({
				episodeId: next.episode_id,
				supportRevisionId: next.support_round.support_revision_id,
				manifestRevisionId: next.support_round.manifest_revision_id,
			});
			setSupport(null);
			setResponse(null);
			setStep("withdrawing");
			return;
		}
		if (next.support) {
			setSupport(next.support);
			setSupportStage(0);
			resetWork();
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
					response_time_ms: reducedMotion ? undefined : Date.now() - startedAt,
					interaction_summary: { move_count: moves },
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceSupport(next);
	};

	const continueAfterFeedback = () => {
		if (!skillId) return;
		if (!correct) {
			void openSkill(skillId);
			return;
		}
		const nextCompleted = completedSkills.includes(skillId)
			? completedSkills
			: [...completedSkills, skillId];
		setCompletedSkills(nextCompleted);
		const nextIndex = activeIndex + 1;
		if (DIVISION_SKILLS[nextIndex]?.chapter === activeSkill?.chapter)
			void openSkill(DIVISION_SKILLS[nextIndex].id);
		else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) continueAfterFeedback();
	}, [step, correct]);

	return (
		<main
			className="division-adventure"
			data-reduced-motion={reducedMotion || undefined}
			data-episode-id={episodeId ?? undefined}
		>
			<header className="division-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<div>
					<h1>බෙදීම</h1>
				</div>
			</header>
			{step === "chapters" ? (
				<section className="division-game-list" aria-label="බෙදීමේ ක්‍රීඩා">
					{DIVISION_GAMES.map((game) => (
						<button
							className="division-game-card"
							key={game.id}
							onClick={() => {
								const first = DIVISION_SKILLS.find(
									(item) => item.chapter === game.id,
								);
								if (first) void openSkill(first.id);
							}}
						>
							<img className="division-game-icon" src={game.asset} alt="" />
							<span>
								<strong>{game.title}</strong>
								<small>
									අභියෝග {game.challengeCount}ක් · {game.difficulty}
								</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="division-play-shell game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={5}
						currentActivity={Math.min(5, activeIndex + 1)}
						completedActivities={completedCount}
					/>
					{activeSkill && (
						<p className="division-position">
							ක්‍රීඩාව {activeGameIndex + 1} · ක්‍රියාකාරකම {activeIndex + 1}/5 ·{" "}
							{activeSkill.name}
						</p>
					)}
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<DivisionActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="division-primary"
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
									<DivisionActivity
										key={activity.revision_id}
										game={activity.game}
										onResponse={record}
									/>
								)}
							>
								{support.game_manifest.stage_kind !== "view" && (
									<button
										className="division-primary"
										disabled={busy || !response}
										onClick={() => void answerSupport()}
									>
										තහවුරු කරන්න
									</button>
								)}
							</SupportRoundFrame>
						) : (
							<DivisionSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						))}
					{step === "withdrawing" && (
						<p className="division-status" role="status">
							පිළිතුරු සහිත සහාය ඉවත් කර අලුත් ප්‍රශ්නය සූදානම් කරමින්…
						</p>
					)}
					{step === "feedback" && !correct && (
						<section className="division-feedback">
							<h2>
								{feedbackStep === null
									? "පළමු වැරදි පියවර නැවත බලමු."
									: `පියවර ${feedbackStep + 1} නැවත බලමු.`}
							</h2>
							<button
								className="division-primary"
								onClick={continueAfterFeedback}
							>
								සහාය සමඟ නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={activeGameIndex + 1}
							gameCount={DIVISION_GAMES.length}
							onContinue={() => {
								const nextGame = DIVISION_GAMES[activeGameIndex + 1];
								const nextSkill =
									nextGame &&
									DIVISION_SKILLS.find((item) => item.chapter === nextGame.id);
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
	disabled = false,
}: {
	onDigit(value: number): void;
	onClear(): void;
	disabled?: boolean;
}) {
	return (
		<fieldset className="division-keypad">
			<legend className="sr-only">අංක යතුරු පුවරුව</legend>
			{[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map((digit) => (
				<button
					style={{ minWidth: 48, minHeight: 48 }}
					key={digit}
					disabled={disabled}
					aria-label={`අංක ${digit}`}
					onClick={() => onDigit(digit)}
				>
					{digit}
				</button>
			))}
			<button
				style={{ minWidth: 48, minHeight: 48 }}
				disabled={disabled}
				aria-label="තෝරාගත් කොටුව හිස් කරන්න"
				onClick={onClear}
			>
				⌫
			</button>
		</fieldset>
	);
}

export function EqualSharingActivity({
	dividend,
	divisor,
	onResponse,
}: {
	dividend: number;
	divisor: number;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [groups, setGroups] = useState(
		() => Array(divisor).fill(0) as number[],
	);
	const [quotient, setQuotient] = useState<number | null>(null);
	const assigned = groups.reduce((sum, value) => sum + value, 0);
	const remainingMarkers = Array.from(
		{ length: Math.max(0, dividend - assigned) },
		(_, value) => value + 1,
	);
	const groupRows = groups.map((count, position) => ({
		count,
		position,
		id: `sharing-group-${position + 1}`,
	}));
	const update = (nextGroups: number[], nextQuotient = quotient) => {
		setGroups(nextGroups);
		onResponse(
			nextGroups.reduce((sum, value) => sum + value, 0) === dividend &&
				nextQuotient !== null
				? {
						kind: "equal_sharing",
						dividend,
						divisor,
						group_quantities: nextGroups,
						quotient: nextQuotient,
						remainder: 0,
					}
				: null,
		);
	};
	return (
		<section
			className="equal-sharing"
			aria-label={`${dividend} වස්තු කණ්ඩායම් ${divisor}කට බෙදීම`}
		>
			<img
				className="sharing-asset"
				src="/curriculum/game/G5-AREA-MAT-08/sharing-basket.png"
				alt=""
			/>
			<div className="unshared-pool">
				<strong>තව බෙදිය යුතුයි: {Math.max(0, dividend - assigned)}</strong>
				<div aria-hidden="true">
					{remainingMarkers.map((marker) => (
						<i key={`pool-marker-${marker}`} />
					))}
				</div>
			</div>
			<div className="sharing-groups">
				{groupRows.map((group) => (
					<button
						key={group.id}
						className="sharing-group"
						disabled={assigned >= dividend}
						aria-label={`${group.position + 1} කණ්ඩායම, වස්තු ${group.count}. ඊළඟ වස්තුව මෙහි තබන්න`}
						onClick={() => {
							const next = [...groups];
							next[group.position] += 1;
							update(next);
						}}
					>
						<span>{group.position + 1} කණ්ඩායම</span>
						<div aria-hidden="true">
							{Array.from({ length: group.count }, (_, value) => value + 1).map(
								(marker) => (
									<i key={`${group.id}-marker-${marker}`} />
								),
							)}
						</div>
						<strong>{group.count}</strong>
					</button>
				))}
			</div>
			<label className="answer-cell">
				<span>එක් කණ්ඩායමක</span>
				<button
					className={quotient === null ? "" : "filled"}
					aria-label="එක් කණ්ඩායමක වස්තු ගණන"
					aria-pressed={quotient !== null}
				>
					{quotient ?? "?"}
				</button>
			</label>
			<NumberPad
				onDigit={(digit) => {
					setQuotient(digit);
					onResponse(
						assigned === dividend
							? {
									kind: "equal_sharing",
									dividend,
									divisor,
									group_quantities: groups,
									quotient: digit,
									remainder: 0,
								}
							: null,
					);
				}}
				onClear={() => {
					setQuotient(null);
					onResponse(null);
				}}
			/>
		</section>
	);
}

function emptyDraft(stepCount: number): DraftStep[] {
	return Array.from({ length: stepCount }, () => ({
		partial_dividend: null,
		quotient_digit: null,
		quotient_column: null,
		partial_product: null,
		subtraction_result: null,
		brought_down_digit: null,
	}));
}

export function LongDivisionWorkspace({
	dividend,
	divisor,
	stepCount,
	traceLimit,
	onComplete,
	demoResponse,
	revealSteps = Number.POSITIVE_INFINITY,
	cueOnly = false,
	cueStep = 0,
}: {
	dividend: number;
	divisor: number;
	stepCount: number;
	traceLimit?: number;
	onComplete?(response: WrittenDivisionResponse | null): void;
	demoResponse?: WrittenDivisionResponse;
	revealSteps?: number;
	cueOnly?: boolean;
	cueStep?: number;
}) {
	const count = traceLimit ?? stepCount;
	const digits = String(dividend).split("");
	const digitCells = digits.map((digit, column) => ({
		digit,
		column,
		id: `dividend-column-${column + 1}`,
	}));
	const [draft, setDraft] = useState<DraftStep[]>(() => emptyDraft(count));
	const [finalQuotient, setFinalQuotient] = useState<number | null>(null);
	const [finalRemainder, setFinalRemainder] = useState<number | null>(null);
	const [active, setActive] = useState<ActiveCell | null>({
		kind: "step",
		step: 0,
		field: "partial_dividend",
	});
	const shownSteps = demoResponse?.working_steps.slice(0, revealSteps);
	const visibleDraft: DraftStep[] = demoResponse
		? draft.map((blank, index) => {
				const shown = shownSteps?.[index];
				return shown
					? {
							partial_dividend: shown.partial_dividend,
							quotient_digit: shown.quotient_digit,
							quotient_column: shown.quotient_column,
							partial_product: shown.partial_product,
							subtraction_result: shown.subtraction_result,
							brought_down_digit: shown.brought_down_digit,
						}
					: blank;
			})
		: draft;
	const visibleFinalQuotient =
		demoResponse && revealSteps >= count
			? demoResponse.final_quotient
			: finalQuotient;
	const visibleFinalRemainder =
		demoResponse && revealSteps >= count
			? demoResponse.final_remainder
			: finalRemainder;
	const cycleRows = visibleDraft.map((row, stepIndex) => ({
		row,
		stepIndex,
		id: `division-cycle-${stepIndex + 1}`,
	}));
	const visibleCycles =
		demoResponse || active?.kind === "final"
			? cycleRows
			: cycleRows.filter(({ stepIndex }) => stepIndex <= (active?.step ?? 0));
	const nextCell = useCallback(
		(current: ActiveCell): ActiveCell => {
			if (current.kind === "final")
				return current.field === "quotient"
					? { kind: "final", field: "remainder" }
					: current;
			const structuralColumn = Math.min(
				digits.length - 1,
				digits.length - count + current.step,
			);
			if (current.field === "partial_dividend")
				return {
					kind: "step",
					step: current.step,
					field: "quotient_digit",
					column: structuralColumn,
				};
			if (current.field === "quotient_digit")
				return { kind: "step", step: current.step, field: "partial_product" };
			if (current.field === "partial_product")
				return {
					kind: "step",
					step: current.step,
					field: "subtraction_result",
				};
			if (current.field === "subtraction_result")
				return current.step < count - 1
					? { kind: "step", step: current.step, field: "brought_down_digit" }
					: { kind: "final", field: "quotient" };
			return {
				kind: "step",
				step: Math.min(count - 1, current.step + 1),
				field: "partial_dividend",
			};
		},
		[count, digits.length],
	);

	const emit = useCallback(
		(
			nextDraft: DraftStep[],
			quotient: number | null,
			remainder: number | null,
		) => {
			if (!onComplete) return;
			const complete = nextDraft.every(
				(row, index) =>
					row.partial_dividend !== null &&
					row.quotient_digit !== null &&
					row.quotient_column !== null &&
					row.partial_product !== null &&
					row.subtraction_result !== null &&
					(index === count - 1 || row.brought_down_digit !== null),
			);
			if (!complete || quotient === null || remainder === null) {
				onComplete(null);
				return;
			}
			const steps: LongDivisionStep[] = nextDraft.map((row, index) => ({
				step_index: index,
				partial_dividend: row.partial_dividend as number,
				quotient_digit: row.quotient_digit as number,
				quotient_column: row.quotient_column as number,
				partial_product: row.partial_product as number,
				subtraction_result: row.subtraction_result as number,
				brought_down_digit: index === count - 1 ? null : row.brought_down_digit,
			}));
			onComplete(
				writtenDivisionResponse(dividend, divisor, steps, quotient, remainder),
			);
		},
		[count, dividend, divisor, onComplete],
	);
	const write = useCallback(
		(digit: number, clear = false) => {
			if (!active || demoResponse) return;
			if (active.kind === "final") {
				const current =
					active.field === "quotient" ? finalQuotient : finalRemainder;
				const maximumDigits = active.field === "quotient" ? 3 : 1;
				const next = clear
					? null
					: Number(`${current ?? ""}${digit}`.slice(-maximumDigits));
				if (active.field === "quotient") setFinalQuotient(next);
				else setFinalRemainder(next);
				emit(
					draft,
					active.field === "quotient" ? next : finalQuotient,
					active.field === "remainder" ? next : finalRemainder,
				);
				return;
			}
			setDraft((current) => {
				const next = current.map((row) => ({ ...row }));
				const row = next[active.step];
				const maximumDigits =
					active.field === "quotient_digit" ||
					active.field === "subtraction_result" ||
					active.field === "brought_down_digit"
						? 1
						: 3;
				const prior = row[active.field];
				row[active.field] = clear
					? null
					: Number(`${prior ?? ""}${digit}`.slice(-maximumDigits));
				if (active.field === "quotient_digit" && active.column !== undefined)
					row.quotient_column = active.column;
				emit(next, finalQuotient, finalRemainder);
				if (
					!clear &&
					[
						"quotient_digit",
						"subtraction_result",
						"brought_down_digit",
					].includes(active.field)
				)
					setActive(nextCell(active));
				return next;
			});
		},
		[
			active,
			demoResponse,
			draft,
			emit,
			finalQuotient,
			finalRemainder,
			nextCell,
		],
	);
	const handleKey = (event: React.KeyboardEvent) => {
		if (/^[0-9]$/.test(event.key)) {
			event.preventDefault();
			write(Number(event.key));
		}
		if (event.key === "Backspace" || event.key === "Delete") {
			event.preventDefault();
			write(0, true);
		}
	};
	const cellClass = (target: ActiveCell) =>
		active && JSON.stringify(active) === JSON.stringify(target)
			? "division-cell selected"
			: "division-cell";
	return (
		<section
			className={`long-division-workspace${cueOnly ? " cue-only" : ""}`}
			style={{ maxWidth: "100%", overflowX: "clip" }}
			aria-label={`${dividend} බෙදීම ${divisor} කඩදාසි ක්‍රමය`}
			onKeyDown={handleKey}
		>
			<p className="paper-instruction" role="status">
				{active?.kind === "final"
					? active.field === "quotient"
						? "දැන් අවසාන ලබ්ධිය ලියන්න."
						: "දැන් ඉතිරිය ලියන්න."
					: active?.field === "partial_dividend"
						? "බෙදිය යුතු කොටස ලියන්න."
						: active?.field === "quotient_digit"
							? "ලබ්ධි ඉලක්කම ඉහළින් ලියන්න."
							: active?.field === "partial_product"
								? "ගුණිතය යටින් ලියන්න."
								: active?.field === "subtraction_result"
									? "අඩු කිරීමේ පිළිතුර ලියන්න."
									: "ඊළඟ ඉලක්කම පහළට ගෙන එන්න."}
			</p>
			<div
				className="division-paper"
				style={{ "--digit-count": digits.length } as React.CSSProperties}
			>
				<div className="division-given">
					<strong
						className="divisor-position"
						role="img"
						aria-label={`බෙදුම ${divisor}`}
					>
						{divisor}
					</strong>
					<span className="division-bracket" aria-hidden="true" />
					<fieldset className="dividend-digits">
						<legend className="sr-only">බෙදිය යුතු සංඛ්‍යාව {dividend}</legend>
						{digitCells.map((cell) => (
							<button
								key={cell.id}
								aria-label={`${cell.column + 1} ස්ථානයේ ${cell.digit}, පහළට ගෙන එන්න`}
								onClick={() => {
									if (
										active?.kind === "step" &&
										active.field === "brought_down_digit"
									)
										write(Number(cell.digit));
								}}
							>
								{cell.digit}
							</button>
						))}
					</fieldset>
				</div>
				{visibleCycles.map(({ row, stepIndex: index, id }) => (
					<div
						className={`division-cycle cycle-${index}${cueOnly && index === cueStep ? " is-cue" : ""}`}
						key={id}
						data-step-type="divide-multiply-subtract-bring-down"
					>
						<span className="cycle-label">පියවර {index + 1}</span>
						<fieldset className="quotient-row">
							<legend className="sr-only">ලබ්ධි ඉලක්කම් පේළිය</legend>
							{digitCells.map((cell) => (
								<button
									style={{ minWidth: 48, minHeight: 48 }}
									key={`${id}-${cell.id}`}
									className={cellClass({
										kind: "step",
										step: index,
										field: "quotient_digit",
										column: cell.column,
									})}
									aria-label={`${index + 1} පියවරේ ${cell.column + 1} ස්ථානයේ ලබ්ධි ඉලක්කම`}
									aria-pressed={row.quotient_column === cell.column}
									onClick={() =>
										setActive({
											kind: "step",
											step: index,
											field: "quotient_digit",
											column: cell.column,
										})
									}
								>
									{row.quotient_column === cell.column
										? (row.quotient_digit ?? "")
										: ""}
								</button>
							))}
						</fieldset>
						<button
							style={{ minWidth: 48, minHeight: 48 }}
							className={cellClass({
								kind: "step",
								step: index,
								field: "partial_dividend",
							})}
							data-cell-type="division-choice"
							aria-label={`${index + 1} පියවරේ බෙදිය යුතු කොටස`}
							onClick={() =>
								setActive({
									kind: "step",
									step: index,
									field: "partial_dividend",
								})
							}
						>
							{row.partial_dividend ?? "?"}
						</button>
						<div className="paper-equation">
							<span aria-hidden="true">×</span>
							<button
								className={cellClass({
									kind: "step",
									step: index,
									field: "partial_product",
								})}
								data-cell-type="multiplication-result"
								aria-label={`${index + 1} පියවරේ ගුණිතය`}
								onClick={() =>
									setActive({
										kind: "step",
										step: index,
										field: "partial_product",
									})
								}
							>
								{row.partial_product ?? "?"}
							</button>
						</div>
						<div className="subtraction-line" aria-hidden="true" />
						<div className="paper-equation">
							<span aria-hidden="true">−</span>
							<button
								className={cellClass({
									kind: "step",
									step: index,
									field: "subtraction_result",
								})}
								data-cell-type="subtraction-result"
								aria-label={`${index + 1} පියවරේ අඩු කිරීමේ ඉතිරිය`}
								onClick={() =>
									setActive({
										kind: "step",
										step: index,
										field: "subtraction_result",
									})
								}
							>
								{row.subtraction_result ?? "?"}
							</button>
						</div>
						{index < count - 1 && (
							<div className="bring-down-row">
								<span aria-hidden="true">↓</span>
								<button
									className={cellClass({
										kind: "step",
										step: index,
										field: "brought_down_digit",
									})}
									data-cell-type="brought-down-digit"
									aria-label={`${index + 1} පියවරේ පහළට ගෙනෙන ඉලක්කම`}
									onClick={() =>
										setActive({
											kind: "step",
											step: index,
											field: "brought_down_digit",
										})
									}
								>
									{row.brought_down_digit ?? "?"}
								</button>
							</div>
						)}
					</div>
				))}
			</div>
			<div className="division-final">
				<label>
					<span>{count < stepCount ? "මෙම පියවරේ ලබ්ධිය" : "අවසාන ලබ්ධිය"}</span>
					<button
						className={cellClass({ kind: "final", field: "quotient" })}
						aria-label="අවසාන ලබ්ධිය"
						onClick={() => setActive({ kind: "final", field: "quotient" })}
					>
						{visibleFinalQuotient ?? "?"}
					</button>
				</label>
				<label>
					<span>ඉතිරිය</span>
					<button
						className={cellClass({ kind: "final", field: "remainder" })}
						data-cell-type="final-remainder"
						aria-label="අවසාන ඉතිරිය"
						onClick={() => setActive({ kind: "final", field: "remainder" })}
					>
						{visibleFinalRemainder ?? "?"}
					</button>
				</label>
			</div>
			{!demoResponse && (
				<>
					<NumberPad
						onDigit={(digit) => write(digit)}
						onClear={() => write(0, true)}
						disabled={!active}
					/>
					<button
						className="paper-next-cell"
						disabled={!active}
						onClick={() => active && setActive(nextCell(active))}
					>
						ඊළඟ කොටුව →
					</button>
				</>
			)}
		</section>
	);
}

function StoryDivisionActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const dividend = Number(game.dividend),
		divisor = Number(game.divisor);
	const [expression, setExpression] = useState<[number | null, number | null]>([
		null,
		null,
	]);
	const [selectedExpression, setSelectedExpression] = useState<0 | 1>(0);
	const [written, setWritten] = useState<WrittenDivisionResponse | null>(null);
	const [context, setContext] = useState<[number | null, number | null]>([
		null,
		null,
	]);
	const [selectedContext, setSelectedContext] = useState<0 | 1>(0);
	useEffect(() => {
		if (
			!written ||
			expression[0] === null ||
			expression[1] === null ||
			context[0] === null ||
			context[1] === null
		) {
			onResponse(null);
			return;
		}
		const { kind: _kind, ...writtenWorking } = written;
		onResponse({
			kind: "division_story",
			problem_id: String(game.story_id),
			dividend: expression[0],
			divisor: expression[1],
			written_working: writtenWorking,
			quotient: context[0],
			remainder: context[1],
			contextual_interpretation: contextualRemainderInterpretation(
				context[0],
				context[1],
			),
		});
	}, [context, expression, game.story_id, onResponse, written]);
	const expressionReady = expression[0] !== null && expression[1] !== null;
	const storyObjects = Array.from(
		{ length: dividend },
		(_, value) => value + 1,
	);
	return (
		<section className="division-story">
			<img
				className="story-asset"
				src="/curriculum/game/G5-AREA-MAT-08/story-ball.png"
				alt=""
			/>
			<ol className="story-sequence">
				<li className="active">කතාව</li>
				<li className={expressionReady ? "active" : ""}>බෙදීමේ ප්‍රකාශය</li>
				<li className={written ? "active" : ""}>කඩදාසි ක්‍රමය</li>
				<li
					className={context[0] !== null && context[1] !== null ? "active" : ""}
				>
					පිළිතුර
				</li>
			</ol>
			<div className="story-objects" aria-hidden="true">
				{storyObjects.map((marker) => (
					<i key={`story-object-${marker}`}>●</i>
				))}
			</div>
			<div className="story-expression">
				<button
					className={selectedExpression === 0 ? "selected" : ""}
					aria-label="බෙදිය යුතු සංඛ්‍යාව"
					onClick={() => setSelectedExpression(0)}
				>
					{expression[0] ?? "?"}
				</button>
				<strong>÷</strong>
				<button
					className={selectedExpression === 1 ? "selected" : ""}
					aria-label="බෙදුම"
					onClick={() => setSelectedExpression(1)}
				>
					{expression[1] ?? "?"}
				</button>
			</div>
			<div className="story-number-tiles">
				<button
					onClick={() => {
						const next: [number | null, number | null] = [...expression];
						next[selectedExpression] = dividend;
						setExpression(next);
						setSelectedExpression(1);
					}}
				>
					{dividend}
				</button>
				<button
					onClick={() => {
						const next: [number | null, number | null] = [...expression];
						next[selectedExpression] = divisor;
						setExpression(next);
					}}
				>
					{divisor}
				</button>
			</div>
			{expressionReady && (
				<LongDivisionWorkspace
					dividend={dividend}
					divisor={divisor}
					stepCount={Number(game.step_count)}
					onComplete={setWritten}
				/>
			)}
			{written && (
				<>
					<div className="context-answer">
						<label>
							සම්පූර්ණ කූඩ{" "}
							<button
								className={selectedContext === 0 ? "selected" : ""}
								aria-label="සම්පූර්ණ කූඩ ගණන"
								onClick={() => setSelectedContext(0)}
							>
								{context[0] ?? "?"}
							</button>
						</label>
						<label>
							ඉතිරි පලතුරු{" "}
							<button
								className={selectedContext === 1 ? "selected" : ""}
								aria-label="ඉතිරි පලතුරු ගණන"
								onClick={() => setSelectedContext(1)}
							>
								{context[1] ?? "?"}
							</button>
						</label>
					</div>
					<NumberPad
						onDigit={(digit) => {
							const next: [number | null, number | null] = [...context];
							next[selectedContext] = digit;
							setContext(next);
						}}
						onClear={() => {
							const next: [number | null, number | null] = [...context];
							next[selectedContext] = null;
							setContext(next);
						}}
					/>
				</>
			)}
		</section>
	);
}

export function DivisionActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	if (game.response_kind === "equal_sharing")
		return (
			<EqualSharingActivity
				dividend={Number(game.dividend)}
				divisor={Number(game.divisor)}
				onResponse={onResponse}
			/>
		);
	if (game.response_kind === "division_story")
		return <StoryDivisionActivity game={game} onResponse={onResponse} />;
	return (
		<LongDivisionWorkspace
			dividend={Number(game.dividend)}
			divisor={Number(game.divisor)}
			stepCount={Number(game.step_count)}
			traceLimit={
				game.trace_limit === undefined ? undefined : Number(game.trace_limit)
			}
			onComplete={onResponse}
		/>
	);
}

type WorkedExample = {
	prompt_si?: string;
	game?: Record<string, unknown>;
	correct_response?: ConstructedResponse | null;
	steps_si?: string[];
};

export function DivisionWorkedDemo({
	example,
	stage,
	focusStep = 0,
}: {
	example?: WorkedExample;
	stage: number;
	focusStep?: number;
}) {
	const game = example?.game ?? {};
	const answer = example?.correct_response;
	if (stage === 0 || !answer)
		return (
			<div className="division-cue-demo">
				<span aria-hidden="true">↓</span>
				<strong>ඉස්මතු කළ ඊළඟ කොටුව තෝරන්න. අගය තවම නොපෙන්වයි.</strong>
				{game.response_kind !== "equal_sharing" && (
					<LongDivisionWorkspace
						dividend={Number(game.dividend)}
						divisor={Number(game.divisor)}
						stepCount={Number(game.step_count)}
						traceLimit={
							game.trace_limit === undefined
								? undefined
								: Number(game.trace_limit)
						}
						cueOnly
						cueStep={focusStep}
					/>
				)}
			</div>
		);
	if (answer.kind === "equal_sharing")
		return (
			<div className="sharing-demo" role="img" aria-label="සමාන බෙදීමේ විසඳුම">
				{answer.group_quantities
					.map((count, position) => ({
						count,
						position,
						id: `demo-sharing-group-${position + 1}`,
					}))
					.map((group) => (
						<div key={group.id}>
							<strong>{group.position + 1} කණ්ඩායම</strong>
							<span>{group.count}</span>
						</div>
					))}
				{stage >= 2 && (
					<strong>
						{answer.dividend} ÷ {answer.divisor} = {answer.quotient}
					</strong>
				)}
			</div>
		);
	if (answer.kind !== "written_division" && answer.kind !== "division_story")
		return null;
	const written =
		answer.kind === "written_division"
			? answer
			: { kind: "written_division" as const, ...answer.written_working };
	const totalWorkedSteps = Number(game.trace_limit ?? game.step_count);
	const revealedWorkedSteps =
		stage >= 3 ? totalWorkedSteps : Math.max(0, stage - 1);
	return (
		<div className="division-worked-demo">
			<LongDivisionWorkspace
				dividend={written.dividend}
				divisor={written.divisor}
				stepCount={Number(game.step_count)}
				traceLimit={
					game.trace_limit === undefined ? undefined : Number(game.trace_limit)
				}
				demoResponse={written}
				revealSteps={revealedWorkedSteps}
			/>
			{stage > 0 &&
				written.working_steps
					.slice(0, Math.max(1, revealedWorkedSteps))
					.map((row) => (
						<p className="worked-equation" key={row.step_index}>
							{row.quotient_digit} × {written.divisor} = {row.partial_product} ·{" "}
							{row.partial_dividend} − {row.partial_product} ={" "}
							{row.subtraction_result}
						</p>
					))}
			{answer.kind === "division_story" && stage >= 3 && (
				<p className="context-explanation">
					සම්පූර්ණ කූඩ {answer.quotient}යි. ඉතිරි පලතුරු {answer.remainder}යි.
				</p>
			)}
		</div>
	);
}

function DivisionSupport({
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
	const manifest = support.game_manifest;
	if (manifest.schema_version !== "division-adventure-support-v1") return null;
	const required = Number(manifest.required_actions);
	return (
		<section className="division-support">
			<p>{support.title_si}</p>
			<h2>{manifest.worked_example.prompt_si}</h2>
			<DivisionWorkedDemo
				example={manifest.worked_example}
				stage={stage}
				focusStep={manifest.focus_step_index}
			/>
			<ol>
				{manifest.worked_example.steps_si.map((text, index) => (
					<li className={index < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="division-primary"
				onClick={stage < required ? onNext : onComplete}
			>
				{stage < required ? "ඊළඟ පියවර" : "දැන් තනිව කරමි"}
			</button>
		</section>
	);
}
