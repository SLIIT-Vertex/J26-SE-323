import type { ReactNode } from "react";
import type {
	AccuracyMetric,
	AccuracyReport,
	EpisodeSummary,
	LearnerProfile,
	ModelSetting,
	Overview,
	Trace,
} from "./api";
import {
	HELP_STYLE,
	HelpMark,
	KpiTile,
	PlayGrid,
	pct,
	WeeklyBars,
} from "./charts";
import { answerLabel, GameRow, PlayStatus } from "./game-row";

function Card({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="rd-card">
			<h3>{title}</h3>
			{children}
		</section>
	);
}

function Mark({ value }: { value: boolean | null | undefined }) {
	return (
		<span
			className={
				value ? "rd-mark is-yes" : value === false ? "rd-mark is-no" : "rd-mark"
			}
		>
			{value ? "✓" : value === false ? "✗" : "—"}
		</span>
	);
}

export function EmptyStep({ text }: { text: string }) {
	return <p className="rd-empty">{text}</p>;
}

export function OverviewPanel({
	overview,
	onOpenEpisode,
}: {
	overview: Overview;
	onOpenEpisode(id: string): void;
}) {
	const board = overview.board ?? [];
	const maths = board.filter((cell) => cell.area_id.startsWith("G5-AREA-MAT-"));
	const english = board.filter((cell) =>
		cell.area_id.startsWith("G5-AREA-ENG-"),
	);
	const tried = (rows: typeof board) =>
		rows.filter((cell) => cell.played > 0).length;
	const fair = overview.independent_after_help_total ?? 0;
	const alone = overview.independent_after_help ?? 0;
	const recent = overview.recent.slice(0, 8);
	return (
		<div className="rd-stack">
			<ul className="rd-kpis">
				<KpiTile
					label="Games played"
					value={String(overview.counts.completed ?? 0)}
				/>
				<KpiTile
					label="Help sessions"
					value={String(overview.counts.helped_completed ?? 0)}
				/>
				<KpiTile
					label="Could do it alone after help"
					value={fair ? pct(alone / fair) : "—"}
					detail={fair ? `${alone} of ${fair}` : undefined}
				/>
				<KpiTile
					label="Games tried"
					value={`${tried(maths)}/${maths.length || 16}`}
					detail={`English ${tried(english)}/${english.length || 18}`}
				/>
			</ul>
			<p className="rd-quiet">
				Not valid {overview.counts.invalidated ?? 0} · Stopped partway{" "}
				{overview.counts.abandoned ?? 0}
			</p>
			<WeeklyBars weeks={overview.weeks ?? []} />
			<PlayGrid cells={[...maths, ...english]} />
			<section className="rd-recent" aria-label="Recent games">
				<h4>Recent games</h4>
				{recent.length ? (
					<ul>
						{recent.map((episode) => (
							<li key={episode.episode_id}>
								<GameRow
									title={episode.area_title?.split(" · ").at(-1) ?? "Game"}
									date={episode.started_at}
									onClick={() => onOpenEpisode(episode.episode_id)}
									status={<PlayStatus status={episode.play_status} />}
								>
									<span>
										<b>Before help</b>
										{answerLabel(episode.before_correct)}
									</span>
									<span>
										<b>After help</b>
										{answerLabel(
											episode.after_correct,
											episode.before_correct === true
												? "Not needed"
												: "Not retested",
										)}
									</span>
									{(episode.help_types ?? []).length > 0 && (
										<span className="rd-game-row__wide">
											<b>Help used</b>
											{episode.help_types.map((code) => (
												<span className="rd-help-label" key={code}>
													<HelpMark code={code} />
													{HELP_STYLE[code]?.name ?? "Help"}
												</span>
											))}
										</span>
									)}
								</GameRow>
							</li>
						))}
					</ul>
				) : (
					<EmptyStep text="Appears after the first game." />
				)}
			</section>
		</div>
	);
}

