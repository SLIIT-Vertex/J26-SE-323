// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import { ContractError } from "../../../mobile-learning-flow/api/runtime";
import {
	adaptiveGameProgressStage,
	AdventureProgress,
} from "../../../mobile-learning-flow/AdventureProgress";
import {
	AdventureBackButton,
	GameSuccessScreen,
} from "../../../mobile-learning-flow/AdventureShared";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import {
	compassResponse,
	type CompassPosition,
	sceneResponse,
	type PlaceStatement,
} from "./directionLogic";
import {
	DIRECTION_GAMES,
	DIRECTION_LABELS,
	DIRECTION_SKILLS,
	type DirectionId,
	PLACE_ASSETS,
	PLACE_LABELS,
} from "./manifest";
import "./direction-adventure.css";

type Step =
	| "games"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function DirectionAdventureJourney({
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
		DIRECTION_SKILLS.findIndex((skill) => skill.id === skillId),
	);
	const active = DIRECTION_SKILLS[index];
	const activeGameIndex = Math.max(
		0,
		DIRECTION_GAMES.findIndex((game, gameIndex) => {
			const next = DIRECTION_GAMES[gameIndex + 1];
			return (
				index >= game.firstSkillIndex && (!next || index < next.firstSkillIndex)
			);
		}),
	);
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
					area_id: "G5-AREA-MAT-14",
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
	const record = (value: ConstructedResponse | null) => {
		setResponse(value);
		setMoves((count) => count + 1);
	};
	const confirm = async () => {
		if (!episodeId || !manifest || !response || lock.current) return;
		lock.current = true;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			response_time_ms: reducedMotion ? null : Date.now() - startedAt,
			interaction_summary: {
				move_count: moves,
				correction_count: 0,
				first_action_ms: 0,
				active_time_ms: reducedMotion ? 0 : Date.now() - startedAt,
				attempt_count: 1,
				working_cell_count:
					response.kind === "place_direction_scene"
						? response.selections.length
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
		setFeedback(next.server_score.feedback_column ?? null);
		if (next.status === "support_active" && next.support) {
			setSupport(next.support);
			setSupportStage(0);
			setStep("support");
		} else setStep("feedback");
	};
	const finishSupport = async () => {
		if (!episodeId || !support) return;
		const game = support.game_manifest;
		if (game.schema_version === "half-set-manifest-v1") return;
		if (
			game.schema_version !== "support-round-v1" &&
			supportStage < game.required_actions
		)
			return;
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
		if (done) advanceSupport(done);
	};
	const advanceSupport = (next: ChildEpisodeResponse) => {
		if (next.support_round?.withdrawal_allowed) {
			setPending({
				episode: next.episode_id,
				support: next.support_round.support_revision_id,
				manifest: next.support_round.manifest_revision_id,
			});
			setSupport(null);
			setResponse(null);
			setStep("withdrawing");
			return;
		}
		if (next.support) {
			setSupport(next.support);
			setSupportStage(0);
			reset();
		}
	};
	const answerSupport = async () => {
		const submit = api.answerSupported,
			game = support?.game_manifest,
			activity =
				game?.schema_version === "support-round-v1" ? game.activity : null;
		if (
			!submit ||
			!episodeId ||
			!response ||
			!game ||
			game.schema_version !== "support-round-v1" ||
			!activity
		)
			return;
		const next = await run(() =>
			submit(
				episodeId,
				{
					constructed_response: {
						...response,
						presentation_id: activity.presentation_id,
						item_revision_id: activity.revision_id,
						interaction_version: "constructed-response-v1",
					},
					response_time_ms: Date.now() - startedAt,
					interaction_summary: { move_count: moves },
				},
				crypto.randomUUID(),
			),
		);
		if (next) advanceSupport(next);
	};
	const advance = () => {
		if (!skillId || !correct)
			return skillId ? void openSkill(skillId) : undefined;
		const nextDone = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(nextDone);
		const nextSkill = DIRECTION_SKILLS[index + 1];
		if (nextSkill && nextSkill.chapter === active?.chapter)
			void openSkill(nextSkill.id);
		else setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) advance();
	}, [step, correct]);

	return (
		<main
			className="direction-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="direction-header">
				<AdventureBackButton
					onClick={step === "games" ? onBack : () => setStep("games")}
				/>
				<div>
					<h1>දිශා</h1>
				</div>
			</header>
			{step === "games" ? (
				<section className="direction-game-list" aria-label="දිශා ක්‍රීඩා">
					{DIRECTION_GAMES.map((game) => (
						<button
							className="direction-game-card"
							key={game.id}
							onClick={() =>
								void openSkill(DIRECTION_SKILLS[game.firstSkillIndex].id)
							}
						>
							<span className="direction-game-icon" aria-hidden="true">
								{game.firstSkillIndex === 0 ? "✣" : "🏡"}
							</span>
							<span>
								<strong>{game.title}</strong>
								<small>
									{game.challengeLabel} · {game.difficulty}
								</small>
							</span>
						</button>
					))}
				</section>
			) : (
				<section className="direction-play game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={3}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="direction-position">
						ක්‍රියාකාරකම {index + 1}/3 · {active?.name}
					</p>
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<DirectionActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="direction-primary"
								disabled={busy || !response}
								onClick={confirm}
							>
								තහවුරු කරන්න
							</button>
						</>
					)}
					{step === "support" &&
						support &&
						(support.game_manifest.schema_version === "support-round-v1" ? (
							<SupportRoundFrame
								support={support}
								busy={busy}
								onViewComplete={() => void finishSupport()}
								renderActivity={(activity) => (
									<DirectionActivity
										key={activity.revision_id}
										game={activity.game}
										onResponse={record}
									/>
								)}
							>
								{support.game_manifest.stage_kind !== "view" && (
									<button
										className="direction-primary"
										disabled={busy || !response}
										onClick={() => void answerSupport()}
									>
										තහවුරු කරන්න
									</button>
								)}
							</SupportRoundFrame>
						) : (
							<DirectionSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						))}
					{step === "withdrawing" && (
						<p role="status">පිළිතුරු සහිත සහාය ඉවත් කර අලුත් මාලිමාව සූදානම් කරමින්…</p>
					)}
					{step === "feedback" && !correct && (
						<section className="direction-feedback">
							<h2>{`${feedbackLabel(feedback)} නැවත බලමු.`}</h2>
							<button className="direction-primary" onClick={advance}>
								නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={activeGameIndex + 1}
							gameCount={DIRECTION_GAMES.length}
							onContinue={() => {
								const nextGame = DIRECTION_GAMES[activeGameIndex + 1];
								if (!nextGame) setStep("games");
								else
									void openSkill(DIRECTION_SKILLS[nextGame.firstSkillIndex].id);
							}}
						/>
					)}
				</section>
			)}
		</main>
	);
}

