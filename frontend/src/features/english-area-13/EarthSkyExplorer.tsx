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
} from "../mobile-learning-flow/api/generated";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import "../mobile-learning-flow/english-game-shared.css";
import "./earth-sky-explorer.css";
import {
	type ExplorerLink,
	bilingualResponse,
	sceneResponse,
} from "./earthSkyLogic";
import { EARTH_SKY_SKILLS } from "./manifest";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type TokenRow = Record<string, unknown>;

export function EarthSkyExplorer({
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
		EARTH_SKY_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = EARTH_SKY_SKILLS[index];
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
					area_id: "G5-AREA-ENG-13",
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
					"invalid_drop_count" in response
						? response.invalid_drop_count
						: "invalid_link_count" in response
							? response.invalid_link_count
							: 0,
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
			support.game_manifest.schema_version !== "earth-sky-explorer-support-v1"
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
		if (index < EARTH_SKY_SKILLS.length - 1)
			void openSkill(EARTH_SKY_SKILLS[index + 1].id);
		else setStep(done.length === EARTH_SKY_SKILLS.length ? "result" : "games");
	};
	const game =
		manifest?.game?.schema_version === "earth-sky-explorer-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main
			className="classroom-action-quest earth-sky-explorer"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Earth &amp; Sky</h1>
				</div>
			</header>
			{step === "games" ? (
				<section
					className="caq-game-list"
					aria-label="Earth and Sky Explorer games"
				>
					<div className="es-observatory" aria-hidden="true">
						<i />
						<i />
						<i />
						<span>🔭</span>
					</div>
					<div className="es-stage-strip">
						<span>1 · Signal Bridge</span>
						<span>2 · Panorama</span>
						<span>3 · Nature Lens</span>
					</div>
					{EARTH_SKY_SKILLS.map((skill, position) => (
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
								<em>{position + 1}/2 · Separate measured skill</em>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
							activityCount={2}
							currentActivity={index + 1}
							completedActivities={completed.length}
						/>
					)}
					<p className="caq-position">
						Activity {index + 1}/2 · {active.name}
					</p>
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<span aria-hidden="true">🧭✨</span>
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<ExplorerActivity
								key={manifest?.revision_id}
								game={game}
								onResponse={(value) => {
									setResponse(value);
									setMoves((count) => count + 1);
								}}
							/>
							<button
								className="caq-primary"
								disabled={busy || !response || incomplete(response)}
								onClick={confirm}
							>
								Check my explorer links
							</button>
						</>
					)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null && !incomplete(response)}
							checkLabel="Check my explorer links"
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
								<ExplorerActivity
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
					{step === "support" && support && !isSupportRound(support) && (
						<ExplorerSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							All clues, examples, selections, and lens details are clearing.
							Explore a fresh set alone.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Explorer badge earned!"
									: "Look closely and rebuild every link."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct
									? index === 1
										? "Finish expedition"
										: "Next activity"
									: "Try a fresh observation"}
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={2}
							gameCount={2}
							onContinue={() => setStep("games")}
						/>
					)}
				</section>
			)}
		</main>
	);
}

