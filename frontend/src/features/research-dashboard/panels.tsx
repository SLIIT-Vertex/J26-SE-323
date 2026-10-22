import type { ReactNode } from "react";
import type {
	AccuracyCheck,
	AccuracyReport,
	EpisodeSummary,
	LearnerProfile,
	Overview,
	Trace,
} from "./api";
import { HELP_STYLE, HelpMark, KpiTile, pct, WeeklyBars } from "./charts";
import { answerLabel, GameRow, PlayStatus } from "./GameRow";

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
							<span
								key={round.position}
								className="rd-round-dot"
								title={
									round.phase === "follow_up" ? "After the try alone" : undefined
								}
							>
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

const CHECK_STATUS: Record<AccuracyCheck["status"], string> = {
	passing: "Working accurately",
	not_passing: "Not yet beating the baseline",
	not_enough_data: "Not enough games yet",
};

/** One model's deterministic accuracy test: the rule, today's number and the verdict. */
export function ModelCheckCard({ check }: { check: AccuracyCheck }) {
	const hasData = check.count > 0 && check.value != null;
	const range = hasData ? check.interval : null;
	const waiting = Math.max(0, check.minimum - check.count);
	return (
		<section className={`rd-verdict is-${check.status.replace(/_/g, "-")}`}>
			<p className="rd-verdict__status">{CHECK_STATUS[check.status]}</p>
			<div className="rd-verdict__numbers">
				<strong className="rd-num">
					{hasData ? pct(check.value) : "No result yet"}
				</strong>
				{check.reference != null && (
					<span>
						vs {pct(check.reference)} {check.reference_label}
					</span>
				)}
			</div>
			<p className="rd-quiet">
				{check.count} {check.count === 1 ? "game" : "games"}
				{range && ` · 95% range ${pct(range[0])}–${pct(range[1])}`}
				{waiting > 0 && ` · ${waiting} more needed`}
			</p>
			<p className="rd-verdict__rule">{check.rule}</p>
		</section>
	);
}

export function AccuracyPanel({ report }: { report: AccuracyReport }) {
	const models = report.models.filter((model) => model.check);
	const gain = report.models.find((model) => model.kind === "measurement");
	const fair = gain?.metrics.find((metric) => metric.key === "fair");
	return (
		<div className="rd-stack rd-validate-page">
			<header className="rd-model__head">
				<h3>Is each model working accurately?</h3>
				<p className="rd-quiet">
					Each model has one fixed test, run on this child's finished games. It
					passes only when the low end of its 95% range beats a simple baseline,
					with at least {report.minimum_sessions ?? 20} games behind it.
				</p>
			</header>
			<div className="rd-validate-grid">
				{models.map((model) => (
					<article className="rd-validate" key={model.name}>
						<header>
							<h4>{model.name}</h4>
							<p className="rd-quiet">{model.check?.question}</p>
						</header>
						{model.check && <ModelCheckCard check={model.check} />}
						<section>
							<h5 className="rd-eyebrow">Settings</h5>
							<ul className="rd-settings">
								{(model.settings ?? []).map((setting) => (
									<li key={setting.name} className="rd-settings__head">
										<span>{setting.name}</span>
										<strong>{setting.value}</strong>
									</li>
								))}
							</ul>
						</section>
					</article>
				))}
			</div>
			{gain && (
				<p className="rd-quiet rd-gain-note">
					Independence gain is a before-and-after score, not a learned model, so
					it has no accuracy test.
					{fair && fair.count > 0 && fair.value != null
						? ` ${pct(fair.value)} of ${fair.count} help games passed its fairness checks.`
						: ""}
				</p>
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