function feedbackLabel(value: string | null) {
	if (!value) return "දිශාව";
	if (value.startsWith("statement")) return "ළමයා සිටින තැනින් ස්ථානයට යන දිශාව";
	return "මාලිමාවේ තෝරාගත් තැන";
}

const MAIN_POSITIONS: CompassPosition[] = ["top", "right", "bottom", "left"];
const SECONDARY_POSITIONS: CompassPosition[] = [
	"top_right",
	"bottom_right",
	"bottom_left",
	"top_left",
];

export function DirectionActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const kind = String(game.response_kind);
	if (kind === "place_direction_scene")
		return <PlaceDirectionActivity game={game} onResponse={onResponse} />;
	return (
		<CompassActivity
			kind={kind as "main_direction_compass" | "secondary_direction_compass"}
			positions={
				(game.active_positions as CompassPosition[]) ??
				(kind === "main_direction_compass"
					? MAIN_POSITIONS
					: SECONDARY_POSITIONS)
			}
			options={(game.direction_options as DirectionId[]) ?? []}
			anchors={(game.anchor_directions as DirectionId[]) ?? []}
			onResponse={onResponse}
		/>
	);
}

function CompassActivity({
	kind,
	positions,
	options,
	anchors,
	onResponse,
}: {
	kind: "main_direction_compass" | "secondary_direction_compass";
	positions: CompassPosition[];
	options: DirectionId[];
	anchors: DirectionId[];
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [values, setValues] = useState<
		Partial<Record<CompassPosition, DirectionId>>
	>({});
	const [order, setOrder] = useState<string[]>([]);
	const choose = (position: CompassPosition, direction: DirectionId | "") => {
		const next = { ...values };
		if (direction) next[position] = direction;
		else delete next[position];
		const nextOrder =
			direction && !order.includes(position) ? [...order, position] : order;
		setValues(next);
		setOrder(nextOrder);
		onResponse(
			compassResponse(
				kind,
				positions,
				next,
				nextOrder,
				anchors,
			) as ConstructedResponse | null,
		);
	};
	return (
		<DirectionCompass anchors={anchors}>
			{positions.map((position) => (
				<CompassDirectionSelect
					key={position}
					position={position}
					options={options}
					value={values[position] ?? ""}
					onChange={(value) => choose(position, value)}
				/>
			))}
		</DirectionCompass>
	);
}

export function DirectionCompass({
	anchors = [],
	focus,
	children,
}: {
	anchors?: DirectionId[];
	focus?: string;
	children?: React.ReactNode;
}) {
	return (
		<div className="direction-compass" data-focus={focus}>
			<svg
				viewBox="0 0 300 300"
				role="img"
				aria-label="මධ්‍යයෙන් දිශා අටට යන ඊතල අටක්"
			>
				<defs>
					<marker
						id="direction-arrow"
						viewBox="0 0 10 10"
						refX="8"
						refY="5"
						markerWidth="7"
						markerHeight="7"
						orient="auto-start-reverse"
					>
						<path d="M 0 0 L 10 5 L 0 10 z" />
					</marker>
				</defs>
				{(
					[
						[150, 150, 150, 30],
						[150, 150, 270, 150],
						[150, 150, 150, 270],
						[150, 150, 30, 150],
						[150, 150, 235, 65],
						[150, 150, 235, 235],
						[150, 150, 65, 235],
						[150, 150, 65, 65],
					] as number[][]
				).map((line) => (
					<line
						key={line.join("-")}
						x1={line[0]}
						y1={line[1]}
						x2={line[2]}
						y2={line[3]}
						markerEnd="url(#direction-arrow)"
					/>
				))}
				<circle cx="150" cy="150" r="8" />
			</svg>
			{anchors.map((direction) => (
				<span className={`compass-anchor anchor-${direction}`} key={direction}>
					{DIRECTION_LABELS[direction]}
				</span>
			))}
			{children}
		</div>
	);
}

export function CompassDirectionSelect({
	position,
	options,
	value,
	onChange,
	disabled = false,
}: {
	position: CompassPosition;
	options: DirectionId[];
	value: DirectionId | "";
	onChange(value: DirectionId | ""): void;
	disabled?: boolean;
}) {
	return (
		<label className={`compass-select compass-${position}`}>
			<span className="sr-only">{positionLabel(position)} දිශාව තෝරන්න</span>
			<select
				style={{ minHeight: 48 }}
				aria-label={`${positionLabel(position)} දිශාව තෝරන්න`}
				value={value}
				disabled={disabled}
				onChange={(event) => onChange(event.target.value as DirectionId | "")}
			>
				<option value="">තෝරන්න</option>
				{options.map((direction) => (
					<option value={direction} key={direction}>
						{DIRECTION_LABELS[direction]}
					</option>
				))}
			</select>
		</label>
	);
}

function positionLabel(position: CompassPosition) {
	return (
		{
			top: "ඉහළ",
			top_right: "ඉහළ දකුණ",
			right: "දකුණත",
			bottom_right: "පහළ දකුණ",
			bottom: "පහළ",
			bottom_left: "පහළ වම",
			left: "වම",
			top_left: "ඉහළ වම",
		} as Record<CompassPosition, string>
	)[position];
}

type Placement = { place_id: string; direction: DirectionId; label_si: string };

function PlaceDirectionActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const statements = (game.statements as PlaceStatement[]) ?? [];
	const [values, setValues] = useState<Record<string, DirectionId | "">>({});
	const [order, setOrder] = useState<string[]>([]);
	const [revisions, setRevisions] = useState(0);
	const choose = (statementId: string, value: DirectionId | "") => {
		const next = { ...values, [statementId]: value };
		const nextOrder =
			value && !order.includes(statementId) ? [...order, statementId] : order;
		setValues(next);
		setOrder(nextOrder);
		if (values[statementId] && values[statementId] !== value)
			setRevisions((count) => count + 1);
		onResponse(
			sceneResponse(
				String(game.scene_id),
				statements,
				next,
				nextOrder,
				revisions +
					(values[statementId] && values[statementId] !== value ? 1 : 0),
			) as ConstructedResponse | null,
		);
	};
	return (
		<div className="place-direction-activity">
			<ChildPlaceScene placements={(game.placements as Placement[]) ?? []} />
			<div className="direction-sentences">
				{statements.map((statement) => (
					<DirectionSentence
						key={statement.statement_id}
						statement={statement}
						value={values[statement.statement_id] ?? ""}
						options={(game.direction_options as DirectionId[]) ?? []}
						onChange={(value) => choose(statement.statement_id, value)}
					/>
				))}
			</div>
		</div>
	);
}

