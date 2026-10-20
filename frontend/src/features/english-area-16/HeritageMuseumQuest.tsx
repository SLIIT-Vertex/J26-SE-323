// biome-ignore-all lint/a11y/useButtonType: application controls, no forms.
import { useCallback, useEffect, useRef, useState } from "react";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	SuccessCelebration,
} from "../mobile-learning-flow/AdventureShared";
import type {
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../english-area-1/classroom-action-quest.css";
import "./heritage-museum.css";
import {
	exhibitMappingResponse,
	type HeritageLink,
	pastBilingualResponse,
} from "./heritageLogic";

const SKILLS = [
	{ id: "G5-ENG-PAST-BILINGUAL-01", name: "Museum Word Bridge", icon: "🏷️" },
	{ id: "G5-ENG-PAST-VISUAL-02", name: "Exhibit Label Match", icon: "🔎" },
] as const;
type Api = Pick<
	LearningFlowClient,
	| "open"
	| "answerBefore"
	| "completeSupport"
	| "withdrawSupport"
	| "presentAfter"
	| "answerAfter"
>;
type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type Row = Record<string, unknown>;

export function HeritageMuseumQuest({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: {
	api: Api;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("games");
	const [skill, setSkill] = useState<string | null>(null);
	const [episode, setEpisode] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
	const [busy, setBusy] = useState(false);
	const [supportStage, setSupportStage] = useState(0);
	const [completed, setCompleted] = useState<string[]>([]);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [moves, setMoves] = useState(0);
	const [pendingWithdrawal, setPendingWithdrawal] = useState<{
		episode: string;
		support: string;
		manifest: string;
	} | null>(null);
	const submitLock = useRef(false);
	const skillIndex = Math.max(
		0,
		SKILLS.findIndex((entry) => entry.id === skill),
	);
	const run = useCallback(
		async <T,>(operation: () => Promise<T>) => {
			setBusy(true);
			try {
				return await operation();
			} catch (error) {
				onFailure(error);
			} finally {
				setBusy(false);
			}
		},
		[onFailure],
	);
	const resetQuestion = useCallback(() => {
		setResponse(null);
		setMoves(0);
		setStartedAt(Date.now());
	}, []);

	useEffect(() => {
		if (step !== "withdrawing" || !pendingWithdrawal) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() =>
				api.withdrawSupport(
					pendingWithdrawal.episode,
					{
						request_id: crypto.randomUUID(),
						support_revision_id: pendingWithdrawal.support,
						manifest_revision_id: pendingWithdrawal.manifest,
						all_support_removed: true,
						answer_revealing_state_cleared: true,
						input_handlers_cleared: true,
					},
					crypto.randomUUID(),
				),
			);
			if (!withdrawn || cancelled) return;
			const next = await run(() =>
				api.presentAfter(pendingWithdrawal.episode, crypto.randomUUID()),
			);
			if (!next || cancelled) return;
			setManifest(next.manifest);
			setSupport(null);
			setPendingWithdrawal(null);
			resetQuestion();
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, pendingWithdrawal, resetQuestion, run, step]);

	const openSkill = async (skillId: string) => {
		if (submitLock.current) return;
		submitLock.current = true;
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
					area_id: "G5-AREA-ENG-16",
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		submitLock.current = false;
		if (!opened) return;
		setSkill(skillId);
		setEpisode(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setCorrect(false);
		resetQuestion();
		setStep("question");
	};

	const submit = async () => {
		if (!episode || !manifest || !response || submitLock.current) return;
		submitLock.current = true;
		const elapsed = reducedMotion ? 0 : Date.now() - startedAt;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			response_time_ms: reducedMotion ? null : elapsed,
			interaction_summary: {
				move_count: moves,
				correction_count: Math.max(0, moves - 1),
				first_action_ms: 0,
				active_time_ms: elapsed,
				attempt_count: 1,
				invalid_drop_count: 0,
				tap_alternative_used: true,
			},
		};
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episode, body, crypto.randomUUID())
				: api.answerBefore(episode, body, crypto.randomUUID()),
		);
		submitLock.current = false;
		if (!next) return;
		if (
			!next.server_score ||
			next.server_score.presentation_id !== manifest.presentation_id ||
			next.server_score.item_revision_id !== manifest.revision_id
		) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
			return;
		}
		setCorrect(next.server_score.correct === true);
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportStage(0);
			setStep("support");
		} else {
			setStep("feedback");
		}
	};

	const finishSupport = async () => {
		if (
			!episode ||
			!support ||
			support.game_manifest.schema_version !== "heritage-museum-support-v1" ||
			supportStage < support.game_manifest.required_actions
		)
			return;
		const game = support.game_manifest;
		const completedSupport = await run(() =>
			api.completeSupport(
				episode,
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
		if (!completedSupport) return;
		setPendingWithdrawal({
			episode,
			support: support.revision_id,
			manifest: game.revision_id,
		});
		setSupport(null);
		setResponse(null);
		setStep("withdrawing");
	};

	const advance = () => {
		if (!skill || !correct) {
			if (skill) void openSkill(skill);
			return;
		}
		const nextCompleted = completed.includes(skill)
			? completed
			: [...completed, skill];
		setCompleted(nextCompleted);
		if (skillIndex < 1) void openSkill(SKILLS[1].id);
		else setStep(nextCompleted.length === 2 ? "result" : "games");
	};

	const game =
		manifest?.game?.schema_version === "heritage-museum-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main className="classroom-action-quest heritage-museum">
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<p>Theme 16</p>
					<h1>Our Past</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list">
					<div className="hm-gallery" aria-hidden="true">
						<i />
						<b />
						<span>🔎</span>
					</div>
					<p className="hm-notice">
						Simple learning symbols · not real museum objects
					</p>
					{SKILLS.map((entry) => (
						<button
							className="caq-game-card"
							key={entry.id}
							onClick={() => void openSkill(entry.id)}
						>
							<span>{entry.icon}</span>
							<span>
								<strong>{entry.name}</strong>
								<small>Connect reviewed textbook vocabulary.</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={2}
						currentActivity={skillIndex + 1}
						completedActivities={completed.length}
					/>
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<MuseumBoard
								key={manifest?.revision_id}
								game={game}
								onResponse={(next) => {
									setResponse(next);
									setMoves((value) => value + 1);
								}}
							/>
							<button
								className="caq-primary"
								disabled={busy || !response || isIncomplete(response)}
								onClick={submit}
							>
								Check my labels
							</button>
						</>
					)}
					{step === "support" &&
						support?.game_manifest.schema_version ===
							"heritage-museum-support-v1" && (
							<section className="caq-support">
								<h2>{support.title_si}</h2>
								<p>
									{
										support.body_si[
											Math.min(supportStage, support.body_si.length - 1)
										]
									}
								</p>
								<button
									className="caq-primary"
									onClick={
										supportStage < support.game_manifest.required_actions
											? () => setSupportStage((value) => value + 1)
											: finishSupport
									}
								>
									{supportStage < support.game_manifest.required_actions
										? "Next museum step"
										: "I’m ready to curate alone"}
								</button>
							</section>
						)}
					{step === "withdrawing" && (
						<p className="caq-status">
							All examples, highlights, selections, and lens details are
							clearing.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Museum label approved!"
									: "Inspect the words and exhibits once more."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct ? "Continue" : "Try a fresh gallery"}
							</button>
						</section>
					)}
					{step === "result" && (
						<section className="caq-feedback caq-result">
							<SuccessCelebration />
							<h2>Heritage Museum Quest complete!</h2>
							<p>You connected the lesson vocabulary independently.</p>
						</section>
					)}
				</section>
			)}
		</main>
	);
}

