// biome-ignore-all lint/a11y/useButtonType: game controls do not submit forms.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
	ChildEpisodeResponse,
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	ShapeAdventureWorkedExample,
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
	netMatchResponse,
	orientationResponse,
	shapeTableResponse,
	type Orientation,
} from "./shapeLogic";
import { SHAPE_GAMES, SHAPE_SKILLS, SOLID_LABELS } from "./manifest";
import "./shape-adventure.css";

type Step =
	| "chapters"
	| "question"
	| "support"
	| "withdrawing"
	| "feedback"
	| "result";

export function ShapeAdventureJourney({
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
	const [step, setStep] = useState<Step>("chapters"),
		[skillId, setSkillId] = useState<string | null>(null),
		[episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null),
		[support, setSupport] = useState<SupportView | null>(null),
		[response, setResponse] = useState<ConstructedResponse | null>(null);
	const [correct, setCorrect] = useState(false),
		[feedback, setFeedback] = useState<string | null>(null),
		[busy, setBusy] = useState(false),
		[supportStage, setSupportStage] = useState(0);
	const [completed, setCompleted] = useState<string[]>([]),
		[startedAt, setStartedAt] = useState(Date.now()),
		[moves, setMoves] = useState(0),
		[pending, setPending] = useState<{
			episode: string;
			support: string;
			manifest: string;
		} | null>(null);
	const lock = useRef(false),
		index = Math.max(
			0,
			SHAPE_SKILLS.findIndex((skill) => skill.id === skillId),
		),
		active = SHAPE_SKILLS[index];
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
					area_id: "G5-AREA-MAT-13",
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
					response.kind === "shape_property_table"
						? response.filled_cells.length
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
		if (!skillId) return;
		if (!correct) return void openSkill(skillId);
		const nextDone = completed.includes(skillId)
			? completed
			: [...completed, skillId];
		setCompleted(nextDone);
		setStep("result");
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: transition exactly once when feedback becomes correct
	useEffect(() => {
		if (step === "feedback" && correct) advance();
	}, [step, correct]);

	return (
		<main
			className="shape-adventure"
			data-reduced-motion={reducedMotion || undefined}
		>
			<header className="shape-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<div>
					<h1>හැඩතල හා ඝන වස්තු</h1>
				</div>
			</header>
			{step === "chapters" ? (
				<section className="shape-game-list" aria-label="හැඩතල හා ඝන වස්තු ක්‍රීඩා">
					{SHAPE_GAMES.map((game, gameIndex) => (
						<button
							className="shape-game-card"
							key={game.id}
							onClick={() => void openSkill(SHAPE_SKILLS[gameIndex].id)}
						>
							<ShapeIcon
								solidId={
									gameIndex === 0
										? "cube"
										: gameIndex === 1
											? "orientation"
											: "triangular_pyramid"
								}
								variant={gameIndex === 2 ? "net" : "solid"}
							/>
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
				<section className="shape-play game-play-surface">
					<AdventureProgress
						stage={adaptiveGameProgressStage(step, manifest?.measurement_role)}
						activityCount={3}
						currentActivity={index + 1}
						completedActivities={completed.length}
					/>
					<p className="shape-position">
						ක්‍රියාකාරකම {index + 1}/3 · {active?.name}
					</p>
					{step === "question" && manifest?.game && (
						<>
							<h2>{manifest.prompt_si}</h2>
							<ShapeActivity
								key={manifest.revision_id}
								game={manifest.game as Record<string, unknown>}
								onResponse={record}
							/>
							<button
								className="shape-primary"
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
									<ShapeActivity
										key={activity.revision_id}
										game={activity.game}
										onResponse={record}
									/>
								)}
							>
								{support.game_manifest.stage_kind !== "view" && (
									<button
										className="shape-primary"
										disabled={busy || !response}
										onClick={() => void answerSupport()}
									>
										තහවුරු කරන්න
									</button>
								)}
							</SupportRoundFrame>
						) : (
							<ShapeSupport
								support={support}
								stage={supportStage}
								onNext={() => setSupportStage((value) => value + 1)}
								onComplete={finishSupport}
							/>
						))}
					{step === "withdrawing" && (
						<p role="status">පිළිතුරු සහිත සහාය ඉවත් කර අලුත් ප්‍රශ්නය සූදානම් කරමින්…</p>
					)}
					{step === "feedback" && !correct && (
						<section className="shape-feedback">
							<h2>{`${feedbackLabel(feedback)} නැවත බලමු.`}</h2>
							<button className="shape-primary" onClick={advance}>
								නැවත උත්සාහ කරන්න
							</button>
						</section>
					)}
					{step === "result" && (
						<GameSuccessScreen
							gameNumber={index + 1}
							gameCount={SHAPE_GAMES.length}
							onContinue={() =>
								index < SHAPE_SKILLS.length - 1
									? void openSkill(SHAPE_SKILLS[index + 1].id)
									: setStep("chapters")
							}
						/>
					)}
				</section>
			)}
		</main>
	);
}

function feedbackLabel(value: string | null) {
	if (!value) return "රූපය";
	if (value.includes("faces")) return "මුහුණත් තීරුව";
	if (value.includes("vertices")) return "ශීර්ෂ තීරුව";
	if (value.includes("edges")) return "දාර තීරුව";
	if (
		value.includes("line") ||
		value.includes("level") ||
		value.includes("edge")
	)
		return "තිරස්/සිරස් දිශාව";
	return "ගැළපීම";
}

export function ShapeActivity({
	game,
	onResponse,
}: {
	game: Record<string, unknown>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const kind = String(game.response_kind);
	if (kind === "shape_property_table")
		return (
			<ShapeTableActivity
				rowIds={array(game.row_ids)}
				onResponse={onResponse}
			/>
		);
	if (kind === "orientation_identification")
		return (
			<OrientationActivity
				exampleIds={array(game.example_ids)}
				onResponse={onResponse}
			/>
		);
	return (
		<NetMatchActivity
			solidIds={array(game.solid_ids)}
			netIds={array(game.net_ids)}
			onResponse={onResponse}
		/>
	);
}

type Field = "faces" | "vertices" | "edges";
const FIELD_LABELS: Record<Field, string> = {
	faces: "මුහුණත්",
	vertices: "ශීර්ෂ",
	edges: "දාර",
};

function ShapeTableActivity({
	rowIds,
	onResponse,
}: {
	rowIds: string[];
	onResponse(response: ConstructedResponse | null): void;
}) {
	const first = `${rowIds[0]}:faces`,
		[active, setActive] = useState(first),
		[values, setValues] = useState<Record<string, number | null>>({});
	const write = (digit: number | null, append = false) => {
		const current = values[active];
		const value =
			digit === null
				? null
				: append
					? Number(`${current ?? ""}${digit}`.slice(-2))
					: digit;
		const next = { ...values, [active]: value };
		setValues(next);
		onResponse(shapeTableResponse(rowIds, next));
	};
	return (
		<fieldset
			className="shape-table-wrap"
			onKeyDown={(event) => {
				if (/^[0-9]$/.test(event.key)) write(Number(event.key), true);
				if (event.key === "Backspace" || event.key === "Delete") write(null);
			}}
		>
			<legend className="sr-only">යතුරු පුවරුවෙන් පිරවිය හැකි හැඩතල වගුව</legend>
			<p className="shape-help">රූපයේ අංක බලන්න. කොටුවක් තෝරා අංකය තට්ටු කරන්න.</p>
			<table className="shape-table">
				<thead>
					<tr>
						<th>ඝන වස්තුව</th>
						<th>මුහුණත්</th>
						<th>ශීර්ෂ</th>
						<th>දාර</th>
					</tr>
				</thead>
				<tbody>
					{rowIds.map((solid) => (
						<tr key={solid}>
							<th>
								<ShapeIcon solidId={solid} variant="solid" numbered />
								<span>{SOLID_LABELS[solid]}</span>
							</th>
							{(["faces", "vertices", "edges"] as Field[]).map((field) => {
								const key = `${solid}:${field}`;
								return (
									<td key={field}>
										<button
											style={{ minWidth: 48, minHeight: 48 }}
											className={active === key ? "selected" : ""}
											aria-label={`${SOLID_LABELS[solid]} ${FIELD_LABELS[field]} ගණන`}
											aria-pressed={active === key}
											onClick={() => setActive(key)}
										>
											{values[key] ?? "?"}
										</button>
									</td>
								);
							})}
						</tr>
					))}
				</tbody>
			</table>
			<NumberPad onDigit={write} onClear={() => write(null)} />
			<p className="cylinder-note">
				<ShapeIcon solidId="cylinder" variant="solid" /> සිලින්ඩරයට පැතලි මුහුණත් 2ක්
				සමඟ වක්‍ර පෘෂ්ඨයක්ද ඇත.
			</p>
		</fieldset>
	);
}

function NumberPad({
	onDigit,
	onClear,
}: {
	onDigit(value: number): void;
	onClear(): void;
}) {
	return (
		<fieldset className="shape-keypad">
			<legend className="sr-only">අංක යතුරු පුවරුව</legend>
			{[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12].map((number) => (
				<button
					aria-label={`අංක ${number}`}
					key={number}
					onClick={() => onDigit(number)}
				>
					{number}
				</button>
			))}
			<button aria-label="තෝරාගත් කොටුව හිස් කරන්න" onClick={onClear}>
				⌫
			</button>
		</fieldset>
	);
}

function OrientationActivity({
	exampleIds,
	onResponse,
}: {
	exampleIds: string[];
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [values, setValues] = useState<Record<string, Orientation | "">>({});
	const choose = (id: string, value: Orientation | "") => {
		const next = { ...values, [id]: value };
		setValues(next);
		onResponse(orientationResponse(exampleIds, next));
	};
	return (
		<div className="orientation-list">
			{exampleIds.map((id) => (
				<article key={id} className="orientation-card">
					<OrientationPicture exampleId={id} />
					<label htmlFor={`orientation-${id}`}>{exampleLabel(id)}</label>
					<select
						id={`orientation-${id}`}
						aria-label={`${exampleLabel(id)} තිරස් හෝ සිරස් තෝරන්න`}
						value={values[id] ?? ""}
						onChange={(event) =>
							choose(id, event.target.value as Orientation | "")
						}
					>
						<option value="">තෝරන්න</option>
						<option value="horizontal">තිරස්</option>
						<option value="vertical">සිරස්</option>
					</select>
				</article>
			))}
		</div>
	);
}

function OrientationPicture({ exampleId }: { exampleId: string }) {
	const horizontal = exampleId === "spirit_level" || exampleId === "shelf";
	return (
		<svg
			className="orientation-picture"
			viewBox="0 0 180 100"
			role="img"
			aria-label={exampleLabel(exampleId)}
		>
			{horizontal ? (
				<>
					<line
						x1="18"
						y1="70"
						x2="162"
						y2="70"
						stroke="currentColor"
						strokeWidth="8"
						strokeLinecap="round"
					/>
					{exampleId === "spirit_level" ? (
						<>
							<rect
								x="30"
								y="38"
								width="120"
								height="24"
								rx="5"
								fill="#f6b73c"
								stroke="currentColor"
								strokeWidth="3"
							/>
							<rect
								x="78"
								y="42"
								width="24"
								height="16"
								rx="8"
								fill="#dff8ee"
								stroke="currentColor"
							/>
							<circle cx="90" cy="50" r="4" fill="#276f64" />
						</>
					) : (
						<>
							<rect
								x="25"
								y="45"
								width="130"
								height="18"
								rx="3"
								fill="#b77a46"
							/>
							<line
								x1="45"
								y1="63"
								x2="45"
								y2="90"
								stroke="currentColor"
								strokeWidth="6"
							/>
							<line
								x1="135"
								y1="63"
								x2="135"
								y2="90"
								stroke="currentColor"
								strokeWidth="6"
							/>
						</>
					)}
				</>
			) : exampleId === "plumb_line" ? (
				<>
					<line
						x1="90"
						y1="10"
						x2="90"
						y2="73"
						stroke="currentColor"
						strokeWidth="4"
					/>
					<path
						d="M90 66 L75 90 H105 Z"
						fill="#f6b73c"
						stroke="currentColor"
						strokeWidth="2"
					/>
				</>
			) : (
				<>
					<rect x="75" y="10" width="30" height="80" fill="#d9c2a2" />
					<line
						x1="75"
						y1="8"
						x2="75"
						y2="92"
						stroke="#6d3a2a"
						strokeWidth="5"
					/>
				</>
			)}
		</svg>
	);
}

function NetMatchActivity({
	solidIds,
	netIds,
	onResponse,
}: {
	solidIds: string[];
	netIds: string[];
	onResponse(response: ConstructedResponse | null): void;
}) {
	const [selected, setSelected] = useState<string | null>(null),
		[matches, setMatches] = useState<Record<string, string>>({}),
		[trace, setTrace] = useState<string[]>([]);
	const match = (net: string) => {
		if (!selected) return;
		const next = { ...matches, [selected]: net },
			nextTrace = [...trace, `match:${selected}:${net}`];
		setMatches(next);
		setTrace(nextTrace);
		onResponse(netMatchResponse(solidIds, next, nextTrace));
		setSelected(null);
	};
	return (
		<div className="net-match">
			<section>
				<h3>1. ඝන වස්තුව තෝරන්න</h3>
				<div className="shape-choice-grid">
					{solidIds.map((solid) => (
						<button
							className={
								selected === solid
									? "selected"
									: matches[solid]
										? "matched"
										: ""
							}
							aria-pressed={selected === solid}
							key={solid}
							onClick={() => setSelected(solid)}
						>
							<ShapeIcon solidId={solid} variant="solid" />
							<span>{SOLID_LABELS[solid]}</span>
						</button>
					))}
				</div>
			</section>
			<section>
				<h3>2. එයට ගැළපෙන පතරොම තෝරන්න</h3>
				<div className="shape-choice-grid nets">
					{netIds.map((net) => (
						<button key={net} onClick={() => match(net)} disabled={!selected}>
							<ShapeIcon solidId={net} variant="net" />
							<span>පතරොම {netIds.indexOf(net) + 1}</span>
						</button>
					))}
				</div>
			</section>
			<ul className="match-results" aria-live="polite">
				{solidIds
					.filter((id) => matches[id])
					.map((id) => (
						<li key={id}>
							✓ {SOLID_LABELS[id]} → පතරොම {netIds.indexOf(matches[id]) + 1}
						</li>
					))}
			</ul>
		</div>
	);
}

function ShapeSupport({
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
	if (support.game_manifest.schema_version !== "shape-adventure-support-v1")
		return null;
	const manifest = support.game_manifest,
		example = manifest.worked_example,
		visualOnly = manifest.scaffold_type === "visual_guidance";
	return (
		<section className="shape-support">
			<p className="support-type">{support.title_si}</p>
			<h2>{example.prompt_si}</h2>
			{visualOnly ? (
				<ShapeVisualCue
					game={example.game as Record<string, unknown>}
					focus={manifest.focus_column}
				/>
			) : (
				<ShapeWorkedDemo example={example} stage={stage} />
			)}
			<ol>
				{example.steps_si.map((text, index) => (
					<li className={index < stage ? "done" : ""} key={text}>
						{text}
					</li>
				))}
			</ol>
			<button
				className="shape-primary"
				onClick={stage < manifest.required_actions ? onNext : onComplete}
			>
				{stage < manifest.required_actions ? "ඊළඟ පියවර" : "දැන් මම කරමි"}
			</button>
		</section>
	);
}

function ShapeVisualCue({
	game,
	focus,
}: {
	game: Record<string, unknown>;
	focus?: string;
}) {
	const kind = String(game.response_kind);
	if (kind === "orientation_identification")
		return (
			<div className="support-picture-pair">
				<OrientationPicture
					exampleId={array(game.example_ids)[0] ?? "spirit_level"}
				/>
				<strong>ප්‍රධාන රේඛාව බලන්න</strong>
			</div>
		);
	if (kind === "solid_net_match")
		return (
			<div className="support-picture-pair">
				<ShapeIcon
					solidId={array(game.solid_ids)[0] ?? "cube"}
					variant="solid"
				/>
				<span>→</span>
				<ShapeIcon solidId={array(game.net_ids)[0] ?? "cube"} variant="net" />
			</div>
		);
	const solid = focus?.split(":")[0] ?? array(game.row_ids)[0] ?? "cube";
	return (
		<div className="support-picture-pair">
			<ShapeIcon solidId={solid} variant="solid" numbered />
			<strong>{feedbackLabel(focus ?? null)} බලන්න</strong>
		</div>
	);
}

export function ShapeWorkedDemo({
	example,
	stage,
}: {
	example: ShapeAdventureWorkedExample;
	stage: number;
}) {
	const response = example.correct_response;
	if (!response) return null;
	if (response.kind === "shape_property_table")
		return (
			<div className="worked-shape-table">
				{response.rows.map((row, index) => (
					<article key={row.solid_id}>
						<ShapeIcon solidId={row.solid_id} variant="solid" numbered />
						{stage >= 1 && (
							<span>
								මුහුණත් <b>{row.faces}</b>
							</span>
						)}
						{stage >= 2 && (
							<span>
								ශීර්ෂ <b>{row.vertices}</b>
							</span>
						)}
						{stage >= 3 && (
							<span>
								දාර <b>{row.edges}</b>
							</span>
						)}
						{stage >= 4 && index === response.rows.length - 1 && (
							<strong>වගුව සම්පූර්ණයි</strong>
						)}
					</article>
				))}
			</div>
		);
	if (response.kind === "orientation_identification")
		return (
			<div className="worked-orientations">
				{response.selections.map((row, index) => (
					<article key={row.example_id}>
						<OrientationPicture exampleId={row.example_id} />
						{stage > index / 2 && (
							<strong>
								{row.orientation === "horizontal" ? "තිරස්" : "සිරස්"}
							</strong>
						)}
					</article>
				))}
			</div>
		);
	if (response.kind === "solid_net_match")
		return (
			<div className="worked-net-matches">
				{response.matches.map((row, index) => (
					<article
						className={stage > index ? "revealed" : ""}
						key={row.solid_id}
					>
						<ShapeIcon solidId={row.solid_id} variant="solid" />
						<span>→</span>
						{stage > index ? (
							<ShapeIcon solidId={row.net_id} variant="net" />
						) : (
							<span className="hidden-net">?</span>
						)}
						<strong>{SOLID_LABELS[row.solid_id]}</strong>
					</article>
				))}
			</div>
		);
	return null;
}

export function ShapeIcon({
	solidId,
	variant,
	numbered = false,
}: {
	solidId: string;
	variant: "solid" | "net";
	numbered?: boolean;
}) {
	if (solidId === "orientation")
		return <OrientationPicture exampleId="spirit_level" />;
	const label = `${SOLID_LABELS[solidId] ?? solidId} ${variant === "net" ? "පතරොම" : "රූපය"}`;
	if (variant === "net")
		return (
			<svg
				className="shape-icon"
				viewBox="0 0 120 90"
				role="img"
				aria-label={label}
			>
				{solidId === "cube" ? (
					<g className="net-lines">
						<rect x="42" y="5" width="24" height="24" />
						<rect x="18" y="29" width="24" height="24" />
						<rect x="42" y="29" width="24" height="24" />
						<rect x="66" y="29" width="24" height="24" />
						<rect x="90" y="29" width="24" height="24" />
						<rect x="42" y="53" width="24" height="24" />
					</g>
				) : solidId === "cuboid" ? (
					<g className="net-lines">
						<rect x="40" y="4" width="36" height="20" />
						<rect x="16" y="24" width="24" height="30" />
						<rect x="40" y="24" width="36" height="30" />
						<rect x="76" y="24" width="24" height="30" />
						<rect x="40" y="54" width="36" height="20" />
						<rect x="40" y="74" width="36" height="12" />
					</g>
				) : solidId === "cylinder" ? (
					<g className="net-lines">
						<rect x="12" y="24" width="58" height="42" />
						<circle cx="90" cy="24" r="17" />
						<circle cx="90" cy="66" r="17" />
					</g>
				) : (
					<g className="net-lines">
						<path d="M60 8 L35 48 L85 48 Z" />
						<path d="M35 48 L10 84 L60 84 Z" />
						<path d="M85 48 L60 84 L110 84 Z" />
						<path d="M35 48 L60 84 L85 48 Z" />
					</g>
				)}
			</svg>
		);
	return (
		<svg
			className="shape-icon"
			viewBox="0 0 120 90"
			role="img"
			aria-label={label}
		>
			{solidId === "cylinder" ? (
				<>
					<ellipse cx="60" cy="18" rx="30" ry="12" fill="#fff1b8" />
					<path d="M30 18v48c0 8 60 8 60 0V18" fill="#f8d982" />
					<ellipse cx="60" cy="66" rx="30" ry="12" fill="#f1c95c" />
					<ellipse cx="60" cy="18" rx="30" ry="12" fill="#fff1b8" />
				</>
			) : solidId === "triangular_pyramid" ? (
				<>
					<path d="M60 8 L18 75 L100 75 Z" fill="#ffe39a" />
					<path d="M60 8 L60 58 L18 75" fill="none" />
					<path d="M60 58 L100 75" fill="none" />
				</>
			) : (
				<>
					<path
						d={
							solidId === "cube"
								? "M28 25 L72 25 L94 10 L50 10 Z"
								: "M20 30 L78 30 L100 16 L42 16 Z"
						}
						fill="#ffe39a"
					/>
					<path
						d={
							solidId === "cube"
								? "M72 25 L94 10 L94 58 L72 74 Z"
								: "M78 30 L100 16 L100 59 L78 74 Z"
						}
						fill="#f2bf5f"
					/>
					<rect
						x={solidId === "cube" ? 28 : 20}
						y={solidId === "cube" ? 25 : 30}
						width={solidId === "cube" ? 44 : 58}
						height={solidId === "cube" ? 49 : 44}
						fill="#fff3c4"
					/>
				</>
			)}
			{numbered && (
				<g className="shape-numbers">
					<text x="48" y="52">
						1
					</text>
					<text x="79" y="42">
						2
					</text>
					<text x="58" y="20">
						3
					</text>
				</g>
			)}
		</svg>
	);
}

function array(value: unknown): string[] {
	return Array.isArray(value) ? value.map(String) : [];
}
function exampleLabel(id: string) {
	return (
		(
			{
				spirit_level: "ස්පිරිතු ලෙවලය",
				shelf: "මේසයේ මතුපිට",
				plumb_line: "ලඹය",
				wall_edge: "බිත්තියේ සිරස් දාරය",
			} as Record<string, string>
		)[id] ?? id
	);
}
