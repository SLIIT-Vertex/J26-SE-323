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
import "./bloom-builder-garden.css";
import { type BloomLink, flowerMappingResponse } from "./bloomBuilderLogic";
import { BLOOM_SKILL, BLOOM_STAGES } from "./manifest";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type Word = { word_token: string; text_en: string };
type Flower = { flower_token: string; renderer_variant: number };

export function BloomBuilderGarden({
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

	const openQuest = async () => {
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
					area_id: "G5-AREA-ENG-10",
					atomic_skill_id: BLOOM_SKILL.id,
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
				detail_sheet_open_count:
					response.kind === "flower_vocabulary_mapping"
						? response.detail_sheet_open_count
						: 0,
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
			support.game_manifest.schema_version !== "bloom-builder-garden-support-v1"
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
	const game =
		manifest?.game?.schema_version === "bloom-builder-garden-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main
			className="classroom-action-quest bloom-builder-garden"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Home Garden</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list" aria-label="Home Garden games">
					<button className="caq-game-card" onClick={() => void openQuest()}>
						<span className="object-icon" aria-hidden="true">
							{BLOOM_SKILL.icon}
						</span>
						<span>
							<strong>{BLOOM_SKILL.name}</strong>
							<small>{BLOOM_SKILL.description}</small>
							<em>3 stages · Easy to challenging</em>
						</span>
					</button>
					<StageStrip />
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
					<StageStrip active={game ? String(game.chapter) : undefined} />
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<span className="code-companion" aria-hidden="true">
									🪴✨
								</span>
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<BloomActivity
								key={manifest?.revision_id}
								game={game}
								onResponse={(value) => {
									setResponse(value);
									setMoves((count) => count + 1);
								}}
							/>
							<button
								className="caq-primary"
								disabled={
									busy ||
									!response ||
									(response.kind === "flower_vocabulary_mapping" &&
										response.unplaced_word_tokens.length > 0)
								}
								onClick={confirm}
							>
								Check my garden
							</button>
						</>
					)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={
								response !== null &&
								!(
									response.kind === "flower_vocabulary_mapping" &&
									response.unplaced_word_tokens.length > 0
								)
							}
							checkLabel="Check my garden"
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
								<BloomActivity
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
						<BloomSupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							The garden hint is fading. A fresh flower set is growing for you.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Beautiful bloom building!"
									: "Look at the petal and centre shapes, then try again."}
							</h2>
							<button
								className="caq-primary"
								onClick={() => (correct ? setStep("result") : void openQuest())}
							>
								{correct ? "Collect garden badge" : "Try a fresh garden"}
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

function StageStrip({ active }: { active?: string }) {
	return (
		<div className="bloom-stage-strip">
			{Object.entries(BLOOM_STAGES).map(([key, item]) => (
				<span
					className="bloom-stage-chip"
					data-active={key === active}
					key={key}
				>
					<span>{item.icon}</span>
					<strong>{item.name}</strong>
					{item.level}
				</span>
			))}
		</div>
	);
}

function FlowerGlyph({ variant }: { variant: number }) {
	return (
		<span className="flower-glyph" data-variant={variant} aria-hidden="true">
			<span />
		</span>
	);
}

function BloomActivity({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	const words = game.words as Word[];
	const flowers = game.flowers as Flower[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<BloomLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const [detail, setDetail] = useState<Flower | null>(null);
	const [detailCount, setDetailCount] = useState(0);
	const closeRef = useRef<HTMLButtonElement | null>(null);
	useEffect(() => {
		if (detail) closeRef.current?.focus();
	}, [detail]);
	const emit = (
		nextLinks: BloomLink[],
		nextTrace: string[],
		count = detailCount,
	) =>
		onResponse(
			flowerMappingResponse(
				String(game.command_token),
				nextLinks,
				words.map((word) => word.word_token),
				nextTrace,
				count,
			),
		);
	const place = (target: string) => {
		if (!selected) return;
		const filtered = links.filter(
			(link) => link.source !== selected && link.target !== target,
		);
		const replacing = links.some(
			(link) => link.target === target || link.source === selected,
		);
		const next = [
			...filtered,
			{ sequence: filtered.length + 1, source: selected, target },
		];
		const nextTrace = [
			...trace,
			`${replacing ? "replace" : "place"}:${selected}:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		emit(next, nextTrace);
	};
	const openDetail = (flower: Flower) => {
		const count = detailCount + 1;
		const nextTrace = [...trace, `detail-open:${flower.flower_token}`];
		setDetail(flower);
		setDetailCount(count);
		setTrace(nextTrace);
		emit(links, nextTrace, count);
	};
	return (
		<section>
			<p className="bloom-hint">
				Tap a seed packet, then its flower. Use the magnifier to inspect
				structure.
			</p>
			<div className="seed-packet-tray">
				{words.map((word) => (
					<button
						className="seed-packet"
						data-opaque-token={word.word_token}
						key={word.word_token}
						aria-pressed={selected === word.word_token}
						disabled={links.some((link) => link.source === word.word_token)}
						onClick={() => {
							setSelected(word.word_token);
							setTrace((old) => [...old, `select:${word.word_token}`]);
						}}
					>
						{word.text_en}
					</button>
				))}
			</div>
			<div className="garden-bed">
				{flowers.map((flower) => {
					const link = links.find(
						(item) => item.target === flower.flower_token,
					);
					const word = words.find((item) => item.word_token === link?.source);
					return (
						<div
							className="flower-target"
							data-selected={Boolean(word)}
							key={flower.flower_token}
						>
							<button
								className="flower-detail-button"
								aria-label="Enlarge flower structure"
								onClick={() => openDetail(flower)}
							>
								🔎
							</button>
							<button
								className="flower-target-hit"
								data-opaque-token={flower.flower_token}
								aria-label={
									word
										? `Matched to ${word.text_en}`
										: "Unmatched flower structure"
								}
								onClick={() => place(flower.flower_token)}
							>
								<FlowerGlyph variant={flower.renderer_variant} />
								<strong>{word?.text_en ?? "?"}</strong>
							</button>
						</div>
					);
				})}
			</div>
			{detail && (
				<div
					className="flower-detail"
					role="dialog"
					aria-modal="true"
					aria-label="Flower structure detail"
				>
					<div className="flower-detail-card">
						<h2>Look closely</h2>
						<FlowerGlyph variant={detail.renderer_variant} />
						<p>
							Notice petal arrangement, centre shape, and whether blooms form a
							cluster. Colour is not the only clue.
						</p>
						<button
							ref={closeRef}
							className="caq-primary"
							onClick={() => {
								setTrace((old) => [
									...old,
									`detail-close:${detail.flower_token}`,
								]);
								setDetail(null);
							}}
						>
							Close detail
						</button>
					</div>
				</div>
			)}
		</section>
	);
}

function BloomSupport({
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
		support.game_manifest.schema_version !== "bloom-builder-garden-support-v1"
	)
		return null;
	const required = support.game_manifest.required_actions;
	return (
		<section className="caq-support">
			<div className="object-icon" aria-hidden="true">
				🌼🔍
			</div>
			<h2>{support.title_si}</h2>
			<p>{support.body_si[Math.min(stage, support.body_si.length - 1)]}</p>
			<p className="bloom-hint">
				Hint step {Math.min(stage, required)} of {required}
			</p>
			<button
				className="caq-primary"
				onClick={stage < required ? onNext : onComplete}
			>
				{stage < required ? "Show next garden clue" : "I’m ready to grow alone"}
			</button>
		</section>
	);
}
