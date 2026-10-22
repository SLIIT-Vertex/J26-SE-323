// biome-ignore-all lint/suspicious/noArrayIndexKey: generated region and object positions are stable semantic identities.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
	ConstructedResponse,
	ChildEpisodeResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../../../mobile-learning-flow/AdventureProgress";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	FRACTION_GAMES,
	FRACTION_SKILLS,
	type FractionChapter,
} from "./manifest";
import {
	groupingResponse,
	quarterTableResponse,
	shadingResponse,
	tenthsResponse,
} from "./fractionLogic";
import "./fraction-adventure.css";

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
	firstActionMs: number | null;
};

export function FractionAdventureJourney({
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
	const [step, setStep] = useState<Step>("chapters");
	const [chapter, setChapter] = useState<FractionChapter | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [skillId, setSkillId] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [correct, setCorrect] = useState(false);
	const [supportActions, setSupportActions] = useState(0);
	const [startedAt, setStartedAt] = useState(0);
	const [evidence, setEvidence] = useState<Evidence>({
		moves: 0,
		corrections: 0,
		firstActionMs: null,
	});
	const [attempts, setAttempts] = useState<Record<string, number>>({});
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{
		episodeId: string;
		requestId: string;
		supportRevisionId: string;
		manifestRevisionId: string;
	} | null>(null);
	const inFlight = useRef(false);
	const skills = useMemo(
		() => FRACTION_SKILLS.filter((item) => item.chapter === chapter),
		[chapter],
	);
	const challengeIndex = Math.max(
		0,
		skills.findIndex((item) => item.id === skillId),
	);
	const chapterIndex = FRACTION_GAMES.findIndex((game) => game.id === chapter);
	const reset = useCallback(() => {
		setResponse(null);
		setEvidence({ moves: 0, corrections: 0, firstActionMs: null });
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
	const record = (next: ConstructedResponse, correction = false) => {
		setResponse(next);
		setEvidence((current) => ({
			moves: current.moves + 1,
			corrections: current.corrections + Number(correction),
			firstActionMs: current.firstActionMs ?? Date.now() - startedAt,
		}));
	};

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
			setSupport(null);
			setManifest(next.manifest);
			setPendingWithdrawal(null);
			reset();
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pendingWithdrawal, reset, run, step]);

	const openSkill = async (nextSkill: string, nextChapter: FractionChapter) => {
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
					area_id: "G5-AREA-MAT-05",
					atomic_skill_id: nextSkill,
				},
				crypto.randomUUID(),
			),
		);
		inFlight.current = false;
		if (!opened) return;
		setChapter(nextChapter);
		setSkillId(nextSkill);
		setEpisodeId(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setCorrect(false);
		reset();
		setStep("question");
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
			response_time_ms: Date.now() - startedAt,
			interaction_summary: {
				move_count: evidence.moves,
				correction_count: evidence.corrections,
				first_action_ms: evidence.firstActionMs ?? 0,
				active_time_ms: Date.now() - startedAt,
				attempt_count: (skillId ? (attempts[skillId] ?? 0) : 0) + 1,
				evidence_quality: 0.8,
				all_objects_placed:
					response.kind !== "equal_grouping" ||
					!response.assignments.includes(-1),
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
		if (!isCorrect && skillId)
			setAttempts((current) => ({
				...current,
				[skillId]: (current[skillId] ?? 0) + 1,
			}));
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportActions(0);
			setStep("support");
		} else setStep("feedback");
	};

	const finishSupport = async () => {
		if (
			!episodeId ||
			!manifest ||
			!support ||
			(support.game_manifest.schema_version !== "support-round-v1" && supportActions <
				Number(
					(support.game_manifest as { required_actions?: number })
						.required_actions ?? 1,
				))
		)
			return;
		const completed = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Date.now() - startedAt,
					steps_viewed: Math.min(8, Math.max(1, supportActions)),
					manifest_revision_id: support.game_manifest.revision_id,
					interaction_summary: {
						action_count: supportActions,
						exact_failed_activity: true,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (completed) advanceSupport(completed);
	};
	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) { setPendingWithdrawal({ episodeId: next.episode_id, requestId: crypto.randomUUID(), supportRevisionId: next.support_round.support_revision_id, manifestRevisionId: next.support_round.manifest_revision_id }); setResponse(null); setSupport(null); setStep("withdrawing"); return; }
		if (next.support) { setSupport(next.support); reset(); setStep("support"); }
	};
	const answerSupport = async () => {
		const submit = api.answerSupported; const game = support?.game_manifest;
		if (!submit || !episodeId || !response || !game || game.schema_version !== "support-round-v1" || !game.activity) return; const activity = game.activity;
		const next = await run(() => submit(episodeId, { constructed_response: { ...response, presentation_id: activity.presentation_id, item_revision_id: activity.revision_id, interaction_version: "constructed-response-v1" }, response_time_ms: Math.max(0, Date.now() - startedAt), interaction_summary: { move_count: evidence.moves } }, crypto.randomUUID()));
		if (next) advanceSupport(next);
	};

	const continueAfterFeedback = () => {
		if (!correct || !chapter) {
			reset();
			setStep("question");
			return;
		}
		if (challengeIndex + 1 < skills.length)
			void openSkill(skills[challengeIndex + 1].id, chapter);
		else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) continueAfterFeedback();
	}, [step, correct]);

	return (
		<main
			className="fraction-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="fraction-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>භාග</h1>
			</header>
			{step === "chapters" ? (
				<section className="fraction-game-list" aria-label="භාග ක්‍රීඩා">
					{FRACTION_GAMES.map((game) => (
						<button
							type="button"
							className="fraction-game-card"
							key={game.id}
							onClick={() => {
								const first = FRACTION_SKILLS.find(
									(item) => item.chapter === game.id,
								);
								if (first) void openSkill(first.id, game.id);
							}}
						>
							<img src={game.asset} alt="" />
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
				<section className="fraction-play-shell game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
					/>
					{chapter && (
						<p className="fraction-position">
							ක්‍රීඩාව {chapterIndex + 1} · අභියෝගය {challengeIndex + 1}/
							{skills.length}
						</p>
					)}
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<FractionActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="fraction-primary"
								type="button"
								disabled={busy || !response}
								onClick={confirm}
							>
								තහවුරු කරන්න
							</button>
						</>
					)}
					{step === "support" && support && (
						support.game_manifest.schema_version === "support-round-v1" ? <SupportRoundFrame support={support} busy={busy} onViewComplete={() => void finishSupport()} renderActivity={(activity) => <FractionActivity key={activity.revision_id} game={activity.game} onResponse={record} />}>
							{support.game_manifest.stage_kind !== "view" && <button type="button" className="fraction-primary" disabled={busy || !response} onClick={() => void answerSupport()}>තහවුරු කරන්න</button>}
						</SupportRoundFrame> : <FractionSupport
							support={support}
							actions={supportActions}
							onAction={() => setSupportActions((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="fraction-status" role="status">
							සහාය ඉවත් කර නව ප්‍රශ්නය සූදානම් කරමින්…
						</p>
					)}
					{step === "feedback" && !correct && (
						<div className="fraction-feedback">
							<h2>නැවත බලමු.</h2>
							<button
								type="button"
								className="fraction-primary"
								onClick={continueAfterFeedback}
							>
								නැවත උත්සාහ කරන්න
							</button>
						</div>
					)}
					{step === "result" && chapter && (
						<GameSuccessScreen
							gameNumber={chapterIndex + 1}
							gameCount={FRACTION_GAMES.length}
							onContinue={() => {
									const next = FRACTION_GAMES[chapterIndex + 1];
									if (next) {
										const first = FRACTION_SKILLS.find(
											(item) => item.chapter === next.id,
										);
										if (first) void openSkill(first.id, next.id);
									} else setStep("chapters");
								}}
						/>
					)}
				</section>
			)}
		</main>
	);
}

export function StackedFraction({
	numerator,
	denominator,
}: {
	numerator: number | string;
	denominator: number;
}) {
	return (
		<span
			className="stacked-fraction"
			role="img"
			aria-label={`${numerator} බෙදීම ${denominator}`}
		>
			<strong>{numerator}</strong>
			<span aria-hidden="true" />
			<strong>{denominator}</strong>
		</span>
	);
}

export function FractionActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse, correction?: boolean): void;
}) {
	const kind = String(game.response_kind);
	const denominator = Number(game.denominator);
	const representation = String(game.representation ?? "rectangle") as
		| "circle"
		| "rectangle"
		| "strip";
	const stimulus = Array.isArray(game.stimulus_shaded_indices)
		? game.stimulus_shaded_indices.map(Number)
		: [];
	const [selected, setSelected] = useState<number[]>(stimulus);
	const total = Number(game.total ?? 0);
	const [assignments, setAssignments] = useState<number[]>(() =>
		Array(total).fill(-1),
	);
	const [activeGroup, setActiveGroup] = useState(0);
	const [table, setTable] = useState<[number, number, number]>([0, 0, 0]);
	const [numerator, setNumerator] = useState(0);
	const toggle = (index: number) => {
		const next = selected.includes(index)
			? selected.filter((value) => value !== index)
			: [...selected, index];
		setSelected(next);
		if (kind === "tenths_representation")
			onResponse(
				tenthsResponse(
					representation === "circle" ? "circle" : "strip",
					Number(game.requested_numerator ?? numerator),
					next,
				),
				selected.includes(index),
			);
		else
			onResponse(
				shadingResponse(
					representation === "circle" ? "circle" : "rectangle",
					denominator as 2 | 4,
					next,
				),
				selected.includes(index),
			);
	};
	if (kind === "equal_grouping")
		return (
			<div className="grouping-board">
				<fieldset className="object-tray">
					<legend className="sr-only">බෙදීමට ඇති ඇපල්</legend>
					{assignments.map((group, index) => (
						<button
							type="button"
							draggable
							key={`apple-${index}`}
							className="apple-token"
							aria-label={`ඇපල් ${index + 1}${group >= 0 ? `, කණ්ඩායම ${group + 1}` : ", තවම බෙදා නැත"}`}
							onClick={() => {
								const next = [...assignments];
								const correction = next[index] >= 0;
								next[index] = activeGroup;
								setAssignments(next);
								onResponse(
									groupingResponse(denominator as 2 | 4, next),
									correction,
								);
							}}
						>
							<img
								src="/curriculum/game/G5-AREA-MAT-05/apple-token.png"
								alt=""
							/>
						</button>
					))}
				</fieldset>
				<div className={`sharing-groups groups-${denominator}`}>
					{Array.from({ length: denominator }, (_, group) => (
						<button
							type="button"
							key={`group-${group}`}
							className={
								activeGroup === group ? "sharing-bowl active" : "sharing-bowl"
							}
							aria-pressed={activeGroup === group}
							aria-label={`කණ්ඩායම ${group + 1} තෝරන්න. ඇපල් ${assignments.filter((value) => value === group).length}`}
							onClick={() => setActiveGroup(group)}
						>
							<img
								src="/curriculum/game/G5-AREA-MAT-02/empty-fruit-basket.png"
								alt=""
							/>
							<strong>
								{assignments.filter((value) => value === group).length}
							</strong>
						</button>
					))}
				</div>
			</div>
		);
	if (kind === "fraction_quantity_table")
		return (
			<div className="quarter-table-wrap">
				<table>
					<caption>{total} සඳහා කාල සම්බන්ධතා</caption>
					<thead>
						<tr>
							<th>සම්පූර්ණය</th>
							<th>
								<StackedFraction numerator={1} denominator={4} />
							</th>
							<th>
								<StackedFraction numerator={2} denominator={4} />
							</th>
							<th>
								<StackedFraction numerator={3} denominator={4} />
							</th>
						</tr>
					</thead>
					<tbody>
						<tr>
							<td>{total}</td>
							{table.map((value, index) => (
								<td key={`quarter-${index + 1}`}>
									<button
										type="button"
										style={{ minWidth: 48, minHeight: 48 }}
										aria-label={`${index + 1} කාල අගය අඩු කරන්න`}
										onClick={() => {
											const next = [...table] as [number, number, number];
											next[index] = Math.max(0, value - 1);
											setTable(next);
											onResponse(quarterTableResponse(total, next), true);
										}}
									>
										−
									</button>
									<strong>{value}</strong>
									<button
										type="button"
										style={{ minWidth: 48, minHeight: 48 }}
										aria-label={`${index + 1} කාල අගය එකතු කරන්න`}
										onClick={() => {
											const next = [...table] as [number, number, number];
											next[index] = Math.min(total, value + 1);
											setTable(next);
											onResponse(quarterTableResponse(total, next));
										}}
									>
										+
									</button>
								</td>
							))}
						</tr>
					</tbody>
				</table>
			</div>
		);
	const regions = Number(game.region_count ?? denominator);
	const readOnly =
		kind === "tenths_representation" && game.requested_numerator == null;
	return (
		<div className="fraction-construction">
			<StackedFraction
				numerator={
					game.requested_numerator == null
						? numerator || "?"
						: Number(game.requested_numerator)
				}
				denominator={denominator}
			/>
			<div className={`fraction-shape ${representation}`} data-parts={regions}>
				{Array.from({ length: regions }, (_, index) => (
					<button
						type="button"
						style={{ minWidth: 48, minHeight: 48 }}
						key={`region-${index}`}
						className={
							(readOnly ? stimulus : selected).includes(index)
								? "region shaded"
								: "region"
						}
						disabled={readOnly}
						aria-pressed={(readOnly ? stimulus : selected).includes(index)}
						aria-label={`සමාන කොටස ${index + 1}${(readOnly ? stimulus : selected).includes(index) ? ", පාට කර ඇත" : ""}`}
						onClick={() => toggle(index)}
					/>
				))}
			</div>
			{readOnly && (
				<div className="numerator-stepper">
					<button
						type="button"
						style={{ minWidth: 48, minHeight: 48 }}
						aria-label="ඉහළ අංකයෙන් එකක් අඩු කරන්න"
						disabled={numerator === 0}
						onClick={() => {
							const next = Math.max(0, numerator - 1);
							setNumerator(next);
							onResponse(
								tenthsResponse(
									representation === "circle" ? "circle" : "strip",
									next,
									stimulus,
								),
								true,
							);
						}}
					>
						−
					</button>
					<strong>{numerator}</strong>
					<button
						type="button"
						aria-label="ඉහළ අංකයට එකක් එකතු කරන්න"
						disabled={numerator === 9}
						onClick={() => {
							const next = Math.min(9, numerator + 1);
							setNumerator(next);
							onResponse(
								tenthsResponse(
									representation === "circle" ? "circle" : "strip",
									next,
									stimulus,
								),
							);
						}}
					>
						+
					</button>
				</div>
			)}
		</div>
	);
}

function FractionSupport({
	support,
	actions,
	onAction,
	onComplete,
}: {
	support: SupportView;
	actions: number;
	onAction(): void;
	onComplete(): void;
}) {
	const manifest = support.game_manifest as {
		required_actions?: number;
		worked_example?: { prompt_si: string; steps_si: string[] };
	};
	const required = Number(manifest.required_actions ?? 1);
	const steps = manifest.worked_example?.steps_si ?? support.body_si;
	return (
		<div className="fraction-support">
			<p className="support-type">උදව් වර්ගය: {support.title_si}</p>
			<h2>{manifest.worked_example?.prompt_si}</h2>
			<ol>
				{steps.map((text, index) => (
					<li className={index < actions ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				type="button"
				className="fraction-primary"
				onClick={actions < required ? onAction : onComplete}
			>
				{actions < required ? "ඊළඟ පියවර" : "උදව්ව අවසන් කරන්න"}
			</button>
		</div>
	);
}
