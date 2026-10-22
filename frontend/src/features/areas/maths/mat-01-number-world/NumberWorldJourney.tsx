import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	AdaptiveSupportActivity,
	SUPPORT_TYPE_LABELS,
} from "../../../mobile-learning-flow/AdaptiveSupportActivity";
import {
	AdventureProgress,
	type AdventureProgressStage,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	AdventureNotice,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	NumberWorldWorkedExample,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	NUMBER_WORLD_ASSET_ROOT,
	NUMBER_WORLD_GAMES,
	NUMBER_WORLD_SKILLS,
	type NumberWorldChapter,
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
	leadingZeroAttempts: number;
	firstActionMs: number | null;
};

export function NumberWorldJourney({
	api,
	learnerId,
	condition,
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
	const [step, setStep] = useState<Step>("chapters");
	const [chapter, setChapter] = useState<NumberWorldChapter | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [evidence, setEvidence] = useState<Evidence>({
		moves: 0,
		corrections: 0,
		leadingZeroAttempts: 0,
		firstActionMs: null,
	});
	const [startedAt, setStartedAt] = useState(0);
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState("");
	const [answeredCorrectly, setAnsweredCorrectly] = useState(false);
	const [activeSkillId, setActiveSkillId] = useState<string | null>(null);
	const [activeGameIndex, setActiveGameIndex] = useState<number | null>(null);
	const [activeChallengeIndex, setActiveChallengeIndex] = useState(0);
	const [failedAttempts, setFailedAttempts] = useState<Record<string, number>>(
		{},
	);
	const [supportActions, setSupportActions] = useState(0);
	const [supportComplete, setSupportComplete] = useState(false);
	const requestSequence = useRef(0);
	const requestInFlight = useRef(false);
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{
		episodeId: string;
		requestId: string;
		supportRevisionId: string;
		manifestRevisionId: string;
	} | null>(null);
	const progressStage = Math.min(
		4,
		(activeGameIndex ?? 0) +
			1 +
			(step === "result" && answeredCorrectly ? 1 : 0),
	) as AdventureProgressStage;

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
			setResponse(null);
			setEvidence({
				moves: 0,
				corrections: 0,
				leadingZeroAttempts: 0,
				firstActionMs: null,
			});
			setStartedAt(Date.now());
			setPendingWithdrawal(null);
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pendingWithdrawal, run, step]);

	const openChallenge = async (gameIndex: number, challengeIndex: number) => {
		const game = NUMBER_WORLD_GAMES[gameIndex];
		const skillId = game?.skillIds[challengeIndex];
		const skill = NUMBER_WORLD_SKILLS.find((item) => item.id === skillId);
		if (!game || !skill) return;
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
					area_id: "G5-AREA-MAT-01",
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		if (!opened) return;
		setActiveGameIndex(gameIndex);
		setActiveChallengeIndex(challengeIndex);
		setChapter(skill.chapter);
		setEpisodeId(opened.episode_id);
		setActiveSkillId(skillId);
		setManifest(opened.manifest);
		setSupport(null);
		setAnsweredCorrectly(false);
		setMessage("");
		setResponse(null);
		setStartedAt(Date.now());
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
			leadingZeroAttempts:
				current.leadingZeroAttempts + (change.leadingZeroAttempts ?? 0),
			firstActionMs:
				current.firstActionMs ?? Math.max(0, Date.now() - startedAt),
		}));
	};

	const confirm = async () => {
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
				first_action_ms: evidence.firstActionMs ?? 0,
				active_time_ms: Math.max(0, Date.now() - startedAt),
				leading_zero_attempts: evidence.leadingZeroAttempts,
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
		if (activeSkillId) {
			setFailedAttempts((current) => {
				const updated = { ...current };
				if (correct) delete updated[activeSkillId];
				else if (manifest.measurement_role === "unsupported_after") {
					updated[activeSkillId] = (updated[activeSkillId] ?? 0) + 1;
				}
				return updated;
			});
		}
		setAnsweredCorrectly(correct);
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
		}
		if (correct && !next.support && activeGameIndex !== null) {
			setResponse(null);
			const challengeCount =
				NUMBER_WORLD_GAMES[activeGameIndex].skillIds.length;
			if (activeChallengeIndex + 1 < challengeCount) {
				await openChallenge(activeGameIndex, activeChallengeIndex + 1);
				return;
			}
			setMessage(
				activeGameIndex === NUMBER_WORLD_GAMES.length - 1
					? "ක්‍රීඩා තුනම සම්පූර්ණයි!"
					: `ක්‍රීඩාව ${activeGameIndex + 1} සම්පූර්ණයි!`,
			);
			setStep("result");
			return;
		}
		setMessage("නැවත බලමු.");
		setStep("feedback");
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
		if (activeGameIndex === null) {
			setStep("chapters");
			return;
		}
		const nextGame = activeGameIndex + 1;
		if (!NUMBER_WORLD_GAMES[nextGame]) {
			setStep("chapters");
			return;
		}
		void openChallenge(nextGame, 0);
	};
	const retryCurrentGame = () => {
		if (activeGameIndex !== null)
			void openChallenge(activeGameIndex, activeChallengeIndex);
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
					duration_ms: 1_000,
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
		advanceSupport(completed);
	};

	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) {
			setPendingWithdrawal({
				episodeId: next.episode_id,
				requestId: crypto.randomUUID(),
				supportRevisionId: next.support_round.support_revision_id,
				manifestRevisionId: next.support_round.manifest_revision_id,
			});
			setSupport(null);
			setStep("withdrawing");
			return;
		}
		if (next.support) {
			setSupport(next.support);
			setResponse(null);
			setStartedAt(Date.now());
		}
	};

	const answerSupport = async () => {
		const submitSupported = api.answerSupported;
		if (!episodeId || !support || !response || !submitSupported) return;
		const game = support.game_manifest;
		if (game.schema_version !== "support-round-v1" || !game.activity) return;
		const activity = game.activity;
		const next = await run(() =>
			submitSupported(
				episodeId,
				{
					constructed_response: {
						...response,
						presentation_id: activity.presentation_id,
						item_revision_id: activity.revision_id,
						interaction_version: "constructed-response-v1",
					},
					response_time_ms: Math.max(0, Date.now() - startedAt),
					interaction_summary: { move_count: evidence.moves },
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceSupport(next);
	};

	return (
		<section
			className="learning-adventure number-world"
			data-number-world-step={step}
			data-episode-id={episodeId ?? undefined}
		>
			<header className="adventure-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>සංඛ්‍යා</h1>
			</header>
			{step === "chapters" && (
				<div className="adventure-cards">
					{NUMBER_WORLD_GAMES.map((item, index) => (
						<button
							type="button"
							key={item.id}
							disabled={busy}
							style={
								{
									"--card-tone": ["#32A9E6", "#54CBAB", "#F47FA5", "#57558F"][
										index
									],
								} as React.CSSProperties
							}
							onClick={() => void openChallenge(index, 0)}
						>
							<img
								src={item.asset}
								alt=""
								onError={(event) => {
									event.currentTarget.hidden = true;
								}}
							/>
							<span>
								<strong>{item.title}</strong>
								<small>
									අභියෝග {item.skillIds.length}ක් · {item.difficulty}
								</small>
							</span>
						</button>
					))}
				</div>
			)}
			{(step === "question" || step === "feedback") && manifest && chapter && (
				<div className="adventure-play game-play-surface">
					<AdventureProgress stage={progressStage} />
					<p className="game-round-label">
						ක්‍රීඩාව {(activeGameIndex ?? 0) + 1} · අභියෝගය{" "}
						{activeChallengeIndex + 1}/
						{activeGameIndex === null
							? 0
							: NUMBER_WORLD_GAMES[activeGameIndex].skillIds.length}
					</p>
					<h2>{manifest.prompt_si}</h2>
					<div
						aria-disabled={step === "feedback"}
						style={step === "feedback" ? { pointerEvents: "none" } : undefined}
					>
						<NumberManipulation
							key={manifest.revision_id}
							chapter={chapter}
							game={manifest.game ?? {}}
							onChange={record}
						/>
					</div>
					{step === "feedback" && !answeredCorrectly && (
						<h3 role="status">{message}</h3>
					)}
					<button
						type="button"
						className="primary-action"
						disabled={step === "question" && (!response || busy)}
						onClick={step === "feedback" ? advanceFeedback : confirm}
					>
						{step === "feedback"
							? support
								? "උදව්ව බලන්න"
								: "ප්‍රතිඵලය බලන්න"
							: "තහවුරු කරන්න"}
					</button>
				</div>
			)}
			{step === "support" && support && chapter && (
				<div
					className="adventure-play game-play-surface"
					data-support-visible="true"
				>
					<AdventureProgress stage={progressStage} />
					{support.game_manifest.schema_version === "support-round-v1" ? (
						<SupportRoundFrame
							support={support}
							busy={busy}
							onViewComplete={() => void finishSupport()}
							renderActivity={(activity) => (
								<NumberManipulation
									key={activity.revision_id}
									chapter={activity.game.chapter as NumberWorldChapter}
									game={activity.game}
									onChange={record}
								/>
							)}
						>
							{support.game_manifest.stage_kind !== "view" && (
								<button
									type="button"
									className="primary-action"
									disabled={busy || !response}
									onClick={() => void answerSupport()}
								>
									තහවුරු කරන්න
								</button>
							)}
						</SupportRoundFrame>
					) : (
						<>
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
							{support.game_manifest.schema_version !==
								"half-set-manifest-v1" &&
								support.game_manifest.schema_version !==
									"classroom-action-support-v1" && (
									<AdaptiveSupportActivity
										manifest={support.game_manifest}
										renderNumberWorldExample={(example, actions) => (
											<NumberWorldSupportReplica
												example={example}
												actions={actions}
											/>
										)}
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
						</>
					)}
				</div>
			)}
			{step === "withdrawing" && (
				<div className="adventure-result" role="status">
					<AdventureProgress stage={progressStage} />
					<h2>උදව් සම්පූර්ණයෙන් ඉවත් කරමින්…</h2>
					<p>අලුත් ස්වාධීන ක්‍රියාව සූදානම් කරමු.</p>
				</div>
			)}
			{step === "result" &&
				(answeredCorrectly && activeGameIndex !== null ? (
					<GameSuccessScreen
						gameNumber={activeGameIndex + 1}
						gameCount={NUMBER_WORLD_GAMES.length}
						onContinue={openNextGame}
					/>
				) : (
					<div className="adventure-result" data-answer-result="incorrect">
						<AdventureProgress stage={progressStage} />
						<h2>{message}</h2>
						<p>තවම නිවැරදි නැහැ. වෙනස් උදව්වක් සමඟ නැවත උත්සාහ කරමු.</p>
						<button
							type="button"
							className="primary-action"
							onClick={retryCurrentGame}
						>
							නැවත උත්සාහ කරන්න
						</button>
					</div>
				))}
		</section>
	);
}

function NumberManipulation({
	chapter,
	game,
	onChange,
}: {
	chapter: NumberWorldChapter;
	game: Record<string, unknown>;
	onChange(
		response: ConstructedResponse | null,
		evidence?: Partial<Evidence>,
	): void;
}) {
	const skill = String(game.skill_id ?? "");
	if (skill.endsWith("EXPAND-01"))
		return <ExpandedTable game={game} onChange={onChange} />;
	if (skill.endsWith("ABACUS-01") || chapter === "firefly_abacus")
		return <Abacus game={game} onChange={onChange} />;
	if (chapter === "place_value_harbour")
		return <Harbour game={game} onChange={onChange} />;
	if (chapter === "kite_workshop")
		return <Kite game={game} onChange={onChange} />;
	return <River game={game} onChange={onChange} />;
}

function correctNumberWorldAnswer(response: ConstructedResponse): string {
	switch (response.kind) {
		case "drag_to_slot":
			return response.represented_value !== undefined
				? formatPlaceValue(response.represented_value)
				: placeLabels[5 - (response.selected_place ?? 0)];
		case "constructed_number":
			return formatPlaceValue(response.constructed_number);
		case "bead_placement":
			return formatPlaceValue(Number(response.rods.join("")));
		case "expanded_form":
			return response.terms.map(formatPlaceValue).join(" + ");
		case "digit_order":
			return response.digits.join("");
		case "number_order":
			return response.order.map(formatPlaceValue).join(" → ");
		default:
			return "නිවැරදි පිළිතුර පෙන්වා ඇත.";
	}
}

function NumberWorldSupportReplica({
	example,
	actions,
}: {
	example: NumberWorldWorkedExample;
	actions: number;
}) {
	const [practiceResponse, setPracticeResponse] =
		useState<ConstructedResponse | null>(null);
	return (
		<div
			className="exact-worked-example number-world-support-replica"
			data-worked-example-mode={example.mode}
		>
			<p className="worked-same-question">ඔබට වැරදුණු එම ප්‍රශ්නය</p>
			<h4>{example.prompt_si}</h4>
			<div className="support-question-replica">
				<NumberManipulation
					chapter={example.game.chapter}
					game={example.game}
					onChange={setPracticeResponse}
				/>
			</div>
			<ol className="worked-steps" aria-live="polite">
				{example.steps_si.map((step, index) => (
					<li
						className={
							actions > index
								? "is-done"
								: actions === index
									? "is-current"
									: ""
						}
						key={step}
					>
						<span>{index + 1}</span>
						{step}
					</li>
				))}
			</ol>
			{actions >= 3 && (
				<p className="worked-answer support-correct-answer" role="status">
					නිවැරදි පිළිතුර: {correctNumberWorldAnswer(example.correct_response)}
				</p>
			)}
			{practiceResponse && actions < 3 && (
				<p className="support-practice-note" aria-live="polite">
					හොඳයි—දැන් පහත මඟ පෙන්වීමෙන් ඊළඟ පියවර බලන්න.
				</p>
			)}
		</div>
	);
}

const placeLabels = ["ලක්ෂ", "දස දහස්", "දහස්", "සිය", "දහය", "එක"];
const placePowers = [100_000, 10_000, 1_000, 100, 10, 1];
const abacusBeadSlots = [
	"bead-1",
	"bead-2",
	"bead-3",
	"bead-4",
	"bead-5",
	"bead-6",
	"bead-7",
	"bead-8",
	"bead-9",
];
function formatPlaceValue(value: number) {
	return value.toLocaleString("en-US").replaceAll(",", " ");
}

export function Harbour({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse): void;
}) {
	const skill = String(game.skill_id);
	const number = Number(game.number ?? 0);
	const digit = Number(game.digit ?? 1);
	const [selectedPlace, setSelectedPlace] = useState<number | null>(null);
	const [value, setValue] = useState(0);
	const choose = (visualIndex: number) => {
		const place = 5 - visualIndex;
		setSelectedPlace(place);
		onChange(
			skill.endsWith("REPRESENTED-01")
				? { kind: "drag_to_slot", represented_value: digit * 10 ** place }
				: { kind: "drag_to_slot", selected_place: place },
		);
	};
	if (skill.endsWith("100000-01")) {
		// The server sends the number one below a round milestone (39 999, 7 999, 99 999, or a
		// shorter one in the simpler version); the ladder climbs to it.
		const base = Number(game.milestone_base ?? 99_999);
		const choices = Array.isArray(game.milestone_choices)
			? game.milestone_choices.map(Number)
			: [10_000, 100_000, 1_000_000];
		const spaced = (n: number) =>
			n.toLocaleString("en-US").replaceAll(",", " ");
		// The ladder climbs in the same pattern as the question: for 59 999 it shows
		// 59 + 1 = 60, 599 + 1 = 600, 5 999 + 1 = 6 000, then asks 59 999 + 1.
		const target = base + 1;
		let zeros = 0;
		while (target % 10 ** (zeros + 1) === 0) zeros += 1;
		const lead = target / 10 ** zeros;
		const rungs: number[] = [];
		for (let place = 1; place < zeros; place += 1)
			rungs.push(lead * 10 ** place - 1);
		return (
			<div className="manipulation-board milestone-builder">
				<p className="milestone-instruction">එක් එක් පේළියේ 1ක් එකතු වන රටාව බලන්න.</p>
				<div className="milestone-ladder">
					{rungs.map((rung) => (
						<span key={rung}>
							{spaced(rung)} + 1 = {spaced(rung + 1)}
						</span>
					))}
					<strong>{spaced(base)} + 1 = ?</strong>
				</div>
				<p>නිවැරදි පිළිතුර තෝරන්න.</p>
				<div className="milestone-options">
					{choices.map((option) => (
						<button
							type="button"
							key={option}
							className={value === option ? "is-selected" : undefined}
							aria-pressed={value === option}
							onClick={() => {
								setValue(option);
								onChange({
									kind: "constructed_number",
									constructed_number: option,
								});
							}}
						>
							{spaced(option)}
						</button>
					))}
				</div>
			</div>
		);
	}
	const rawNumber = String(number);
	const targetDigitIndex = rawNumber.indexOf(String(digit));
	let digitIndex = -1;
	const characterOccurrences = new Map<string, number>();
	const formattedNumber = number
		.toLocaleString("en-US")
		.split("")
		.map((character) => {
			const isDigit = /\d/.test(character);
			if (isDigit) digitIndex += 1;
			const occurrence = (characterOccurrences.get(character) ?? 0) + 1;
			characterOccurrences.set(character, occurrence);
			return {
				id: `${character}-${occurrence}`,
				character,
				isTarget: isDigit && digitIndex === targetDigitIndex,
			};
		});
	const selectedVisualIndex = selectedPlace === null ? null : 5 - selectedPlace;
	const selectedPower = selectedPlace === null ? null : 10 ** selectedPlace;
	const isRepresentedValue = skill.endsWith("REPRESENTED-01");
	return (
		<div className="manipulation-board harbour-board place-value-board">
			<div className="place-value-question-number">
				<span>සංඛ්‍යාව</span>
				<strong data-question-number={number}>
					{formattedNumber.map((part) => (
						<span
							key={part.id}
							className={part.isTarget ? "is-target-digit" : undefined}
						>
							{part.character}
						</span>
					))}
				</strong>
			</div>
			<div className="place-value-target">
				<span>තබන්න ඕනෑ ඉලක්කම</span>
				<strong
					className="target-digit-tile"
					draggable
					role="img"
					aria-label={`${digit} ඉලක්කම`}
					onDragStart={(event) =>
						event.dataTransfer.setData("text/plain", String(digit))
					}
				>
					{digit}
				</strong>
			</div>
			<div className="place-value-table-frame">
				<table className="place-value-table">
					<caption className="sr-only">ඉලක්කම තැබීමට ස්ථානීය අගය වගුව</caption>
					<thead>
						<tr>
							{placeLabels.map((label, index) => (
								<th scope="col" key={label}>
									<span className="place-value-heading-label">{label}</span>
									<small className="place-value-heading-power">
										{formatPlaceValue(placePowers[index])}
									</small>
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						<tr>
							{placeLabels.map((label, index) => (
								<td
									key={label}
									className={
										selectedVisualIndex === index ? "is-selected" : undefined
									}
								>
									<button
										type="button"
										className="place-value-cell-button"
										aria-label={`${digit} ඉලක්කම ${label} ස්ථානයට තබන්න`}
										aria-pressed={selectedVisualIndex === index}
										onDragOver={(event) => event.preventDefault()}
										onDrop={() => choose(index)}
										onClick={() => choose(index)}
									>
										{selectedVisualIndex === index ? digit : "?"}
									</button>
								</td>
							))}
						</tr>
					</tbody>
				</table>
			</div>
			{selectedPlace === null || selectedPower === null ? (
				<p className="place-value-selection-hint">ඉලක්කම තැබීමට තීරුවක් තෝරන්න.</p>
			) : (
				<div
					className="place-value-selection-summary"
					data-selected-place={selectedPlace}
					aria-live="polite"
				>
					<span className="place-value-summary-label">ඔබ තෝරාගත් පිළිතුර</span>
					<strong className="place-value-summary-value">
						{isRepresentedValue
							? `${digit} × ${formatPlaceValue(selectedPower)} = ${formatPlaceValue(digit * selectedPower)}`
							: `${placeLabels[5 - selectedPlace]} — ${formatPlaceValue(selectedPower)}`}
					</strong>
				</div>
			)}
		</div>
	);
}

export function ExpandedTable({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse | null): void;
}) {
	const number = Number(game.number ?? 0);
	const [digits, setDigits] = useState<number[]>([0, 0, 0, 0, 0, 0]);
	const [started, setStarted] = useState(false);
	useEffect(() => {
		if (!Number.isFinite(number)) return;
		setDigits([0, 0, 0, 0, 0, 0]);
		setStarted(false);
	}, [number]);
	const update = (index: number, delta: number) => {
		const next = digits.map((value, at) =>
			at === index ? Math.max(0, Math.min(9, value + delta)) : value,
		);
		setDigits(next);
		setStarted(true);
		const terms = next
			.map((digit, at) => digit * 10 ** (placeLabels.length - at - 1))
			.filter((value) => value > 0);
		onChange({ kind: "expanded_form", terms: terms.length ? terms : [0] });
	};
	const terms = digits
		.map((digit, index) => digit * 10 ** (placeLabels.length - index - 1))
		.filter((value) => value > 0);
	return (
		<div className="manipulation-board expanded-form-board">
			<p className="expanded-question-number">
				සංඛ්‍යාව <strong>{formatPlaceValue(number)}</strong>
			</p>
			<table className="expanded-place-table">
				<caption className="sr-only">ස්ථානීය අගය වගුවෙන් විහිදුවීම</caption>
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
					<tr>
						{placeLabels.map((label, index) => (
							<td key={label}>
								<div className="expanded-column">
									<button
										type="button"
										className="expanded-step-button expanded-step-button--increment"
										aria-label={`${label} තැනට එකක් එකතු කරන්න`}
										onClick={() => update(index, 1)}
										disabled={digits[index] === 9}
									>
										+
									</button>
									<strong>{started ? digits[index] : "?"}</strong>
									<button
										type="button"
										className="expanded-step-button expanded-step-button--decrement"
										aria-label={`${label} තැනින් එකක් ඉවත් කරන්න`}
										onClick={() => update(index, -1)}
										disabled={!started || digits[index] === 0}
									>
										−
									</button>
								</div>
							</td>
						))}
					</tr>
				</tbody>
			</table>
			<p className="expanded-strip" data-expanded-terms={terms.join("+")}>
				විහිදුණු ආකාරය:{" "}
				{terms.length ? terms.map(formatPlaceValue).join(" + ") : "…"}
			</p>
		</div>
	);
}

export function Abacus({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse): void;
}) {
	const target = typeof game.number === "number" ? game.number : null;
	const [rods, setRods] = useState([0, 0, 0, 0, 0, 0]);
	const constructedNumber = Number(rods.join(""));
	const expanded = rods
		.map((digit, index) => digit * 10 ** (5 - index))
		.filter(Boolean)
		.join(" + ");
	const update = (index: number, delta: number) => {
		const next = rods.map((value, at) =>
			at === index ? Math.max(0, Math.min(9, value + delta)) : value,
		);
		if (next[index] === rods[index]) return;
		setRods(next);
		onChange({ kind: "bead_placement", rods: next });
	};
	return (
		<div className="manipulation-board abacus-board">
			<div className="abacus-readout" aria-live="polite">
				{target !== null && (
					<span className="abacus-target">
						සාදන්න ඕන සංඛ්‍යාව: {formatPlaceValue(target)}
					</span>
				)}
				<span>ගොඩනැගුණු සංඛ්‍යාව</span>
				<strong data-abacus-number={constructedNumber}>
					{constructedNumber.toLocaleString("en-US")}
				</strong>
				<small data-abacus-expanded={expanded || "0"}>
					විහිදුණු ආකාරය: {expanded || "0"}
				</small>
			</div>
			<div className="abacus-visual">
				<img
					className="abacus-frame"
					src={`${NUMBER_WORLD_ASSET_ROOT}/abacus-frame.png`}
					alt=""
				/>
				<div className="abacus-bead-grid" aria-hidden="true">
					{rods.map((count, rodIndex) => (
						<div className="abacus-frame-rod" key={placeLabels[rodIndex]}>
							{abacusBeadSlots.slice(0, count).map((beadId, beadIndex) => (
								<img
									key={beadId}
									className="abacus-bead"
									src={`${NUMBER_WORLD_ASSET_ROOT}/firefly-bead.png`}
									alt=""
									style={
										{
											"--bead-offset": `${2 + beadIndex * 9}%`,
										} as React.CSSProperties
									}
								/>
							))}
						</div>
					))}
				</div>
			</div>
			<div className="abacus-place-labels" aria-hidden="true">
				{placeLabels.map((label) => (
					<span key={label}>{label}</span>
				))}
			</div>
			<div className="abacus-grid">
				{placeLabels.map((label, index) => (
					<div className="abacus-rod-control" key={label}>
						<span className="abacus-control-label">{label}</span>
						<div className="abacus-stepper">
							<button
								type="button"
								className="abacus-step-button abacus-step-button--decrement"
								onClick={() => update(index, -1)}
								disabled={rods[index] === 0}
								aria-label={`${label} තැනින් එකක් ඉවත් කරන්න`}
							>
								−
							</button>
							<strong>{rods[index]}</strong>
							<button
								type="button"
								className="abacus-step-button abacus-step-button--increment"
								onClick={() => update(index, 1)}
								disabled={rods[index] === 9}
								aria-label={`${label} තැනට එකක් එකතු කරන්න`}
							>
								+
							</button>
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

export function Kite({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(
		response: ConstructedResponse | null,
		evidence?: Partial<Evidence>,
	): void;
}) {
	const digitCards = useMemo(() => {
		const values = (game.digits as number[] | undefined) ?? [0, 2, 5, 7];
		return values.map((value, index) => ({ id: `${value}-${index}`, value }));
	}, [game.digits]);
	const digits = digitCards.map((card) => card.value);
	const greatest = Boolean(game.greatest);
	const activePlaceLabels = placeLabels.slice(-digits.length);
	const [available, setAvailable] = useState(digitCards);
	const [slots, setSlots] = useState<
		Array<{ id: string; value: number } | null>
	>(Array(digits.length).fill(null));
	const slotIds = digits.map((_, index) => `kite-slot-${index + 1}`);
	const [note, setNote] = useState("");
	useEffect(() => {
		setAvailable(digitCards);
		setSlots(Array(digits.length).fill(null));
		setNote("");
	}, [digitCards, digits.length]);
	const place = (id: string, slot: number) => {
		const patch = available.find((item) => item.id === id);
		if (!patch || slot < 0) return;
		if (slot === 0 && patch.value === 0) {
			setNote("ශූන්‍යය පළමු තැනට යොදන්න බැහැ—වෙනත් තැනක් තෝරන්න.");
			onChange(null, { leadingZeroAttempts: 1 });
			return;
		}
		const next = [...slots];
		if (next[slot]) return;
		next[slot] = patch;
		setSlots(next);
		setAvailable((items) => items.filter((item) => item.id !== id));
		setNote("");
		onChange(
			next.every(Boolean)
				? {
						kind: "digit_order",
						digits: next
							.map((item) => item?.value)
							.filter((value): value is number => value !== undefined),
					}
				: null,
		);
	};
	const remove = (slot: number) => {
		const patch = slots[slot];
		if (!patch) return;
		const next = [...slots];
		next[slot] = null;
		setSlots(next);
		setAvailable((items) => [...items, patch]);
		onChange(null, { corrections: 1 });
	};
	return (
		<div className="manipulation-board kite-board extreme-number-board">
			<div className="extreme-rule-card">
				<strong>{greatest ? "විශාලම" : "කුඩාම"} සංඛ්‍යාව සාදන්න</strong>
				<span>
					{greatest
						? "විශාල ඉලක්කම වම් පැත්තේ ඉහළ ස්ථානයට තබන්න."
						: "කුඩා ශූන්‍ය නොවන ඉලක්කම වම් පැත්තේ ඉහළ ස්ථානයට තබන්න."}
				</span>
			</div>
			<div className="extreme-construction">
				<div className="extreme-digit-source">
					<span>දී ඇති ඉලක්කම්</span>
					<div
						className={`extreme-digit-circle extreme-digit-circle--${digits.length}`}
					>
						{digitCards.map((patch) => {
							const isAvailable = available.some(
								(item) => item.id === patch.id,
							);
							return (
								<button
									type="button"
									key={patch.id}
									disabled={!isAvailable}
									aria-label={
										isAvailable
											? `${patch.value} ඉලක්කම තෝරන්න`
											: `${patch.value} ඉලක්කම තබා ඇත`
									}
									onClick={() => place(patch.id, slots.indexOf(null))}
								>
									{patch.value}
								</button>
							);
						})}
					</div>
				</div>
				<span className="extreme-arrow" aria-hidden="true">
					→
				</span>
				<div className="extreme-place-table-wrap">
					<table className="extreme-place-table">
						<caption className="sr-only">
							{greatest ? "විශාලම" : "කුඩාම"} සංඛ්‍යාව සෑදීමේ ස්ථානීය අගය වගුව
						</caption>
						<thead>
							<tr>
								{activePlaceLabels.map((label) => (
									<th key={label} scope="col">
										{label}
									</th>
								))}
							</tr>
						</thead>
						<tbody>
							<tr>
								{slotIds.map((slotId, index) => {
									const patch = slots[index];
									return (
										<td key={slotId}>
											<button
												type="button"
												aria-label={`${activePlaceLabels[index]} ස්ථානය${patch ? `, ${patch.value} ඉලක්කම ඉවත් කරන්න` : ""}`}
												onClick={() => remove(index)}
											>
												{patch?.value ?? "?"}
											</button>
										</td>
									);
								})}
							</tr>
						</tbody>
					</table>
				</div>
			</div>
			<AdventureNotice message={note} onDismiss={() => setNote("")} />
		</div>
	);
}

export function River({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(
		response: ConstructedResponse | null,
		evidence?: Partial<Evidence>,
	): void;
}) {
	const values = useMemo(
		() => (game.values as number[] | undefined) ?? [40105, 40015, 40150, 40051],
		[game.values],
	);
	const [bank, setBank] = useState(values);
	const [route, setRoute] = useState<number[]>([]);
	useEffect(() => {
		setBank(values);
		setRoute([]);
	}, [values]);
	const add = (value: number) => {
		if (!bank.includes(value)) return;
		const next = [...route, value];
		setRoute(next);
		setBank((items) => items.filter((item) => item !== value));
		onChange(
			next.length === values.length
				? { kind: "number_order", order: next }
				: null,
		);
	};
	const remove = (value: number) => {
		const next = route.filter((item) => item !== value);
		setRoute(next);
		setBank((items) => [...items, value]);
		onChange(null, { corrections: 1 });
	};
	return (
		<div className="manipulation-board river-board">
			<div className="river-direction-card">
				<span aria-hidden="true">{game.ascending ? "↗" : "↘"}</span>
				<strong>{game.ascending ? "කුඩා සිට විශාල දක්වා" : "විශාල සිට කුඩා දක්වා"}</strong>
			</div>
			<p className="river-instruction">අංක පුවරු තට්ටු කර මාර්ගය සම්පූර්ණ කරන්න.</p>
			<div className="river-bank">
				{values.map((value) => {
					const isAvailable = bank.includes(value);
					return (
						<button
							type="button"
							key={value}
							disabled={!isAvailable}
							aria-label={
								isAvailable ? `${value} මාර්ගයට එක් කරන්න` : `${value} මාර්ගයේ ඇත`
							}
							onClick={() => add(value)}
						>
							<img src={`${NUMBER_WORLD_ASSET_ROOT}/river-stone.png`} alt="" />
							<strong className="river-number-value">
								{value.toLocaleString("en-US")}
							</strong>
						</button>
					);
				})}
			</div>
			<div className="river-route-track">
				<img
					className="route-boat"
					src={`${NUMBER_WORLD_ASSET_ROOT}/route-boat.png`}
					alt=""
				/>
				<ol className="river-route" aria-label="සංඛ්‍යා මාර්ගය">
					{values.map((sourceValue, index) => {
						const value = route[index];
						return (
							<li key={`route-position-${sourceValue}`}>
								{value === undefined ? (
									<span
										className="river-route-position-number"
										aria-hidden="true"
									>
										{index + 1}
									</span>
								) : (
									<button
										type="button"
										aria-label={`${value} මාර්ගයෙන් ඉවත් කරන්න`}
										onClick={() => remove(value)}
									>
										{value.toLocaleString("en-US")}
									</button>
								)}
							</li>
						);
					})}
				</ol>
			</div>
		</div>
	);
}
