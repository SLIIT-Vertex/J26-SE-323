// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import {
	AdventureProgress,
	adaptiveGameProgressStage,
} from "../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../mobile-learning-flow/AdventureShared";
import type {
	ConstructedResponse,
	ExperimentCondition,
	FamilyConstellationWorkedExample,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../mobile-learning-flow/english-game-shared.css";
import "./family-word-constellation.css";
import {
	type FamilyLink,
	familyLinkResponse,
} from "./familyConstellationLogic";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Row = Record<string, unknown>;

export function FamilyWordConstellation({
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
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
	const [busy, setBusy] = useState(false);
	const [supportStage, setSupportStage] = useState(0);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [moves, setMoves] = useState(0);
	const [pending, setPending] = useState<{
		episode: string;
		support: string;
		manifest: string;
	} | null>(null);
	const lock = useRef(false);
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
	const round = useSupportRound({
		api,
		episodeId,
		run,
		onSupport: (next) => {
			setSupport(next);
			reset();
		},
		onWithdraw: (withdrawal) => {
			setPending({
				episode: withdrawal.episodeId,
				support: withdrawal.supportRevisionId,
				manifest: withdrawal.manifestRevisionId,
			});
			setSupport(null);
			setResponse(null);
			setStep("withdrawing");
		},
	});
	const openSkill = async () => {
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
					area_id: "G5-AREA-ENG-12",
					atomic_skill_id: "G5-ENG-FAMILY-BILINGUAL-01",
				},
				crypto.randomUUID(),
			),
		);
		lock.current = false;
		if (!opened) return;
		setEpisodeId(opened.episode_id);
		setManifest(opened.manifest);
		setSupport(null);
		setCorrect(false);
		reset();
		setStep("question");
	};
	const confirm = async () => {
		if (!episodeId || !manifest || !response || lock.current) return;
		lock.current = true;
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
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportStage(0);
			setStep("support");
		} else setStep("feedback");
	};
	const finishSupport = async () => {
		if (
			!episodeId ||
			!support ||
			support.game_manifest.schema_version !==
				"family-word-constellation-support-v1"
		)
			return;
		const game = support.game_manifest;
		if (supportStage < game.required_actions) return;
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
		if (!done) return;
		setPending({
			episode: episodeId,
			support: support.revision_id,
			manifest: game.revision_id,
		});
		setSupport(null);
		setResponse(null);
		setStep("withdrawing");
	};
	return (
		<main
			className="classroom-action-quest family-word-constellation"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Human Behaviour</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list" aria-label="Family word games">
					<button className="caq-game-card" onClick={() => void openSkill()}>
						<span aria-hidden="true">⭐</span>
						<span>
							<strong>Word-Star Bridge</strong>
							<small>
								Connect the English and Sinhala words from this lesson.
							</small>
						</span>
					</button>
					<button className="caq-game-card locked" disabled>
						<span aria-hidden="true">🔒</span>
						<span>
							<strong>Grandword Workshop</strong>
							<small>Waiting for review of the printed grand-word forms.</small>
						</span>
					</button>
				</section>
			) : (
				<section className="caq-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
							activityCount={1}
							currentActivity={1}
							completedActivities={0}
						/>
					)}
					{step === "question" &&
						manifest?.game?.schema_version ===
							"family-word-constellation-item-v1" && (
							<>
								<div className="caq-command">
									<strong>{manifest.prompt_si}</strong>
								</div>
								<LinkBoard
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={(value) => {
										setResponse(value);
										setMoves((count) => count + 1);
									}}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my word links
								</button>
							</>
						)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null}
							checkLabel="Check my word links"
							checkClassName="caq-primary"
							onCheck={() => {
								if (response)
									void round.answer(
										support,
										response,
										Date.now() - startedAt,
										moves,
									);
							}}
							onViewComplete={() =>
								void round.viewComplete(support, Date.now() - startedAt)
							}
							renderActivity={(activity) => (
								<LinkBoard
									key={activity.revision_id}
									game={activity.game as Record<string, unknown>}
									onResponse={(value) => {
										setResponse(value);
										setMoves((count) => count + 1);
									}}
								/>
							)}
						/>
					)}
					{step === "support" &&
						support?.game_manifest.schema_version ===
							"family-word-constellation-support-v1" && (
							<section className="caq-support">
								<p>Help type: {support.title_si}</p>
								<Worked
									example={support.game_manifest.worked_example}
									reveal={
										supportStage > 0 ||
										support.scaffold_type === "visual_guidance"
									}
								/>
								<ol>
									{support.game_manifest.worked_example.steps_si.map(
										(text, index) => (
											<li
												className={index < supportStage ? "done" : ""}
												key={text}
											>
												{text}
											</li>
										),
									)}
								</ol>
								<button
									className="caq-primary"
									onClick={
										supportStage < support.game_manifest.required_actions
											? () => setSupportStage((value) => value + 1)
											: finishSupport
									}
								>
									{supportStage < support.game_manifest.required_actions
										? "Next help step"
										: "Now I will try alone"}
								</button>
							</section>
						)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now link a fresh set of lesson words on
							your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Constellation badge earned!"
									: "Read both lesson words again."}
							</h2>
							<button
								className="caq-primary"
								onClick={() => (correct ? setStep("result") : void openSkill())}
							>
								{correct ? "Finish" : "Try another one"}
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={1}
							gameCount={1}
							onContinue={() => setStep("games")}
						/>
					)}
				</section>
			)}
		</main>
	);
}

function LinkBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const sources = game.english_words as Row[];
	const targets = game.sinhala_words as Row[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<FamilyLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const place = (target: string) => {
		if (!selected) return;
		const old = links.find(
			(link) => link.source === selected || link.target === target,
		);
		const next = links.filter(
			(link) => link.source !== selected && link.target !== target,
		);
		next.push({ sequence: next.length + 1, source: selected, target });
		const nextTrace = [
			...trace,
			`${old ? "replace" : "link"}:${selected}:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		if (next.length === sources.length)
			onResponse(
				familyLinkResponse(
					String(game.command_token),
					next,
					sources.map((row) => String(row.english_token)),
					nextTrace,
				),
			);
	};
	return (
		<section className="link-board">
			<div className="star-rail">
				{sources.map((row) => {
					const id = String(row.english_token);
					return (
						<button
							key={id}
							className={selected === id ? "selected" : ""}
							disabled={links.some((link) => link.source === id)}
							onClick={() => setSelected(id)}
						>
							{String(row.text_en)}
						</button>
					);
				})}
			</div>
			<div className="sinhala-sheet">
				{targets.map((row) => {
					const id = String(row.sinhala_token);
					const linked = links.find((entry) => entry.target === id);
					return (
						<button key={id} disabled={!selected} onClick={() => place(id)}>
							{String(row.text_si)}
							<span>{linked ? "linked" : "Choose a word"}</span>
						</button>
					);
				})}
			</div>
		</section>
	);
}

function Worked({
	example,
	reveal,
}: {
	example: FamilyConstellationWorkedExample;
	reveal: boolean;
}) {
	const count =
		example.correct_response?.kind === "family_bilingual_links"
			? example.correct_response.links.length
			: 0;
	return (
		<p>{reveal ? `${count} lesson links shown on a fresh example` : "?"}</p>
	);
}
