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
import "./blueprint-quest.css";
import {
	groupResponse,
	type Link,
	sequenceResponse,
	vocabularyResponse,
} from "./blueprintLogic";
const SKILLS = [
	{ id: "G5-ENG-PLACE-VOCAB-01", name: "Place Card Explorer", icon: "🏫" },
	{ id: "G5-ENG-PLACE-GROUP-02", name: "Blueprint Zone Sort", icon: "📐" },
	{ id: "G5-ENG-PLACE-NAME-03", name: "Room Name Workshop", icon: "🧩" },
] as const;
type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";
type Game = Record<string, unknown>;
type Row = Record<string, unknown>;
export function SchoolHomeBlueprintQuest({
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
	onFailure(e: unknown): void;
}) {
	const [step, setStep] = useState<Step>("games"),
		[skill, setSkill] = useState<string | null>(null),
		[episode, setEpisode] = useState<string | null>(null),
		[manifest, setManifest] = useState<PresentationManifest | null>(null),
		[support, setSupport] = useState<SupportView | null>(null),
		[response, setResponse] = useState<ConstructedResponse | null>(null),
		[correct, setCorrect] = useState(false),
		[busy, setBusy] = useState(false),
		[stage, setStage] = useState(0),
		[done, setDone] = useState<string[]>([]),
		[start, setStart] = useState(Date.now()),
		[moves, setMoves] = useState(0),
		[pending, setPending] = useState<{
			e: string;
			s: string;
			m: string;
		} | null>(null);
	const lock = useRef(false),
		index = Math.max(
			0,
			SKILLS.findIndex((x) => x.id === skill),
		);
	const run = useCallback(
		async <T,>(f: () => Promise<T>) => {
			setBusy(true);
			try {
				return await f();
			} catch (e) {
				onFailure(e);
			} finally {
				setBusy(false);
			}
		},
		[onFailure],
	);
	const reset = useCallback(() => {
		setResponse(null);
		setMoves(0);
		setStart(Date.now());
	}, []);
	useEffect(() => {
		if (step !== "withdrawing" || !pending) return;
		let cancelled = false;
		void (async () => {
			const w = await run(() =>
				api.withdrawSupport(
					pending.e,
					{
						request_id: crypto.randomUUID(),
						support_revision_id: pending.s,
						manifest_revision_id: pending.m,
						all_support_removed: true,
						answer_revealing_state_cleared: true,
						input_handlers_cleared: true,
					},
					crypto.randomUUID(),
				),
			);
			if (!w || cancelled) return;
			const n = await run(() =>
				api.presentAfter(pending.e, crypto.randomUUID()),
			);
			if (!n || cancelled) return;
			setManifest(n.manifest);
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
		episodeId: episode,
		run,
		onSupport: (next) => {
			setSupport(next);
			reset();
		},
		onWithdraw: (withdrawal) => {
			setPending({
				e: withdrawal.episodeId,
				s: withdrawal.supportRevisionId,
				m: withdrawal.manifestRevisionId,
			});
			setSupport(null);
			setResponse(null);
			setStep("withdrawing");
		},
	});
	const open = async (id: string) => {
		if (lock.current) return;
		lock.current = true;
		const x = await run(() =>
			api.open(
				{
					learner_id: learnerId,
					session_id: crypto.randomUUID(),
					grade: 5,
					medium: "si",
					condition,
					environment: "development",
					allow_draft: true,
					area_id: "G5-AREA-ENG-14",
					atomic_skill_id: id,
				},
				crypto.randomUUID(),
			),
		);
		lock.current = false;
		if (!x) return;
		setSkill(id);
		setEpisode(x.episode_id);
		setManifest(x.manifest);
		setSupport(null);
		setCorrect(false);
		reset();
		setStep("question");
	};
	const submit = async () => {
		if (!episode || !manifest || !response || lock.current) return;
		lock.current = true;
		const elapsed = reducedMotion ? 0 : Date.now() - start,
			body = {
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
		const n = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episode, body, crypto.randomUUID())
				: api.answerBefore(episode, body, crypto.randomUUID()),
		);
		lock.current = false;
		if (!n) return;
		if (
			!n.server_score ||
			n.server_score.presentation_id !== manifest.presentation_id ||
			n.server_score.item_revision_id !== manifest.revision_id
		)
			return onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
		setCorrect(n.server_score.correct === true);
		if (n.status === "support_active" && n.support) {
			setSupport(n.support);
			setStage(0);
			setStep("support");
		} else setStep("feedback");
	};
	const finish = async () => {
		if (
			!episode ||
			!support ||
			support.game_manifest.schema_version !== "blueprint-quest-support-v1" ||
			stage < support.game_manifest.required_actions
		)
			return;
		const g = support.game_manifest,
			d = await run(() =>
				api.completeSupport(
					episode,
					{
						duration_ms: Date.now() - start,
						steps_viewed: Math.max(1, stage),
						manifest_revision_id: g.revision_id,
						interaction_summary: {
							completed: true,
							renderer_id: g.renderer_id,
							parallel_example_id: g.parallel_example_id,
							support_actions: stage,
						},
					},
					crypto.randomUUID(),
				),
			);
		if (!d) return;
		setPending({ e: episode, s: support.revision_id, m: g.revision_id });
		setSupport(null);
		setResponse(null);
		setStep("withdrawing");
	};
	const advance = () => {
		if (!skill || !correct) return skill ? void open(skill) : undefined;
		const d = done.includes(skill) ? done : [...done, skill];
		setDone(d);
		if (index < 2) void open(SKILLS[index + 1].id);
		else setStep(d.length === 3 ? "result" : "games");
	};
	const game =
		manifest?.game?.schema_version === "blueprint-quest-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main className="classroom-action-quest blueprint-quest">
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Changes we can do</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list">
					<div className="bp-hero" aria-hidden="true">
						📐 ✏️ 🏫 🏠
					</div>
					{SKILLS.map((x) => (
						<button
							className="caq-game-card"
							key={x.id}
							onClick={() => void open(x.id)}
						>
							<span>{x.icon}</span>
							<span>
								<strong>{x.name}</strong>
								<small>Build this lesson’s blueprint with words.</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
							activityCount={3}
							currentActivity={index + 1}
							completedActivities={done.length}
						/>
					)}
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<Board
								key={manifest?.revision_id}
								game={game}
								onResponse={(x) => {
									setResponse(x);
									setMoves((v) => v + 1);
								}}
							/>
							<button
								className="caq-primary"
								disabled={busy || !response || incomplete(response)}
								onClick={submit}
							>
								Check my blueprint
							</button>
						</>
					)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null && !incomplete(response)}
							checkLabel="Check my blueprint"
							checkClassName="caq-primary"
							onCheck={() => {
								if (response)
									void round.answer(
										support,
										response,
										Date.now() - start,
										moves,
									);
							}}
							onViewComplete={() =>
								void round.viewComplete(support, Date.now() - start)
							}
							renderActivity={(activity) => (
								<Board
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
							"blueprint-quest-support-v1" && (
							<section className="caq-support">
								<h2>{support.title_si}</h2>
								<p>
									{support.body_si[Math.min(stage, support.body_si.length - 1)]}
								</p>
								<button
									className="caq-primary"
									onClick={
										stage < support.game_manifest.required_actions
											? () => setStage((v) => v + 1)
											: finish
									}
								>
									{stage < support.game_manifest.required_actions
										? "Next blueprint step"
										: "I’m ready to build alone"}
								</button>
							</section>
						)}
					{step === "withdrawing" && (
						<p className="caq-status">
							All examples, selections, and clues are clearing.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Blueprint approved!"
									: "Review the lesson words and rebuild."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct ? "Continue" : "Try a fresh blueprint"}
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
function incomplete(r: ConstructedResponse) {
	return r.kind === "place_vocabulary_mapping"
		? r.unplaced_word_tokens.length > 0
		: r.kind === "lesson_place_group_sort"
			? r.unplaced_entry_tokens.length > 0
			: r.kind === "place_name_sequence"
				? r.unused_chunk_tokens.length > 0
				: true;
}
function Board({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(r: ConstructedResponse): void;
}) {
	return game.response_kind === "place_name_sequence" ? (
		<Sequence game={game} onResponse={onResponse} />
	) : (
		<MappingBoard game={game} onResponse={onResponse} />
	);
}
function MappingBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(r: ConstructedResponse): void;
}) {
	const vocab = game.response_kind === "place_vocabulary_mapping",
		sources = (vocab ? game.words : game.entries) as Row[],
		targets = (vocab ? game.scenes : game.headings) as Row[],
		sk = vocab ? "word_token" : "entry_token",
		tk = vocab ? "scene_token" : "heading_token";
	const [selected, setSelected] = useState<string | null>(null),
		[links, setLinks] = useState<Link[]>([]),
		[trace, setTrace] = useState<string[]>([]);
	const place = (target: string) => {
		if (!selected) return;
		const f = links.filter(
				(x) => x.source !== selected && (vocab ? x.target !== target : true),
			),
			n = [...f, { sequence: f.length + 1, source: selected, target }],
			t = [...trace, `place:${target}`];
		setLinks(n);
		setTrace(t);
		setSelected(null);
		onResponse(
			vocab
				? vocabularyResponse(
						String(game.command_token),
						n,
						sources.map((x) => String(x[sk])),
						t,
					)
				: groupResponse(
						String(game.command_token),
						n,
						sources.map((x) => String(x[sk])),
						t,
					),
		);
	};
	return (
		<section className="bp-board">
			<p>
				{vocab
					? "Tap a word, then its code-built card."
					: "Put each word under the heading where it appears in this lesson."}
			</p>
			<div className="bp-tray">
				{sources.map((x) => (
					<button
						data-opaque-token={String(x[sk])}
						disabled={links.some((y) => y.source === x[sk])}
						aria-pressed={selected === x[sk]}
						key={String(x[sk])}
						onClick={() => setSelected(String(x[sk]))}
					>
						{String(x.text_en)}
					</button>
				))}
			</div>
			<div className="bp-zones">
				{targets.map((x) => (
					<button
						data-opaque-token={String(x[tk])}
						key={String(x[tk])}
						onClick={() => place(String(x[tk]))}
					>
						{vocab ? (
							<Glyph variant={Number(x.renderer_variant)} />
						) : (
							<>
								<strong>{String(x.text_en)}</strong>
								<small>
									{links.filter((y) => y.target === x[tk]).length}/
									{String(x.capacity)}
								</small>
							</>
						)}
					</button>
				))}
			</div>
		</section>
	);
}
function Sequence({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(r: ConstructedResponse): void;
}) {
	const chunks = game.chunks as Row[],
		all = chunks.map((x) => String(x.chunk_token)),
		slots = ["first", "second", "third", "fourth"].slice(
			0,
			Number(game.slot_count),
		),
		[ordered, setOrdered] = useState<string[]>([]),
		[trace, setTrace] = useState<string[]>([]);
	const add = (t: string) => {
		if (ordered.includes(t)) return;
		const n = [...ordered, t],
			tr = [...trace, `slot:${n.length}`];
		setOrdered(n);
		setTrace(tr);
		onResponse(
			sequenceResponse(
				String(game.command_token),
				String(game.place_token),
				n,
				all,
				tr,
			),
		);
	};
	return (
		<section className="bp-board">
			<Glyph variant={Number(game.renderer_variant)} />
			<div className="bp-slots">
				{slots.map((slot, i) => (
					<span key={slot}>
						{(chunks.find((x) => x.chunk_token === ordered[i])
							?.text_en as string) ?? "…"}
					</span>
				))}
			</div>
			<div className="bp-tray">
				{chunks.map((x) => (
					<button
						disabled={ordered.includes(String(x.chunk_token))}
						key={String(x.chunk_token)}
						onClick={() => add(String(x.chunk_token))}
					>
						{String(x.text_en)}
					</button>
				))}
			</div>
		</section>
	);
}
function Glyph({ variant }: { variant: number }) {
	return (
		<span className="bp-glyph" data-v={variant} aria-hidden="true">
			<i />
			<i />
			<b />
		</span>
	);
}