const LIVE_STEPS = [
	{ key: "try", label: "First try" },
	{ key: "why", label: "Why" },
	{ key: "chosen", label: "Help chosen" },
	{ key: "help", label: "Help" },
	{ key: "alone", label: "Try alone" },
	{ key: "learned", label: "Learned" },
] as const;

export function LivePanel({ trace }: { trace: Trace }) {
	const summary = trace.summary;
	const stopped =
		summary.play_status === "abandoned" || summary.play_status === "invalid";
	const reached = {
		try: summary.before_correct !== null,
		why: trace.model1 != null,
		chosen: (trace.model2?.order.length ?? 0) > 0,
		help: trace.rounds.length > 0,
		alone: summary.after_correct !== null,
		learned:
			summary.policy_update_status === "authorized_delayed" ||
			Boolean(trace.model3?.policy?.toLowerCase().includes("learned")),
	};
	const current = LIVE_STEPS.filter((step) => reached[step.key]).at(-1)?.key;
	const label =
		summary.play_status === "abandoned"
			? "Stopped partway · not counted"
			: summary.play_status === "invalid"
				? "Not valid · not counted"
				: summary.play_status === "live"
					? "Being played now"
					: "Finished";
	return (
		<div className="rd-stack">
			<p className={stopped ? "rd-quiet" : "rd-live"}>{label}</p>
			<ol className="rd-rail" aria-label="Steps in this game">
				{LIVE_STEPS.map((step) => (
					<li
						key={step.key}
						className={
							reached[step.key]
								? step.key === current && summary.play_status === "live"
									? "is-current"
									: "is-done"
								: undefined
						}
					>
						{step.label}
					</li>
				))}
			</ol>
			{reached.why && (
				<Card title="Why">
					<p>The three strongest reasons for this mistake.</p>
					<ul className="rd-bars" aria-label="Top reasons">
						{(trace.model1?.reasons ?? []).slice(0, 3).map((reason) => (
							<li key={reason.label} className="is-top">
								<span>{reason.label}</span>
								<span className="rd-bars__track" aria-hidden="true">
									<span
										className="rd-bars__fill"
										style={{ width: `${reason.probability * 100}%` }}
									/>
								</span>
							</li>
						))}
					</ul>
				</Card>
			)}
			{reached.chosen && (
				<Card title="Help chosen">
					<p>The first chip is the help that comes first.</p>
					<p className="rd-help-row">
						{(trace.model2?.order ?? []).map((code, index) => (
							<HelpMark key={code} code={code} large={index === 0} />
						))}
					</p>
				</Card>
			)}
			{reached.help && (
				<Card title="Help">
					<p>Each dot is one help round.</p>
					<p className="rd-help-row">
						{trace.rounds.map((round) => (
							<span key={round.round_number} className="rd-round-dot">
								<HelpMark code={round.scaffold_type} />
								<Mark
									value={
										round.outcome === "succeeded" ||
										round.outcome === "supported_success"
									}
								/>
							</span>
						))}
					</p>
				</Card>
			)}
			{reached.alone && (
				<Card title="Try alone">
					<p>The fresh question, after every help was removed.</p>
					<p className="rd-pair">
						<span>
							<Mark value={summary.before_correct} /> before
						</span>
						<span>
							<Mark value={summary.after_correct} /> after
						</span>
					</p>
				</Card>
			)}
			{reached.learned && (
				<Card title="Learned">
					<p className="rd-chip">
						+1 for <HelpMark code={summary.first_help} />
						<span className="rd-legend">
							{summary.first_help ? "" : "this help"}
						</span>
					</p>
				</Card>
			)}
		</div>
	);
}

const SHORT_HEADLINE: Record<string, string> = {
	"Probabilistic Misconception": "Found the true reason",
	"Contextual Support Selection": "Chose the help that works",
	"Independence Gain": "Gain matched real learning",
};

const METHOD_STEPS = [
	["Set", "Each model runs on a few fixed, written-down settings."],
	["Replay", "Stored games are re-run with other values to see what changes."],
	["Measure", "Finished games are scored against what the child did next."],
] as const;

