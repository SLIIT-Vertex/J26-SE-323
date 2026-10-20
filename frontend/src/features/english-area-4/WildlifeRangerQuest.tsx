// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
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
	WildlifeRangerWorkedExample,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../english-area-1/classroom-action-quest.css";
import { WILDLIFE_ASSET_ROOT, WILDLIFE_SKILLS } from "./manifest";
import "./wildlife-ranger.css";
import {
	type WildlifeLink,
	wildlifeMappingResponse,
} from "./wildlifeRangerLogic";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Api = Pick<
	LearningFlowClient,
	| "open"
	| "answerBefore"
	| "completeSupport"
	| "withdrawSupport"
	| "presentAfter"
	| "answerAfter"
>;

export function WildlifeRangerQuest({
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
	const [skillId, setSkillId] = useState<string | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false);
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
		WILDLIFE_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = WILDLIFE_SKILLS[index];
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
					area_id: "G5-AREA-ENG-04",
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
			support.game_manifest.schema_version !== "wildlife-ranger-support-v1"
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
		if (index < WILDLIFE_SKILLS.length - 1)
			void openSkill(WILDLIFE_SKILLS[index + 1].id);
		else setStep(done.length === WILDLIFE_SKILLS.length ? "result" : "games");
	};

	return (
		<main
			className="classroom-action-quest wildlife-ranger"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<p>Theme 4</p>
					<h1>Animals around us</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list" aria-label="Animals around us games">
					{WILDLIFE_SKILLS.map((skill, position) => (
						<button
							className="caq-game-card"
							key={skill.id}
							onClick={() => void openSkill(skill.id)}
						>
							<img src={`${WILDLIFE_ASSET_ROOT}/${skill.asset}`} alt="" />
							<span>
								<strong>{skill.name}</strong>
								<small>{skill.description}</small>
								<em>{position + 1}/3 · Easy to challenging</em>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={3}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="caq-position">
						Activity {index + 1}/3 · {active.name}
					</p>
					{step === "question" &&
						manifest?.game?.schema_version === "wildlife-ranger-item-v1" && (
							<>
								<div className="caq-command">
									<span>Explore and connect</span>
									<strong>{manifest.prompt_si}</strong>
								</div>
								<WildlifeBoard
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my trail
								</button>
							</>
						)}
					{step === "support" && support && (
						<WildlifeSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now meet a fresh animal on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Excellent spotting!"
									: "Look at the animal and read the English word again."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct
									? index === 2
										? "Finish quest"
										: "Next activity"
									: "Try another one"}
							</button>
						</section>
					)}
					{step === "result" && (
						<section className="caq-feedback caq-result">
							<img
								src={`${WILDLIFE_ASSET_ROOT}/wildlife-ranger-badge.png`}
								alt=""
							/>
							<SuccessCelebration />
							<h2>Wildlife Ranger Quest complete!</h2>
							<p>You connected animal words independently.</p>
						</section>
					)}
				</section>
			)}
		</main>
	);
}

type Row = Record<string, unknown>;
export function WildlifeBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const entries = game.entries as Row[];
	const targets = game.targets as Row[];
	const kind = game.response_kind as
		| "animal_vocabulary_mapping"
		| "lesson_heading_sort"
		| "animal_part_labeling";
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<WildlifeLink[]>([]);
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
			`${old ? "replace" : "place"}:${selected}:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		if (next.length === entries.length)
			onResponse(
				wildlifeMappingResponse(
					kind,
					String(game.command_token),
					next,
					entries.map((row) => String(row.entry_token)),
					nextTrace,
				),
			);
	};
	return (
		<section className="wildlife-board">
			<div className="wildlife-word-rail">
				{entries.map((row) => {
					const id = String(row.entry_token);
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
			{kind !== "lesson_heading_sort" && (
				<div
					className={`wildlife-scene ${kind === "animal_part_labeling" ? "body-map" : ""}`}
				>
					<img
						src={`${WILDLIFE_ASSET_ROOT}/${String(game.scene_asset)}`}
						alt="Illustrated animal scene"
					/>
					{kind === "animal_part_labeling" &&
						targets.map((row) => {
							const id = String(row.target_token);
							const link = links.find((entry) => entry.target === id);
							const source = entries.find(
								(entry) => String(entry.entry_token) === link?.source,
							);
							return (
								<button
									className="body-marker"
									style={{
										left: `${Number(row.x_percent)}%`,
										top: `${Number(row.y_percent)}%`,
									}}
									key={id}
									disabled={!selected}
									onClick={() => place(id)}
									aria-label={`Body-part marker ${Number(row.marker_index)}`}
								>
									<strong>{Number(row.marker_index)}</strong>
									<span>{source ? String(source.text_en) : ""}</span>
								</button>
							);
						})}
				</div>
			)}
			{kind !== "animal_part_labeling" && (
				<div className="wildlife-targets">
					{targets.map((row) => {
						const id = String(row.target_token ?? row.heading_token);
						const link = links.find((entry) => entry.target === id);
						const source = entries.find(
							(entry) => String(entry.entry_token) === link?.source,
						);
						const sprite = Number(row.sprite_index ?? 0);
						return (
							<button
								className={`wildlife-target ${kind === "lesson_heading_sort" ? "heading" : ""}`}
								key={id}
								disabled={!selected}
								onClick={() => place(id)}
							>
								{kind === "animal_vocabulary_mapping" && (
									<span
										className={`animal-sprite sprite-${sprite}`}
										role="img"
										aria-label="Animal target"
									/>
								)}
								{kind === "lesson_heading_sort" && (
									<strong>{String(row.text_en)}</strong>
								)}
								<span>{source ? String(source.text_en) : "Choose a word"}</span>
							</button>
						);
					})}
				</div>
			)}
		</section>
	);
}

function WildlifeSupport({
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
	if (support.game_manifest.schema_version !== "wildlife-ranger-support-v1")
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's explore another example</h2>
			<WildlifeWorkedExample
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
function WildlifeWorkedExample({
	example,
	reveal,
}: {
	example: WildlifeRangerWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	const count =
		response &&
		(response.kind === "animal_part_labeling"
			? response.labels.length
			: response.kind === "animal_vocabulary_mapping" ||
					response.kind === "lesson_heading_sort"
				? response.placements.length
				: 0);
	return (
		<div className="wildlife-support-preview">
			<strong>{example.prompt_si}</strong>
			<span>
				{reveal ? `${count} connections shown on a fresh example` : "?"}
			</span>
		</div>
	);
}
