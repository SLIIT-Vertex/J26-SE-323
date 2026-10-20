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
	EverydayObjectWorkedExample,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../english-area-1/classroom-action-quest.css";
import "./everyday-object-quest.css";
import {
	type ObjectLink,
	objectMappingResponse,
	objectNameResponse,
} from "./everydayObjectLogic";
import { OBJECT_SKILLS } from "./manifest";

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

const GLYPHS = [
	"🪑",
	"✏️",
	"📏",
	"🛏️",
	"🥄",
	"🪥",
	"🧹",
	"🍽️",
	"📘",
	"📒",
	"🧰",
	"📔",
	"✏️⚙️",
	"📎⚙️",
] as const;

export function EverydayObjectQuest({
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
		OBJECT_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = OBJECT_SKILLS[index];
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
					area_id: "G5-AREA-ENG-05",
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
			support.game_manifest.schema_version !==
				"everyday-object-quest-support-v1"
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
		if (index < OBJECT_SKILLS.length - 1)
			void openSkill(OBJECT_SKILLS[index + 1].id);
		else setStep(done.length === OBJECT_SKILLS.length ? "result" : "games");
	};
	return (
		<main
			className="classroom-action-quest everyday-object-quest"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<p>Theme 5</p>
					<h1>What we use</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list" aria-label="What we use games">
					{OBJECT_SKILLS.map((skill, position) => (
						<button
							className="caq-game-card"
							key={skill.id}
							onClick={() => void openSkill(skill.id)}
						>
							<span className="object-icon" aria-hidden="true">
								{skill.icon}
							</span>
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
						manifest?.game?.schema_version ===
							"everyday-object-quest-item-v1" && (
							<>
								<div className="caq-command">
									<span className="code-companion" aria-hidden="true">
										✏️✨📏
									</span>
									<strong>{manifest.prompt_si}</strong>
								</div>
								<ObjectActivity
									key={manifest.revision_id}
									game={manifest.game as Record<string, unknown>}
									onResponse={record}
								/>
								<button
									className="caq-primary"
									disabled={busy || !response}
									onClick={confirm}
								>
									Check my objects
								</button>
							</>
						)}
					{step === "support" && support && (
						<ObjectSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The help is going away. Now tidy a fresh set on your own.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Brilliant tidying!"
									: "Read the word and inspect the object again."}
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
							<div className="object-icon" aria-hidden="true">
								🏅
							</div>
							<SuccessCelebration />
							<h2>Everyday Object Quest complete!</h2>
							<p>You connected object words independently.</p>
						</section>
					)}
				</section>
			)}
		</main>
	);
}

type Row = Record<string, unknown>;
function ObjectGlyph({ variant }: { variant: number }) {
	return (
		<span className="object-icon" aria-hidden="true">
			{GLYPHS[variant] ?? "🔷"}
		</span>
	);
}
export function ObjectActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	return game.response_kind === "object_name_sequence" ? (
		<NameBuilder game={game} onResponse={onResponse} />
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
	const vocabulary = game.response_kind === "object_vocabulary_mapping";
	const sources = (vocabulary ? game.words : game.entries) as Row[];
	const targets = (vocabulary ? game.objects : game.zones) as Row[];
	const sourceKey = vocabulary ? "word_token" : "entry_token";
	const targetKey = vocabulary ? "object_token" : "zone_token";
	const kind = game.response_kind as
		| "object_vocabulary_mapping"
		| "lesson_place_sort";
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<ObjectLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const place = (target: string) => {
		if (!selected) return;
		const old = links.find(
			(link) =>
				link.source === selected || (vocabulary && link.target === target),
		);
		const next = links.filter(
			(link) =>
				link.source !== selected && (!vocabulary || link.target !== target),
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
				objectMappingResponse(
					kind,
					String(game.command_token),
					next,
					sources.map((row) => String(row[sourceKey])),
					nextTrace,
				),
			);
	};
	return (
		<section className="object-board">
			<div className="object-word-rail">
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
			<div className={vocabulary ? "object-workbench" : "room-zones"}>
				{targets.map((row) => {
					const id = String(row[targetKey]);
					const linked = links.filter((entry) => entry.target === id);
					const labels = linked.map((link) =>
						String(
							sources.find((entry) => String(entry[sourceKey]) === link.source)
								?.text_en ?? "",
						),
					);
					return (
						<button
							className={vocabulary ? "object-target" : "room-zone"}
							key={id}
							disabled={!selected}
							onClick={() => place(id)}
						>
							{vocabulary ? (
								<ObjectGlyph variant={Number(row.renderer_variant)} />
							) : (
								<strong>{String(row.display_en)}</strong>
							)}
							<span>
								{labels.length ? labels.join(" · ") : "Choose a word"}
							</span>
						</button>
					);
				})}
			</div>
		</section>
	);
}
function NameBuilder({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(value: ConstructedResponse): void;
}) {
	const chunks = game.chunks as Row[];
	const [ordered, setOrdered] = useState<string[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const add = (token: string) => {
		if (ordered.includes(token)) return;
		const next = [...ordered, token];
		const nextTrace = [...trace, `slot:${token}:${next.length}`];
		setOrdered(next);
		setTrace(nextTrace);
		if (next.length === chunks.length)
			onResponse(
				objectNameResponse(
					String(game.command_token),
					String(game.object_token),
					next,
					nextTrace,
				),
			);
	};
	const remove = (token: string) => {
		const next = ordered.filter((value) => value !== token);
		setOrdered(next);
		setTrace((value) => [...value, `remove:${token}`]);
	};
	return (
		<section className="name-builder">
			<ObjectGlyph variant={Number(game.renderer_variant)} />
			<div className="phrase-slots">
				{Array.from({ length: chunks.length }, (_, index) => {
					const token = ordered[index];
					const row = chunks.find((entry) => entry.chunk_token === token);
					return (
						<button
							key={`slot-${String(chunks[index]?.chunk_token)}`}
							disabled={!token}
							onClick={() => token && remove(token)}
						>
							{row ? String(row.text_en) : `Word ${index + 1}`}
						</button>
					);
				})}
			</div>
			<div className="chunk-rail">
				{chunks.map((row) => {
					const token = String(row.chunk_token);
					return (
						<button
							key={token}
							disabled={ordered.includes(token)}
							onClick={() => add(token)}
						>
							{String(row.text_en)}
						</button>
					);
				})}
			</div>
		</section>
	);
}
function ObjectSupport({
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
		support.game_manifest.schema_version !== "everyday-object-quest-support-v1"
	)
		return null;
	const game = support.game_manifest;
	return (
		<section className="caq-support">
			<p>Help type: {support.title_si}</p>
			<h2>Let's tidy another example</h2>
			<ObjectWorkedExample
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
function ObjectWorkedExample({
	example,
	reveal,
}: {
	example: EverydayObjectWorkedExample;
	reveal: boolean;
}) {
	const response = example.correct_response;
	const count = response
		? response.kind === "object_name_sequence"
			? response.ordered_chunk_tokens.length
			: response.kind === "object_vocabulary_mapping" ||
					response.kind === "lesson_place_sort"
				? response.placements.length
				: 0
		: 0;
	return (
		<div className="wildlife-support-preview">
			<strong>{example.prompt_si}</strong>
			<span>
				{reveal ? `${count} connections shown on a fresh example` : "?"}
			</span>
		</div>
	);
}