type Offline = AccuracyReport["offline"];

/** What replaying the stored games with each tried value showed, for one setting. */
function ReplayRow({
	setting,
	offline,
	minimum,
}: {
	setting: ModelSetting;
	offline: Offline;
	minimum: number;
}) {
	if (!setting.replay || !offline) return null;
	if (setting.replay === "confidence_caps") {
		const rows = offline.confidence_caps;
		const count = rows[0]?.count ?? 0;
		if (rows.every((row) => row.agreement == null))
			return (
				<p className="rd-replay is-waiting">
					<span className="rd-progress" aria-hidden="true">
						<span
							style={{ width: `${Math.min(100, (count / minimum) * 100)}%` }}
						/>
					</span>
					Replay result after {minimum} games · {count} so far
				</p>
			);
		return (
			<ul className="rd-replay">
				{rows.map((row) => (
					<li key={row.confidence_cap}>
						<span>{pct(row.confidence_cap)}</span>
						<strong className="rd-num">{pct(row.agreement)}</strong>
					</li>
				))}
			</ul>
		);
	}
	return (
		<ul className="rd-replay">
			{offline.preference_thresholds.map((row) => (
				<li key={row.success_threshold}>
					<span>{row.success_threshold}</span>
					<strong className="rd-num">
						{row.changed_first_choices}/{row.checked}
					</strong>
					<small>first help changed</small>
				</li>
			))}
		</ul>
	);
}

export function CheckRow({ metric }: { metric: AccuracyMetric }) {
	const hasData =
		metric.count > 0 && metric.value != null && Number.isFinite(metric.value);
	const score = metric.unit === "score";
	const format = (value: number) => (score ? value.toFixed(2) : pct(value));
	const value = hasData ? format(metric.value as number) : "No result yet";
	const interval =
		hasData &&
		metric.interval?.every(Number.isFinite) &&
		metric.interval[0] <= metric.interval[1]
			? metric.interval
			: null;
	return (
		<li className="rd-check">
			<div className="rd-check__head">
				<h5>{metric.title}</h5>
				<strong className="rd-check__value">{value}</strong>
			</div>
			<span className="rd-evidence-status">
				{!hasData
					? "Waiting for evidence"
					: metric.small_sample
						? "Early evidence"
						: "Recorded estimate"}
			</span>
			<p>
				<b>How it is checked</b>
				{metric.method}
			</p>
			{metric.good && (
				<p>
					<b>What a better result means</b>
					{metric.good}
				</p>
			)}
			{metric.meaning && <p>{metric.meaning}</p>}
			<div className="rd-check__foot">
				<span>
					{metric.count} {metric.count === 1 ? "game" : "games"} checked
				</span>
				{interval && (
					<span>
						Estimated range: {format(interval[0])}–{format(interval[1])}
					</span>
				)}
				{metric.small_sample && <em className="rd-pill">early sign</em>}
			</div>
		</li>
	);
}

