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
import "./workplace-link-city.css";
import { WORK_SKILLS } from "./manifest";
import {
	type CityLink,
	occupationPlaceResponse,
	workVocabularyResponse,
} from "./workplaceLinkLogic";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type Word = { word_token: string; text_en: string };
type Representation = {
	representation_token: string;
	renderer_variant: number;
};
type Occupation = { occupation_token: string; text_en: string };
type Place = {
	place_token: string;
	text_en: string;
	renderer_variant: number;
	capacity: number;
};
const CUES = ["🌾", "🐟", "📚", "❤", "⚡", "🧱", "🪚"] as const;
const PLACE_MARKS = ["🌾", "🐟", "🏫", "🏥", "🏙️", "🛠️"] as const;

export function WorkplaceLinkCity({
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
		WORK_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = WORK_SKILLS[index];
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
					area_id: "G5-AREA-ENG-11",
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
			support.game_manifest.schema_version !== "workplace-link-city-support-v1"
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
		if (index < WORK_SKILLS.length - 1)
			void openSkill(WORK_SKILLS[index + 1].id);
		else setStep(done.length === WORK_SKILLS.length ? "result" : "games");
	};
	const game =
		manifest?.game?.schema_version === "workplace-link-city-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main
			className="classroom-action-quest workplace-link-city"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Ways of Making Work Easy</h1>
				</div>
			</header>
			{step === "games" ? (
				<section
					className="caq-game-list"
					aria-label="Workplace Link City games"
				>
					<div className="city-skyline">
						<span className="city-chip">
							🏷️<strong>Badge Match</strong>Words
						</span>
						<span className="city-chip">
							🔗<strong>Route Connector</strong>Pairs
						</span>
						<span className="city-chip">
							🏙️<strong>City Network</strong>Shared hubs
						</span>
					</div>
					{WORK_SKILLS.map((skill, position) => (
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
								<span className="code-companion" aria-hidden="true">
									🏙️✨
								</span>
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<CityActivity
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
								Check my city links
							</button>
						</>
					)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null && !incomplete(response)}
							checkLabel="Check my city links"
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
								<CityActivity
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
						<CitySupport
							support={support}
							stage={supportStage}
							onNext={() => setSupportStage((value) => value + 1)}
							onComplete={finishSupport}
						/>
					)}
					{step === "withdrawing" && (
						<p className="caq-status" role="status">
							All hints and example routes are clearing. Build a fresh route
							alone.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "City link complete!"
									: "Read the lesson words and rebuild the links."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct
									? index === 1
										? "Finish city"
										: "Next activity"
									: "Try a fresh route"}
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
	return response.kind === "work_vocabulary_mapping"
		? response.unplaced_word_tokens.length > 0
		: response.kind === "occupation_place_links"
			? response.unlinked_occupation_tokens.length > 0
			: true;
}
function WorkerGlyph({ variant }: { variant: number }) {
	return (
		<span className="neutral-worker" aria-hidden="true">
			<span>{CUES[variant] ?? "●"}</span>
		</span>
	);
}

function CityActivity({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	if (game.response_kind === "work_vocabulary_mapping")
		return <VocabularyBoard game={game} onResponse={onResponse} />;
	return <RouteBoard game={game} onResponse={onResponse} />;
}

function VocabularyBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	const words = game.words as Word[];
	const representations = game.representations as Representation[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<CityLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const place = (target: string) => {
		if (!selected) return;
		const filtered = links.filter(
			(link) => link.source !== selected && link.target !== target,
		);
		const next = [
			...filtered,
			{ sequence: filtered.length + 1, source: selected, target },
		];
		const nextTrace = [
			...trace,
			`${links.length === filtered.length ? "place" : "replace"}:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		onResponse(
			workVocabularyResponse(
				String(game.command_token),
				next,
				words.map((word) => word.word_token),
				nextTrace,
			),
		);
	};
	return (
		<section>
			<p className="city-instruction">
				Tap a badge, then the matching neutral worker card.
			</p>
			<div className="badge-tray">
				{words.map((word) => (
					<button
						className="work-label"
						data-opaque-token={word.word_token}
						key={word.word_token}
						aria-pressed={selected === word.word_token}
						disabled={links.some((link) => link.source === word.word_token)}
						onClick={() => setSelected(word.word_token)}
					>
						{word.text_en}
					</button>
				))}
			</div>
			<div className="work-card-grid">
				{representations.map((representation) => {
					const link = links.find(
						(item) => item.target === representation.representation_token,
					);
					const word = words.find((item) => item.word_token === link?.source);
					return (
						<button
							className="work-card"
							data-opaque-token={representation.representation_token}
							data-selected={Boolean(word)}
							key={representation.representation_token}
							aria-label={
								word
									? `Matched to ${word.text_en}`
									: "Unmatched neutral worker card"
							}
							onClick={() => place(representation.representation_token)}
						>
							<WorkerGlyph variant={representation.renderer_variant} />
							<strong>{word?.text_en ?? "?"}</strong>
						</button>
					);
				})}
			</div>
		</section>
	);
}

function RouteBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(value: ConstructedResponse): void;
}) {
	const occupations = game.occupations as Occupation[];
	const places = game.places as Place[];
	const [selected, setSelected] = useState<string | null>(null);
	const [links, setLinks] = useState<CityLink[]>([]);
	const [trace, setTrace] = useState<string[]>([]);
	const emit = (next: CityLink[], nextTrace: string[]) =>
		onResponse(
			occupationPlaceResponse(
				String(game.command_token),
				next,
				occupations.map((row) => row.occupation_token),
				nextTrace,
			),
		);
	const connect = (target: string) => {
		if (!selected) return;
		const filtered = links.filter((link) => link.source !== selected);
		const next = [
			...filtered,
			{ sequence: filtered.length + 1, source: selected, target },
		];
		const nextTrace = [
			...trace,
			`${filtered.length === links.length ? "link" : "replace"}:${target}`,
		];
		setLinks(next);
		setTrace(nextTrace);
		setSelected(null);
		emit(next, nextTrace);
	};
	const clear = () => {
		const nextTrace = [...trace, "clear:all"];
		setLinks([]);
		setSelected(null);
		setTrace(nextTrace);
		emit([], nextTrace);
	};
	return (
		<section>
			<p className="city-instruction">
				Connect the pairs from this lesson. A hub may accept more than one
				route.
			</p>
			<div className="occupation-tray">
				{occupations.map((row) => (
					<button
						className="work-label"
						data-opaque-token={row.occupation_token}
						key={row.occupation_token}
						aria-pressed={selected === row.occupation_token}
						disabled={links.some(
							(link) => link.source === row.occupation_token,
						)}
						onClick={() => setSelected(row.occupation_token)}
					>
						{row.text_en}
					</button>
				))}
			</div>
			<div className="route-hubs">
				{places.map((hub) => {
					const count = links.filter(
						(link) => link.target === hub.place_token,
					).length;
					const slots = Array.from(
						{ length: hub.capacity },
						(_, slot) => slot + 1,
					);
					return (
						<button
							className="place-hub"
							data-opaque-token={hub.place_token}
							data-count={count}
							key={hub.place_token}
							onClick={() => connect(hub.place_token)}
						>
							<span className="place-mark" aria-hidden="true">
								{PLACE_MARKS[hub.renderer_variant] ?? "🏢"}
							</span>
							<strong>{hub.text_en}</strong>
							<span
								className="capacity-meter"
								role="img"
								aria-label={`${count} of ${hub.capacity} lesson links added`}
							>
								{slots.map((slot) => (
									<i
										data-filled={slot <= count}
										key={`${hub.place_token}-slot-${slot}`}
									/>
								))}
							</span>
						</button>
					);
				})}
			</div>
			<button
				className="clear-links"
				disabled={links.length === 0}
				onClick={clear}
			>
				Clear links
			</button>
		</section>
	);
}

function CitySupport({
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
	if (support.game_manifest.schema_version !== "workplace-link-city-support-v1")
		return null;
	const required = support.game_manifest.required_actions;
	return (
		<section className="caq-support">
			<div className="object-icon" aria-hidden="true">
				🔗🏙️
			</div>
			<h2>{support.title_si}</h2>
			<p>{support.body_si[Math.min(stage, support.body_si.length - 1)]}</p>
			<p className="city-instruction">
				Support step {Math.min(stage, required)} of {required}
			</p>
			<button
				className="caq-primary"
				onClick={stage < required ? onNext : onComplete}
			>
				{stage < required ? "Show next link clue" : "I’m ready to link alone"}
			</button>
		</section>
	);
}
