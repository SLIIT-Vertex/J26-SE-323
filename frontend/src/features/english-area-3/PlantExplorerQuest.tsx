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
	PlantExplorerWorkedExample,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../english-area-1/classroom-action-quest.css";
import { PLANT_ASSET_ROOT, PLANT_SKILLS } from "./manifest";
import {
	type Link,
	numberPairResponse,
	plantMappingResponse,
} from "./plantExplorerLogic";
import "./plant-explorer.css";

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

export function PlantExplorerQuest({
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
		PLANT_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = PLANT_SKILLS[index];
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
					area_id: "G5-AREA-ENG-03",
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
			support.game_manifest.schema_version !== "plant-explorer-support-v1"
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
		if (index < PLANT_SKILLS.length - 1)
			void openSkill(PLANT_SKILLS[index + 1].id);
		else setStep(done.length === PLANT_SKILLS.length ? "result" : "games");
	};

	return (
		<main
			className="classroom-action-quest plant-explorer"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<p>Theme 3</p>
					<h1>Plants, Trees and Creepers</h1>
				</div>
			</header>
			{step === "games" ? (
				<section
					className="caq-game-list"
					aria-label="Plants, Trees and Creepers games"
				>
					{PLANT_SKILLS.map((skill, position) => (
						<button
							className="caq-game-card"
							key={skill.id}
							onClick={() => void openSkill(skill.id)}
						>
							<img src={`${PLANT_ASSET_ROOT}/${skill.asset}`} alt="" />
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
						manifest?.game?.schema_version === "plant-explorer-item-v1" && (
							<>
								<div className="caq-command">
									<span>Explore and connect</span>
									<strong>{manifest.prompt_si}</strong>
								</div>
								<PlantActivity
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my garden
								</button>
							</>
						)}
					{step === "support" && support && (
						<PlantSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now explore a fresh plant on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>{correct ? "Great growing!" : friendlyFeedback(feedback)}</h2>
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
								src={`${PLANT_ASSET_ROOT}/plant-explorer-badge.png`}
								alt=""
							/>
							<SuccessCelebration />
							<h2>Plant Explorer Quest complete!</h2>
							<p>You connected plant words independently.</p>
						</section>
					)}
				</section>
			)}
		</main>
	);
}

type Row = Record<string, unknown>;
export function PlantActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	return game.response_kind === "singular_plural_pairing" ? (
		<PairBoard game={game} onResponse={onResponse} />
	) : (
		<MappingBoard game={game} onResponse={onResponse} />
	);
}

function MappingBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const vocabulary = game.response_kind === "plant_vocabulary_mapping";
	const sources = (vocabulary ? game.words : game.labels) as Row[];
	const targets = (vocabulary ? game.targets : game.parts) as Row[];
	const sourceKey = vocabulary ? "word_token" : "label_token";
	const targetKey = vocabulary ? "target_token" : "part_token";
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<Link[]>([]);
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
		if (next.length === sources.length)
			onResponse(
				plantMappingResponse(
					game.response_kind as
						| "plant_vocabulary_mapping"
						| "plant_part_labeling",
					String(game.command_token),
					next,
					sources.map((row) => String(row[sourceKey])),
					nextTrace,
				),
			);
	};
	return (
		<section className="plant-board">
			<div className="plant-scene">
				<img
					src={`${PLANT_ASSET_ROOT}/${String(game.scene_asset)}`}
					alt="Illustrated plant scene"
				/>
			</div>
			<div className="plant-word-rail">
				{sources.map((row) => {
					const id = String(row[sourceKey]);
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
			<div className="plant-targets">
				{targets.map((row) => {
					const id = String(row[targetKey]);
					const link = links.find((entry) => entry.target === id);
					const source = sources.find(
						(entry) => String(entry[sourceKey]) === link?.source,
					);
					return (
						<button
							className="plant-target"
							key={id}
							disabled={!selected}
							onClick={() => place(id)}
						>
							{visualName(String(row.visual_key))}
							<span>{source ? String(source.text_en) : "Choose a word"}</span>
						</button>
					);
				})}
			</div>
		</section>
	);
}

function PairBoard({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const concepts = game.concepts as Row[];
	const forms = game.forms as Row[];
	const [selected, setSelected] = useState<string | null>(null);
	const [pairs, setPairs] = useState<
		Record<string, { singular?: string; plural?: string }>
	>({});
	const [trace, setTrace] = useState<string[]>([]);
	const place = (concept: string, slot: "singular" | "plural") => {
		if (!selected) return;
		const next = {
			...pairs,
			[concept]: { ...pairs[concept], [slot]: selected },
		};
		const nextTrace = [...trace, `${slot}:${selected}:${concept}`];
		setPairs(next);
		setTrace(nextTrace);
		setSelected(null);
		if (
			concepts.every(
				(row) =>
					next[String(row.concept_token)]?.singular &&
					next[String(row.concept_token)]?.plural,
			)
		)
			onResponse(
				numberPairResponse(
					String(game.command_token),
					concepts.map((row) => ({
						concept_token: String(row.concept_token),
						singular_form_token: String(
							next[String(row.concept_token)].singular,
						),
						plural_form_token: String(next[String(row.concept_token)].plural),
					})),
					nextTrace,
				),
			);
	};
	const used = Object.values(pairs).flatMap((pair) => [
		pair.singular,
		pair.plural,
	]);
	return (
		<section className="plant-board">
			<div className="plant-form-rail">
				{forms.map((row) => {
					const id = String(row.form_token);
					return (
						<button
							key={id}
							className={selected === id ? "selected" : ""}
							disabled={used.includes(id)}
							onClick={() => setSelected(id)}
						>
							{String(row.text_en)}
						</button>
					);
				})}
			</div>
			<div className="pair-grid">
				{concepts.map((row) => {
					const id = String(row.concept_token);
					const pair = pairs[id] ?? {};
					return (
						<div className="pair-card" key={id}>
							<img
								src={`${PLANT_ASSET_ROOT}/${String(row.single_asset)}`}
								alt="One plant part"
							/>
							<button
								className="pair-slot"
								disabled={!selected}
								onClick={() => place(id, "singular")}
							>
								{formText(forms, pair.singular) || "One"}
							</button>
							<button
								className="pair-slot"
								disabled={!selected}
								onClick={() => place(id, "plural")}
							>
								{formText(forms, pair.plural) || "Many"}
							</button>
						</div>
					);
				})}
			</div>
		</section>
	);
}

function PlantSupport({
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
	if (support.game_manifest.schema_version !== "plant-explorer-support-v1")
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's grow another way</h2>
			<PlantWorkedExample
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
function PlantWorkedExample({
	example,
	reveal,
}: {
	example: PlantExplorerWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	return (
		<div className="caq-worked plant-support-preview">
			<strong>{example.prompt_si}</strong>
			<span>
				{reveal && response
					? response.kind === "singular_plural_pairing"
						? `${response.pairs.length} pairs completed`
						: response.kind === "plant_vocabulary_mapping"
							? `${response.placements.length} words connected`
							: response.kind === "plant_part_labeling"
								? `${response.labels.length} parts labelled`
								: "Plant connection shown"
					: "?"}
			</span>
		</div>
	);
}
function visualName(value: string) {
	return value
		.replace(/-slot/g, "")
		.replace(/-/g, " ")
		.replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function formText(forms: Row[], token?: string) {
	return token
		? String(forms.find((row) => row.form_token === token)?.text_en ?? "")
		: "";
}
function friendlyFeedback(code: string | null) {
	if (code?.includes("number") || code?.includes("plural"))
		return "Look at one and many, then check the word ending.";
	if (code?.includes("stem") || code?.includes("root"))
		return "Look carefully at where the plant part grows.";
	return "Read the plant word and look at the picture again.";
}