function incomplete(response: ConstructedResponse) {
	return response.kind === "earth_sky_bilingual_links"
		? response.unlinked_english_tokens.length > 0
		: response.kind === "earth_sky_scene_mapping"
			? response.unplaced_word_tokens.length > 0
			: true;
}
function ExplorerActivity({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	return game.response_kind === "earth_sky_bilingual_links" ? (
		<BridgeBoard game={game} onResponse={onResponse} />
	) : (
		<PanoramaBoard game={game} onResponse={onResponse} />
	);
}

function BridgeBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	const sources = game.english_words as TokenRow[];
	const targets = game.sinhala_words as TokenRow[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<ExplorerLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const connect = (target: string) => {
		if (!selected) return;
		const old = links.find(
			(link) => link.source === selected || link.target === target,
		);
		const filtered = links.filter(
			(link) => link.source !== selected && link.target !== target,
		);
		const next = [
			...filtered,
			{ sequence: filtered.length + 1, source: selected, target },
		];
		const nextTrace = [...trace, `${old ? "replace" : "link"}:${target}`];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		onResponse(
			bilingualResponse(
				String(game.command_token),
				next,
				sources.map((row) => String(row.english_token)),
				nextTrace,
			),
		);
	};
	return (
		<section className="es-board">
			<p className="es-instruction">
				Tap an English signal, then its Sinhala lesson word.
			</p>
			<div className="es-token-grid">
				{sources.map((row) => (
					<button
						className="es-word"
						data-opaque-token={String(row.english_token)}
						key={String(row.english_token)}
						aria-pressed={selected === row.english_token}
						disabled={links.some((link) => link.source === row.english_token)}
						onClick={() => setSelected(String(row.english_token))}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
			{selected && (
				<p className="es-selected" role="status">
					Signal selected · choose a Sinhala word
				</p>
			)}
			<div className="es-token-grid es-si">
				{targets.map((row) => {
					const link = links.find((item) => item.target === row.sinhala_token);
					return (
						<button
							className="es-word"
							data-opaque-token={String(row.sinhala_token)}
							data-linked={Boolean(link)}
							key={String(row.sinhala_token)}
							onClick={() => connect(String(row.sinhala_token))}
						>
							{String(row.text_si)}
							<small>{link ? "✓ linked" : "tap to link"}</small>
						</button>
					);
				})}
			</div>
		</section>
	);
}

function PanoramaBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	const words = game.words as TokenRow[];
	const scenes = game.scenes as TokenRow[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<ExplorerLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const [lens, setLens] = useState<string | null>(null);
	const place = (target: string) => {
		if (!selected) return;
		const old = links.find(
			(link) => link.source === selected || link.target === target,
		);
		const filtered = links.filter(
			(link) => link.source !== selected && link.target !== target,
		);
		const next = [
			...filtered,
			{ sequence: filtered.length + 1, source: selected, target },
		];
		const nextTrace = [...trace, `${old ? "replace" : "place"}:${target}`];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		onResponse(
			sceneResponse(
				String(game.command_token),
				next,
				words.map((row) => String(row.word_token)),
				nextTrace,
			),
		);
	};
	return (
		<section className="es-board">
			<p className="es-instruction">
				Choose a word, inspect each code-built card, then place it.
			</p>
			<div className="es-token-grid">
				{words.map((row) => (
					<button
						className="es-word"
						data-opaque-token={String(row.word_token)}
						key={String(row.word_token)}
						aria-pressed={selected === row.word_token}
						disabled={links.some((link) => link.source === row.word_token)}
						onClick={() => setSelected(String(row.word_token))}
					>
						{String(row.text_en)}
					</button>
				))}
			</div>
			{selected && (
				<p className="es-selected" role="status">
					Word selected · choose an observation card
				</p>
			)}
			<div className="es-panorama">
				{scenes.map((row, cardIndex) => {
					const token = String(row.scene_token);
					const link = links.find((item) => item.target === token);
					const word = words.find((item) => item.word_token === link?.source);
					const expanded = lens === token;
					return (
						<article
							className="es-card"
							data-v={Number(row.renderer_variant)}
							key={token}
						>
							<button
								className="es-card-target"
								data-opaque-token={token}
								data-linked={Boolean(link)}
								aria-label={`Observation card ${cardIndex + 1}${link ? `, matched to ${String(word?.text_en)}` : ", unmatched"}`}
								onClick={() => place(token)}
							>
								<ScenePrimitive
									variant={Number(row.renderer_variant)}
									expanded={expanded}
								/>
								<strong>{word ? String(word.text_en) : "?"}</strong>
							</button>
							{game.lens_enabled === true && (
								<button
									className="es-lens"
									aria-expanded={expanded}
									aria-label={`${expanded ? "Close" : "Open"} structural detail for observation card ${cardIndex + 1}`}
									onClick={() => {
										setLens(expanded ? null : token);
										setTrace((current) => [
											...current,
											`${expanded ? "lens-close" : "lens-open"}:${token}`,
										]);
									}}
								>
									⌕ {expanded ? "Close" : "Inspect"}
								</button>
							)}
						</article>
					);
				})}
			</div>
		</section>
	);
}

function ScenePrimitive({
	variant,
	expanded,
}: {
	variant: number;
	expanded: boolean;
}) {
	return (
		<span
			className="es-scene"
			data-v={variant}
			data-expanded={expanded || undefined}
			aria-hidden="true"
		>
			<i />
			<i />
			<i />
			<b />
		</span>
	);
}
function ExplorerSupport({
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
	if (support.game_manifest.schema_version !== "earth-sky-explorer-support-v1")
		return null;
	const required = support.game_manifest.required_actions;
	return (
		<section className="caq-support">
			<div className="object-icon" aria-hidden="true">
				🔭✨
			</div>
			<h2>{support.title_si}</h2>
			<p>{support.body_si[Math.min(stage, support.body_si.length - 1)]}</p>
			<ol>
				{support.game_manifest.worked_example.steps_si.map((text, index) => (
					<li className={index < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="caq-primary"
				onClick={stage < required ? onNext : onComplete}
			>
				{stage < required
					? "Show next explorer step"
					: "I’m ready to explore alone"}
			</button>
		</section>
	);
}
