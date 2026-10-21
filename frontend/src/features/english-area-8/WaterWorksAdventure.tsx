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
	PresentationManifest,
	SupportView,
	WaterWorksWorkedExample,
} from "../mobile-learning-flow/api/generated";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../mobile-learning-flow/english-game-shared.css";
import "./water-works-adventure.css";
import { WATER_STAGES } from "./manifest";
import {
	SCENE_MARKS,
	type WaterLink,
	waterActionResponse,
} from "./waterWorksLogic";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
const STAGE_LABELS: Record<string, string> = {
	droplet_match: "Droplet Match",
	pipe_route: "Pipe Route Relay",
	splash_detective: "Splash Scene Detective",
};

export function WaterWorksAdventure({
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
	const [completed, setCompleted] = useState(false);
	const [startedAt, setStartedAt] = useState(Date.now());
	const [moves, setMoves] = useState(0);
	const [pending, setPending] = useState<{
		episode: string;
		support: string;
		manifest: string;
	} | null>(null);
	const lock = useRef(false);
	const skill = WATER_STAGES[0];
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
					area_id: "G5-AREA-ENG-08",
					atomic_skill_id: skill.id,
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
	const record = (value: ConstructedResponse) => {
		setResponse(value);
		setMoves((value) => value + 1);
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
				invalid_drop_count:
					"invalid_drop_count" in response ? response.invalid_drop_count : 0,
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
				"water-works-adventure-support-v1"
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
	const chapter =
		manifest?.game && "chapter" in manifest.game
			? String(manifest.game.chapter)
			: "droplet_match";
	return (
		<main
			className="classroom-action-quest water-works-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Water</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list" aria-label="Water games">
					<button className="caq-game-card" onClick={() => void openSkill()}>
						<span className="scene-mark" aria-hidden="true">
							{skill.icon}
						</span>
						<span>
							<strong>{skill.name}</strong>
							<small>{skill.description}</small>
							<em>One skill · easy to closer scenes</em>
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
							completedActivities={completed ? 1 : 0}
						/>
					)}
					<p className="caq-position">{STAGE_LABELS[chapter] ?? "Water"}</p>
					{step === "question" &&
						manifest?.game?.schema_version ===
							"water-works-adventure-item-v1" && (
							<>
								<div className="caq-command">
									<span className="scene-mark" aria-hidden="true">
										💧
									</span>
									<strong>{manifest.prompt_si}</strong>
								</div>
								<WaterBoard
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my water actions
								</button>
							</>
						)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null}
							checkLabel="Check my water actions"
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
								<WaterBoard
									key={activity.revision_id}
									game={activity.game as Record<string, unknown>}
									onResponse={record}
								/>
							)}
						/>
					)}
					{step === "support" && support && !isSupportRound(support) && (
						<WaterSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now match a fresh set on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Water badge earned!"
									: "Read the action and look at the scene again."}
							</h2>
							<button
								className="caq-primary"
								onClick={() => {
									if (correct) {
										setCompleted(true);
										setStep("result");
									} else void openSkill();
								}}
							>
								{correct ? "Finish adventure" : "Try another one"}
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

type Row = Record<string, unknown>;
export function WaterBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const sources = game.actions as Row[];
	const targets = game.scenes as Row[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<WaterLink[]>([]);
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
			`${old ? "replace" : "route"}:${selected}:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		if (next.length === sources.length)
			onResponse(
				waterActionResponse(
					String(game.command_token),
					next,
					sources.map((row) => String(row.action_token)),
					nextTrace,
				),
			);
	};
	return (
		<section className="water-board">
			<div className="droplet-rail">
				{sources.map((row) => {
					const id = String(row.action_token);
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
			<div className="scene-grid">
				{targets.map((row) => {
					const id = String(row.scene_token);
					const linked = links.find((entry) => entry.target === id);
					const label = linked
						? String(
								sources.find(
									(entry) => String(entry.action_token) === linked.source,
								)?.text_en ?? "",
							)
						: "Choose a word";
					return (
						<button
							className="scene-card"
							key={id}
							disabled={!selected}
							onClick={() => place(id)}
						>
							<span className="scene-mark" aria-hidden="true">
								{SCENE_MARKS[Number(row.renderer_variant)] ?? "💧"}
							</span>
							<span>{label}</span>
						</button>
					);
				})}
			</div>
		</section>
	);
}
function WaterSupport({
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
	if (
		support.game_manifest.schema_version !== "water-works-adventure-support-v1"
	)
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's try another water example</h2>
			<WaterWorkedExample
				example={game.worked_example}
				reveal={stage > 0 || support.scaffold_type === "visual_guidance"}
			/>
			<ol>
				{game.worked_example.steps_si.map((text, index) => (
					<li className={index < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="caq-primary"
				onClick={stage < game.required_actions ? onNext : onComplete}
			>
				{stage < game.required_actions
					? "Next help step"
					: "Now I will try alone"}
			</button>
		</section>
	);
}
function WaterWorkedExample({
	example,
	reveal,
}: {
	example: WaterWorksWorkedExample;
	reveal: boolean;
}) {
	const count =
		example.correct_response?.kind === "water_action_mapping"
			? example.correct_response.placements.length
			: 0;
	return (
		<div>
			<strong>{example.prompt_si}</strong>
			<span>
				{reveal ? `${count} connections shown on a fresh example` : "?"}
			</span>
		</div>
	);
}
