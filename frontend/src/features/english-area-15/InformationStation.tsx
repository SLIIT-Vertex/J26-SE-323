// biome-ignore-all lint/a11y/useButtonType: application controls, no forms.
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
import { ContractError } from "../mobile-learning-flow/api/runtime";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import { SupportRoundPlay } from "../mobile-learning-flow/SupportRoundFrame";
import {
	isSupportRound,
	useSupportRound,
} from "../mobile-learning-flow/useSupportRound";
import "../mobile-learning-flow/english-game-shared.css";
import "./information-station.css";
import {
	bilingualResponse,
	type Link,
	objectResponse,
} from "./informationLogic";

const SKILLS = [
	{ id: "G5-ENG-INFO-BILINGUAL-01", name: "Word Signal Bridge", icon: "🔤" },
	{ id: "G5-ENG-INFO-VISUAL-02", name: "Information Object Dock", icon: "📡" },
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
export function InformationStation({
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
		),
		reset = useCallback(() => {
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
					area_id: "G5-AREA-ENG-15",
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
			support.game_manifest.schema_version !==
				"information-station-support-v1" ||
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
		if (index < 1) void open(SKILLS[1].id);
		else setStep(d.length === 2 ? "result" : "games");
	};
	const game =
		manifest?.game?.schema_version === "information-station-item-v1"
			? (manifest.game as Game)
			: null;
	return (
		<main className="classroom-action-quest info-station">
			<header className="caq-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>Man &amp; Information</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="caq-game-list">
					<div className="is-console" aria-hidden="true">
						<i />
						<b />📡
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
								<small>Connect reviewed lesson signals.</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="caq-play game-play-surface">
					{step !== "result" && (
						<AdventureProgress
							stage={adaptiveGameProgressStage(
								step,
								manifest?.measurement_role,
							)}
							activityCount={2}
							currentActivity={index + 1}
							completedActivities={done.length}
						/>
					)}
					{step === "question" && game && (
						<>
							<div className="caq-command">
								<strong>{manifest?.prompt_si}</strong>
							</div>
							<StationBoard
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
								Check my signals
							</button>
						</>
					)}
					{step === "support" && isSupportRound(support) && (
						<SupportRoundPlay
							support={support}
							busy={busy}
							ready={response !== null && !incomplete(response)}
							checkLabel="Check my signals"
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
								<StationBoard
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
							"information-station-support-v1" && (
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
										? "Next signal step"
										: "I’m ready to connect alone"}
								</button>
							</section>
						)}
					{step === "withdrawing" && (
						<p className="caq-status">
							All examples, clues, and selections are clearing.
						</p>
					)}
					{step === "feedback" && (
						<section className="caq-feedback">
							<h2>
								{correct
									? "Signal station complete!"
									: "Compare the lesson words and reconnect."}
							</h2>
							<button className="caq-primary" onClick={advance}>
								{correct ? "Continue" : "Try fresh signals"}
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
function incomplete(r: ConstructedResponse) {
	return r.kind === "information_bilingual_links"
		? r.unlinked_english_tokens.length > 0
		: r.kind === "information_object_mapping"
			? r.unplaced_word_tokens.length > 0
			: true;
}
function StationBoard({
	game,
	onResponse,
}: {
	game: Game;
	onResponse(r: ConstructedResponse): void;
}) {
	const bilingual = game.response_kind === "information_bilingual_links",
		sources = (bilingual ? game.english_words : game.words) as Row[],
		targets = (bilingual ? game.sinhala_words : game.objects) as Row[],
		sk = bilingual ? "english_token" : "word_token",
		tk = bilingual ? "sinhala_token" : "object_token",
		[selected, setSelected] = useState<string | null>(null),
		[links, setLinks] = useState<Link[]>([]),
		[trace, setTrace] = useState<string[]>([]);
	const place = (target: string) => {
		if (!selected) return;
		const f = links.filter((x) => x.source !== selected && x.target !== target),
			n = [...f, { sequence: f.length + 1, source: selected, target }],
			t = [...trace, `place:${target}`];
		setLinks(n);
		setTrace(t);
		setSelected(null);
		onResponse(
			bilingual
				? bilingualResponse(
						String(game.command_token),
						n,
						sources.map((x) => String(x[sk])),
						t,
					)
				: objectResponse(
						String(game.command_token),
						n,
						sources.map((x) => String(x[sk])),
						t,
					),
		);
	};
	return (
		<section className="is-board">
			<div className="is-tray">
				{sources.map((x) => (
					<button
						data-opaque-token={String(x[sk])}
						key={String(x[sk])}
						disabled={links.some((y) => y.source === x[sk])}
						aria-pressed={selected === x[sk]}
						onClick={() => setSelected(String(x[sk]))}
					>
						{String(x.text_en)}
					</button>
				))}
			</div>
			<div className="is-targets">
				{targets.map((x, i) => (
					<button
						data-opaque-token={String(x[tk])}
						key={String(x[tk])}
						onClick={() => place(String(x[tk]))}
					>
						{bilingual ? (
							<>
								<strong>{String(x.text_si)}</strong>
								<small>
									{links.some((y) => y.target === x[tk])
										? "✓ linked"
										: "tap to link"}
								</small>
							</>
						) : (
							<ObjectGlyph variant={Number(x.renderer_variant)} index={i} />
						)}
					</button>
				))}
			</div>
		</section>
	);
}
function ObjectGlyph({ variant, index }: { variant: number; index: number }) {
	return (
		<span
			className="is-object"
			data-v={variant}
			role="img"
			aria-label={`Information object card ${index + 1}`}
		>
			<i />
			<i />
			<b />
		</span>
	);
}
