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
	SriLankaDiscoveryWorkedExample,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { wordPicture } from "../mobile-learning-flow/phaser-board/pictures";
import { sceneFor } from "../mobile-learning-flow/phaser-board/scenes";
import { TokenBoard } from "../mobile-learning-flow/phaser-board/TokenBoard";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import { SRI_LANKA_SKILLS } from "./manifest";
import { groupingResponse, mappingResponse } from "./sriLankaDiscoveryLogic";
import "./sri-lanka-discovery.css";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function SriLankaDiscovery({
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
		SRI_LANKA_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = SRI_LANKA_SKILLS[index];

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
					area_id: "G5-AREA-ENG-02",
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

	const record = (value: ConstructedResponse) => {
		setResponse(value);
		setMoves((current) => current + 1);
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
		setFeedback(next.server_score.feedback_column ?? null);
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
			support.game_manifest.schema_version !== "sri-lanka-discovery-support-v1"
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

	const advance = () => {
		if (!skillId || !correct)
			return skillId ? void openSkill(skillId) : undefined;
		const done = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(done);
		if (index < SRI_LANKA_SKILLS.length - 1)
			void openSkill(SRI_LANKA_SKILLS[index + 1].id);
		else setStep(done.length === SRI_LANKA_SKILLS.length ? "result" : "games");
	};

	return (
		<main
			className="sri-lanka-discovery"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="sld-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>We are Sri Lankans</h1>
				</div>
			</header>
			{step === "games" ? (
				<section
					className="sld-game-list"
					aria-label="We are Sri Lankans games"
				>
					{SRI_LANKA_SKILLS.map((skill, skillIndex) => (
						<button
							className="sld-game-card"
							key={skill.id}
							onClick={() => void openSkill(skill.id)}
						>
							<span className="sld-icon" aria-hidden="true">
								{skill.icon}
							</span>
							<span>
								<strong>{skill.name}</strong>
								<small>{skill.description}</small>
								<em>{skillIndex + 1}/3 · Easy to challenging</em>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="sld-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(
								step,
								manifest?.measurement_role,
							)}
							activityCount={3}
							currentActivity={index + 1}
							completedActivities={completed.length}
						/>
					)}
					<p className="sld-position">
						Activity {index + 1}/3 · {active.name}
					</p>
					{step === "question" &&
						manifest?.game?.schema_version ===
							"sri-lanka-discovery-item-v1" && (
							<>
								<div className="sld-command">
									<span>Explore and connect</span>
									<strong>{manifest.prompt_si}</strong>
								</div>
								<DiscoveryActivity
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="sld-primary"
									disabled={busy || !response || !isComplete(response)}
									onClick={confirm}
								>
									Check my discovery
								</button>
							</>
						)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null && isComplete(response)}
							checkLabel="Check my discovery"
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
								<DiscoveryActivity
									key={activity.revision_id}
									game={activity.game as Record<string, unknown>}
									onResponse={record}
								/>
							)}
						/>
					)}
					{step === "support" && support && !isSupportRound(support) && (
						<DiscoverySupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="sld-status" role="status">
							The help is going away. Now try a fresh discovery on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="sld-feedback">
							<h2>
								{correct ? "Excellent discovery!" : friendlyFeedback(feedback)}
							</h2>
							<button className="sld-primary" onClick={advance}>
								{correct
									? index === 2
										? "Finish trail"
										: "Next activity"
									: "Try another one"}
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={3}
							gameCount={3}
							onContinue={() => setStep("games")}
						/>
					)}
				</section>
			)}
		</main>
	);
}

type NamedRow = Record<string, unknown>;

export function DiscoveryActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	if (game.response_kind === "semantic_grouping")
		return <GroupingBoard game={game} onResponse={onResponse} />;
	return <MappingBoard game={game} onResponse={onResponse} />;
}

function MappingBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	const isLabel = game.response_kind === "semantic_label_mapping";
	const kind = game.response_kind as
		| "semantic_label_mapping"
		| "category_exemplar_mapping";
	return (
		<TokenBoard
			theme="market"
			scene={sceneFor("G5-AREA-ENG-02")}
			sources={(isLabel ? game.labels : game.exemplars) as NamedRow[]}
			sourceKey={isLabel ? "label_id" : "exemplar_id"}
			targets={(isLabel ? game.destinations : game.categories) as NamedRow[]}
			targetKey={isLabel ? "destination_id" : "category_id"}
			target={(row) =>
				isLabel
					? { label: String(row.text_si) }
					: {
							label: String(row.text_en),
							picture: { emoji: wordPicture(row.text_en) ?? "🇱🇰" },
						}
			}
			instruction={
				isLabel
					? "Drag each English word to its Sinhala meaning."
					: "Drag each example to its national symbol."
			}
			build={(links, tokens, trace) =>
				mappingResponse(
					kind,
					String(game.command_token),
					links.map((link) => ({
						sequence: link.sequence,
						sourceId: link.source,
						destinationId: link.target,
					})),
					tokens,
					trace,
				)
			}
			onResponse={onResponse}
		/>
	);
}

function GroupingBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse | null): void;
}) {
	const members = game.members as NamedRow[];
	const groups = game.groups as NamedRow[];
	return (
		<TokenBoard
			theme="market"
			layout="bins"
			scene={sceneFor("G5-AREA-ENG-02")}
			sources={members}
			sourceKey="member_id"
			targets={groups}
			targetKey="group_id"
			target={(row) => ({
				label: String(row.text_en),
				capacity: members.length,
				picture: { emoji: wordPicture(row.text_en) ?? "🧺" },
			})}
			instruction="Sort each word into its group."
			build={(links, tokens, trace) =>
				groupingResponse(
					String(game.command_token),
					Object.fromEntries(
						groups.map((group) => [
							String(group.group_id),
							links
								.filter((link) => link.target === String(group.group_id))
								.sort((a, b) => a.sequence - b.sequence)
								.map((link) => link.source),
						]),
					),
					tokens,
					trace,
				)
			}
			onResponse={onResponse}
		/>
	);
}

function DiscoverySupport({
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
	if (support.game_manifest.schema_version !== "sri-lanka-discovery-support-v1")
		return null;
	const game = support.game_manifest;
	return (
		<section className="sld-support" data-support-type={support.scaffold_type}>
			<p>Help type: {support.title_si}</p>
			<h2>Let's discover another way</h2>
			<WorkedMapping
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
				className="sld-primary"
				onClick={stage < game.required_actions ? onNext : onComplete}
			>
				{stage < game.required_actions
					? "Next help step"
					: "Now I will try alone"}
			</button>
		</section>
	);
}

function WorkedMapping({
	example,
	reveal,
}: {
	example: SriLankaDiscoveryWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	return (
		<div className="sld-worked">
			<strong>{example.prompt_si}</strong>
			<div>
				{reveal && response
					? response.kind === "semantic_grouping"
						? `${response.groups.length} groups completed`
						: response.kind === "semantic_label_mapping"
							? `${response.placements.length} words connected`
							: response.kind === "category_exemplar_mapping"
								? `${response.mappings.length} pairs connected`
								: "Connection demonstrated"
					: "?"}
			</div>
		</div>
	);
}

function isComplete(response: ConstructedResponse) {
	if (response.kind === "semantic_label_mapping")
		return response.unplaced_label_ids.length === 0;
	if (response.kind === "semantic_grouping")
		return response.unassigned_member_ids.length === 0;
	return response.kind === "category_exemplar_mapping";
}

function friendlyFeedback(code: string | null) {
	if (code?.includes("national"))
		return "Check each national category and its textbook example.";
	if (code?.includes("place"))
		return "Look again: is the word a place or a cultural object?";
	return "Read each English word and check its meaning again.";
}