export function ChildPlaceScene({
	placements,
	focus,
}: {
	placements: Placement[];
	focus?: string;
}) {
	return (
		<figure
			className="child-place-scene"
			data-focus={focus}
			aria-label="ළමයා මැද සිටින අට දිශා ස්ථාන සිතියම"
		>
			<DirectionCompass />
			<AssetImage
				className="scene-child"
				src="/curriculum/game/G5-AREA-MAT-14/direction-child.png"
				fallback="🧒"
				alt="ළමයා"
			/>
			{placements.map((placement) => {
				const asset = PLACE_ASSETS[placement.place_id];
				return (
					<div
						className={`scene-place place-${placement.direction}`}
						data-place={placement.place_id}
						key={placement.place_id}
					>
						<AssetImage
							src={asset?.src ?? ""}
							fallback={asset?.fallback ?? "📍"}
							alt={placement.label_si || PLACE_LABELS[placement.place_id]}
						/>
						<figcaption>
							{placement.label_si || PLACE_LABELS[placement.place_id]}
						</figcaption>
					</div>
				);
			})}
		</figure>
	);
}

function AssetImage({
	src,
	fallback,
	alt,
	className,
}: {
	src: string;
	fallback: string;
	alt: string;
	className?: string;
}) {
	const [failed, setFailed] = useState(false);
	return failed || !src ? (
		<span
			className={`${className ?? ""} asset-fallback`}
			role="img"
			aria-label={alt}
		>
			{fallback}
		</span>
	) : (
		<img
			className={className}
			src={src}
			alt={alt}
			onError={() => setFailed(true)}
		/>
	);
}