function isIncomplete(response: ConstructedResponse) {
	return response.kind === "past_bilingual_links"
		? response.unlinked_english_tokens.length > 0
		: response.kind === "heritage_exhibit_mapping"
			? response.unplaced_word_tokens.length > 0
			: true;
}

function MuseumBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(response: ConstructedResponse): void;
}) {
	const bilingual = game.response_kind === "past_bilingual_links";
	const sources = (bilingual ? game.english_words : game.words) as Row[];
	const targets = (bilingual ? game.sinhala_words : game.exhibits) as Row[];
	const sourceKey = bilingual ? "english_token" : "word_token";
	const targetKey = bilingual ? "sinhala_token" : "exhibit_token";
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<HeritageLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const [detail, setDetail] = useState<number | null>(null);
	const place = (target: string) => {
		if (!selected) return;
		const remaining = links.filter(
			(link) => link.source !== selected && link.target !== target,
		);
		const next = [
			...remaining,
			{ sequence: remaining.length + 1, source: selected, target },
		];
		const nextTrace = [
			...trace,
			links.some((link) => link.source === selected)
				? `replace:${target}`
				: `place:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		onResponse(
			bilingual
				? pastBilingualResponse(
						String(game.command_token),
						next,
						sources.map((row) => String(row[sourceKey])),
						nextTrace,
					)
				: exhibitMappingResponse(
						String(game.command_token),
						next,
						sources.map((row) => String(row[sourceKey])),
						nextTrace,
					),
		);
	};
	return (
		<section className="hm-board">
			{selected && <p className="hm-dock">Selected label ready</p>}
			<div className="hm-tray">
				{sources.map((row) => (
					<button
						data-opaque-token={String(row[sourceKey])}
						key={String(row[sourceKey])}
						aria-pressed={selected === row[sourceKey]}
						onClick={() => setSelected(String(row[sourceKey]))}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
			<div className="hm-cases">
				{targets.map((row, index) => (
					<article key={String(row[targetKey])}>
						<button
							className="hm-target"
							data-opaque-token={String(row[targetKey])}
							onClick={() => place(String(row[targetKey]))}
						>
							{bilingual ? (
								<>
									<strong>{String(row.text_si)}</strong>
									<small>
										{links.some((link) => link.target === row[targetKey])
											? "✓ linked"
											: "tap to link"}
									</small>
								</>
							) : (
								<ExhibitSymbol
									variant={Number(row.renderer_variant)}
									index={index}
								/>
							)}
						</button>
						{!bilingual && (
							<button
								className="hm-lens"
								aria-label={`Inspect schematic exhibit ${index + 1}`}
								onClick={() => setDetail(index)}
							>
								🔎 Inspect
							</button>
						)}
					</article>
				))}
			</div>
			{detail !== null && (
				<div
					className="hm-sheet"
					role="dialog"
					aria-modal="true"
					aria-label="Schematic exhibit detail"
				>
					<ExhibitSymbol
						variant={Number(targets[detail]?.renderer_variant)}
						index={detail}
					/>
					<p>
						Schematic learning symbol — no date, place, ruler, provenance, or
						authenticity claim.
					</p>
					<button onClick={() => setDetail(null)}>Close detail</button>
				</div>
			)}
		</section>
	);
}

function ExhibitSymbol({ variant, index }: { variant: number; index: number }) {
	return (
		<span
			className="hm-symbol"
			data-v={variant}
			role="img"
			aria-label={`Schematic learning exhibit ${index + 1}`}
		>
			<i />
			<i />
			<b />
			<b />
		</span>
	);
}