export function AccuracyPanel({ report }: { report: AccuracyReport }) {
	const simulation = report.simulation;
	return (
		<div className="rd-stack rd-validate-page">
			<header className="rd-model__head">
				<h3>How we validate each model</h3>
				<ol className="rd-method">
					{METHOD_STEPS.map(([step, line], index) => (
						<li key={step}>
							<span className="rd-method__n">{index + 1}</span>
							<strong>{step}</strong>
							<span>{line}</span>
						</li>
					))}
				</ol>
				<p className="rd-quiet">
					Rates include an estimated range when available. Under{" "}
					{report.minimum_sessions ?? 20} games it is marked as an early sign.
				</p>
			</header>
			<div className="rd-validate-grid">
				{report.models.map((model) => (
					<article className="rd-validate" key={model.name}>
						<header>
							<h4>{model.name}</h4>
							<p className="rd-quiet">{model.subtitle}</p>
						</header>
						<section>
							<h5 className="rd-eyebrow">Parameters checked</h5>
							<ul className="rd-settings">
								{(model.settings ?? []).map((setting) => (
									<li key={setting.name}>
										<div className="rd-settings__head">
											<span>{setting.name}</span>
											<strong>{setting.value}</strong>
										</div>
										{setting.tried.length > 0 && (
											<p className="rd-tried">
												Tried{" "}
												{setting.tried.map((value) => (
													<span
														key={value}
														className={
															value === setting.value ? "is-current" : undefined
														}
													>
														{value}
													</span>
												))}
											</p>
										)}
										<p className="rd-quiet">{setting.how}</p>
										<ReplayRow
											setting={setting}
											offline={report.offline}
											minimum={report.minimum_sessions ?? 20}
										/>
									</li>
								))}
							</ul>
						</section>
						<section>
							<h5 className="rd-eyebrow">Accuracy checks</h5>
							<ul className="rd-checks">
								{model.metrics
									.filter((metric) => metric.tile)
									.map((metric) => (
										<CheckRow key={metric.key} metric={metric} />
									))}
							</ul>
							{model.leakage && (
								<p className="rd-chip">
									Answer leaks: {model.leakage.count} of {model.leakage.checked}{" "}
									games
								</p>
							)}
						</section>
					</article>
				))}
			</div>
			{simulation && (
				<section
					className="rd-sim-mini"
					aria-label="Example from simulated learners"
				>
					<div>
						<h4>Example: simulated learners</h4>
						<p className="rd-quiet">
							{simulation.cohort.learners} learners with known answers ·{" "}
							{simulation.cohort.sessions.toLocaleString("en-GB")} games
						</p>
					</div>
					<ul>
						{simulation.models.map((model) => {
							const headline = model.metrics.find(
								(metric) => metric.title === model.headline,
							);
							return (
								<li key={model.name}>
									<strong className="rd-num">
										{pct(headline?.value ?? null)}
									</strong>
									<span>{SHORT_HEADLINE[model.name] ?? model.name}</span>
									{model.reference?.value != null && (
										<small>
											vs {pct(model.reference.value)} {model.reference.label}
										</small>
									)}
								</li>
							);
						})}
					</ul>
					<details className="rd-assumptions">
						<summary>How they behave</summary>
						<ul>
							{simulation.assumptions.map((rule) => (
								<li key={rule}>{rule}</li>
							))}
						</ul>
					</details>
				</section>
			)}
		</div>
	);
}

export function ProfilePanel({ profile }: { profile: LearnerProfile }) {
	return (
		<div className="rd-stack">
			<Card title="Shared child account">
				<dl className="rd-account">
					<dt>Name</dt>
					<dd>{profile.name}</dd>
					<dt>Learner ID</dt>
					<dd>
						<code>{profile.learner_id}</code>
					</dd>
					<dt>Class</dt>
					<dd>
						{profile.grade ? `Grade ${profile.grade}` : "Not recorded"} ·{" "}
						{profile.language === "si"
							? "Sinhala medium"
							: "Language not recorded"}
					</dd>
					<dt>Games played</dt>
					<dd>
						{profile.games_played} finished games · Mathematics{" "}
						{profile.areas_played.MAT.length} of {profile.areas_available.MAT}{" "}
						games tried · English {profile.areas_played.ENG.length} of{" "}
						{profile.areas_available.ENG} games tried
					</dd>
				</dl>
			</Card>
			<Card title="Mistakes seen most often">
				{profile.mistakes.length ? (
					<ul>
						{profile.mistakes.map((row) => (
							<li key={`${row.title}-${row.reason}`}>
								{row.title}: {row.reason} ({row.count})
							</li>
						))}
					</ul>
				) : (
					<p>No mistakes have been recorded yet.</p>
				)}
			</Card>
		</div>
	);
}

export function EpisodeFlow({ episode }: { episode: EpisodeSummary }) {
	return (
		<span className="rd-help-row">
			<Mark value={episode.before_correct} />
			{episode.help_types.map((code) => (
				<HelpMark key={code} code={code} />
			))}
			<Mark value={episode.after_correct} />
		</span>
	);
}