export function DirectionSentence({
	statement,
	value,
	options,
	onChange,
	disabled = false,
}: {
	statement: PlaceStatement;
	value: DirectionId | "";
	options: DirectionId[];
	onChange(value: DirectionId | ""): void;
	disabled?: boolean;
}) {
	const [before, after = ""] = statement.template_si.split("___");
	return (
		<label className="direction-sentence">
			<span>{before}</span>
			<select
				style={{ minHeight: 48 }}
				aria-label={`${PLACE_LABELS[statement.place_id] ?? statement.place_id} සඳහා දිශාව තෝරන්න`}
				value={value}
				disabled={disabled}
				onChange={(event) => onChange(event.target.value as DirectionId | "")}
			>
				<option value="">තෝරන්න</option>
				{options.map((direction) => (
					<option value={direction} key={direction}>
						{DIRECTION_LABELS[direction]}
					</option>
				))}
			</select>
			<span>{after}</span>
		</label>
	);
}

function DirectionSupport({
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
	if (support.game_manifest.schema_version !== "direction-adventure-support-v1")
		return null;
	const manifest = support.game_manifest;
	const visualOnly = manifest.scaffold_type === "visual_guidance";
	return (
		<section className="direction-support">
			<p className="support-type">{support.title_si}</p>
			<h2>{manifest.worked_example.prompt_si}</h2>
			<DirectionWorkedDemo
				example={manifest.worked_example}
				stage={visualOnly ? 0 : stage}
				visualOnly={visualOnly}
				focus={manifest.focus_column}
			/>
			<ol>
				{manifest.worked_example.steps_si.map((line, index) => (
					<li className={index < stage ? "done" : ""} key={line}>
						{line}
					</li>
				))}
			</ol>
			{stage < manifest.required_actions ? (
				<button className="direction-primary" onClick={onNext}>
					{visualOnly ? "ඉඟිය බැලුවා" : "ඊළඟ පියවර"}
				</button>
			) : (
				<button className="direction-primary" onClick={onComplete}>
					සහාය ඉවත් කර නැවත උත්සාහ කරන්න
				</button>
			)}
		</section>
	);
}

type WorkedExample = {
	prompt_si: string;
	game: Record<string, unknown>;
	correct_response: Record<string, unknown> | null;
	steps_si: string[];
};

export function DirectionWorkedDemo({
	example,
	stage,
	visualOnly = false,
	focus,
}: {
	example: WorkedExample;
	stage: number;
	visualOnly?: boolean;
	focus?: string;
}) {
	const game = example.game;
	const response = example.correct_response;
	if (String(game.response_kind) === "place_direction_scene") {
		const answers = new Map(
			((response?.selections as Array<Record<string, string>>) ?? []).map(
				(row) => [row.statement_id, row.selected_direction as DirectionId],
			),
		);
		return (
			<div className="worked-direction-demo">
				<ChildPlaceScene
					placements={(game.placements as Placement[]) ?? []}
					focus={focus}
				/>
				{!visualOnly && (
					<div className="direction-sentences">
						{((game.statements as PlaceStatement[]) ?? [])
							.slice(0, Math.max(1, stage))
							.map((statement) => (
								<DirectionSentence
									key={statement.statement_id}
									statement={statement}
									value={answers.get(statement.statement_id) ?? ""}
									options={(game.direction_options as DirectionId[]) ?? []}
									onChange={() => {}}
									disabled
								/>
							))}
					</div>
				)}
			</div>
		);
	}
	const values = new Map(
		((response?.selections as Array<Record<string, string>>) ?? []).map(
			(row) => [row.position, row.direction as DirectionId],
		),
	);
	const positions = (game.active_positions as CompassPosition[]) ?? [];
	return (
		<DirectionCompass
			anchors={(game.anchor_directions as DirectionId[]) ?? []}
			focus={focus}
		>
			{!visualOnly &&
				positions.map((position, index) => (
					<CompassDirectionSelect
						key={position}
						position={position}
						options={(game.direction_options as DirectionId[]) ?? []}
						value={
							index < Math.max(1, stage) ? (values.get(position) ?? "") : ""
						}
						onChange={() => {}}
						disabled
					/>
				))}
		</DirectionCompass>
	);
}
