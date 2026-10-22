import type { ReactNode } from "react";
import type {
	GainSeries,
	HistoryEntry,
	MisconceptionSeries,
	SupportSeries,
} from "./api";
import {
	DotStrip,
	DotTimeline,
	HBarList,
	HELP_STYLE,
	HelpMark,
	KpiTile,
	pct,
	RunningRateBand,
	StackedBar100,
} from "./charts";
import { answerLabel, GameRow, PlayStatus } from "./GameRow";

/** Every help, most to least preferred, from what worked when help was removed. */
function HelpRanking({
	rows,
}: {
	rows: NonNullable<SupportSeries["preference"]>;
}) {
	const top = Math.max(1, ...rows.map((row) => row.credited));
	return (
		<section className="rd-rank" aria-labelledby="rd-rank-title">
			<header>
				<h4 id="rd-rank-title">Help preference for this child</h4>
				<p className="rd-quiet">
					Most preferred first · ranked by how often the child then managed
					alone
				</p>
			</header>
			<ol>
				{rows.map((row) => {
					const name =
						HELP_STYLE[row.help as keyof typeof HELP_STYLE]?.name ?? "Help";
					return (
						<li
							key={row.help}
							className={row.tried ? undefined : "is-untried"}
							data-rank={row.rank}
						>
							<span className="rd-rank__n">{row.rank}</span>
							<HelpMark code={row.help} />
							<span className="rd-rank__name">{name}</span>
							<span className="rd-rank__bar" aria-hidden="true">
								<span
									className="is-good"
									style={{ width: `${(row.successes / top) * 100}%` }}
								/>
								<span
									className="is-rest"
									style={{
										width: `${((row.credited - row.successes) / top) * 100}%`,
									}}
								/>
							</span>
							<span className="rd-rank__text">
								{!row.tried
									? "Not tried yet"
									: row.credited
										? `${row.successes} of ${row.credited} alone after`
										: "Did not work yet"}
								{row.did_not_help > 0 && (
									<small> · didn't help {row.did_not_help}×</small>
								)}
							</span>
						</li>
					);
				})}
			</ol>
			<p className="rd-rank__ends rd-quiet" aria-hidden="true">
				<span>▲ Most preferred</span>
				<span>Least preferred ▼</span>
			</p>
		</section>
	);
}

/** One game, start to finish: alone, help, alone again. The three outcomes counted. */
function BeforeAfter({ grid }: { grid: GainSeries["grid"] }) {
	const outcomes = [
		{
			key: "learned",
			before: false,
			after: true,
			title: "Learned with help",
			text: "Wrong alone → help → right alone",
			value: grid.wrong_then_right,
			tone: "good",
		},
		{
			key: "not-yet",
			before: false,
			after: false,
			title: "Not yet",
			text: "Wrong alone → help → still wrong alone",
			value: grid.wrong_then_wrong,
			tone: "bad",
		},
		{
			key: "knew",
			before: true,
			after: null,
			title: "Already knew it",
			text: "Right on the first try, so no help was needed",
			value: grid.right_first,
			tone: "grey",
		},
	] as const;
	return (
		<section className="rd-flow" aria-labelledby="rd-flow-title">
			<h4 id="rd-flow-title">How each game is measured</h4>
			<ol className="rd-flow__steps">
				<li>
					<b>1</b> Question alone
					<small>No help shown</small>
				</li>
				<li aria-hidden="true" className="rd-flow__arrow">
					→
				</li>
				<li>
					<b>2</b> Help
					<small>Only if the first answer was wrong</small>
				</li>
				<li aria-hidden="true" className="rd-flow__arrow">
					→
				</li>
				<li>
					<b>3</b> Similar question alone
					<small>Help removed again</small>
				</li>
			</ol>
			<ul className="rd-flow__outcomes">
				{outcomes.map((row) => (
					<li key={row.key} className={`is-${row.tone}`}>
						<strong className="rd-num">{row.value}</strong>
						<span>
							<b>{row.title}</b>
							<small>{row.text}</small>
						</span>
					</li>
				))}
			</ul>
		</section>
	);
}

function ModelTab({
	title,
	question,
	top,
	kpis,
	large,
	small,
	recent,
}: {
	title: string;
	question: string;
	top?: ReactNode;
	kpis: ReactNode;
	large?: ReactNode;
	small: ReactNode;
	recent: ReactNode;
}) {
	return (
		<div className="rd-model">
			<header className="rd-model__head">
				<h3>{title}</h3>
				<p>{question}</p>
			</header>
			<ul className="rd-kpis">{kpis}</ul>
			{top}
			{large && <div className="rd-model__large">{large}</div>}
			<div className="rd-model__small">{small}</div>
			<section className="rd-recent" aria-label="Recent games">
				<h4>Recent games</h4>
				<ul>{recent}</ul>
			</section>
		</div>
	);
}

export function MisconceptionTab({
	series,
	history,
	selected,
	onSelect,
}: {
	series: MisconceptionSeries | null;
	history: HistoryEntry[];
	selected: string | null;
	onSelect(id: string): void;
}) {
	const data = series ?? emptyMisconception();
	return (
		<ModelTab
			title="Probabilistic Misconception"
			question="Why did the child get it wrong?"
			kpis={
				<>
					<KpiTile
						label="Mistakes analysed"
						value={String(data.kpis.analysed)}
					/>
					<KpiTile
						label="Most common reason"
						value={String(data.kpis.top_reason.count)}
						detail={data.kpis.top_reason.label || "None yet"}
					/>
					<KpiTile
						label="Average confidence"
						value={pct(data.kpis.mean_confidence)}
					/>
				</>
			}
			large={
				<DotTimeline
					points={data.points}
					selected={selected}
					onSelect={onSelect}
				/>
			}
			small={
				<>
					<HBarList
						title="Most frequent predicted reasons"
						ariaLabel="The reasons seen most often, with how many games."
						rows={data.top_reasons.map((row) => ({
							label: row.label,
							value: row.count,
							text: String(row.count),
						}))}
					/>
					<section
						className="rd-card rd-memory"
						aria-label="Confidence with and without history"
					>
						<h4>Confidence with and without history</h4>
						<p className="rd-quiet">
							Average confidence in the predicted reason for a mistake.
						</p>
						<dl>
							{[
								["With previous answers", data.memory.with_history],
								["This answer only", data.memory.without],
							].map(([label, group]) => {
								const sample = group as { count: number; mean: number | null };
								return (
									<div key={String(label)}>
										<dt>{String(label)}</dt>
										<dd>
											<strong>
												{sample.count > 0 ? pct(sample.mean) : "No data yet"}
											</strong>
											<span>{sample.count} games</span>
										</dd>
									</div>
								);
							})}
						</dl>
						<p className="rd-quiet">
							Higher confidence does not prove a more accurate prediction or
							better learning.
						</p>
						{(!data.memory.with_history.count ||
							!data.memory.without.count) && (
							<p className="rd-note">
								A comparison needs games in both groups. The missing group has
								no recorded games yet.
							</p>
						)}
					</section>
				</>
			}
			recent={data.recent.slice(0, 8).map((row) => {
				const entry = history.find(
					(item) => item.episode_id === row.episode_id,
				);
				return (
					<li key={row.episode_id}>
						<GameRow
							title={entry?.game ?? row.game_short}
							date={entry?.played_at}
							selected={selected === row.episode_id}
							onClick={() => onSelect(row.episode_id)}
							status={<PlayStatus status={entry?.play_status} />}
						>
							<span className="rd-game-row__wide">
								<b>Predicted reason</b>
								{row.reason_short}
							</span>
							<span>
								<b>Confidence</b>
								{pct(row.confidence)}
							</span>
						</GameRow>
					</li>
				);
			})}
		/>
	);
}

export function SupportTab({
	series,
	history,
	selected,
	onSelect,
}: {
	series: SupportSeries | null;
	history: HistoryEntry[];
	selected: string | null;
	onSelect(id: string): void;
}) {
	const data = series ?? emptySupport();
	const drivers = data.drivers;
	return (
		<ModelTab
			title="Contextual Support Selection"
			question="Which help should come first?"
			top={
				data.preference?.length ? <HelpRanking rows={data.preference} /> : null
			}
			kpis={
				<>
					<KpiTile label="Help sessions" value={String(data.kpis.sessions)} />
					<KpiTile
						label="First help worked"
						value={pct(data.kpis.first_help_worked.value)}
						detail={`${data.kpis.first_help_worked.count} games`}
					/>
					<KpiTile
						label="Skills with a preferred help"
						value={String(data.kpis.skills_with_best_help)}
					/>
				</>
			}
			small={
				<>
					<HBarList
						title="Independent retest results by help"
						ariaLabel="Independent successes divided by times each help was credited."
						rows={data.worked.map((row) => ({
							label:
								HELP_STYLE[row.help as keyof typeof HELP_STYLE]?.name ?? "Help",
							value: row.credited ? row.successes / row.credited : 0,
							text: `${row.successes} of ${row.credited}`,
							star: row.star,
						}))}
						empty="Appears after a credited help result."
					/>
					<StackedBar100
						title="Why it chose, all games"
						ariaLabel="How often the likely reason, the child's past results, or the fixed order drove the choice."
						segments={[
							{ label: "Likely reason", value: drivers.reason, tone: "accent" },
							{
								label: "Past results",
								value: drivers.history,
								tone: "soft",
							},
							{ label: "Fixed order", value: drivers.fixed, tone: "grey" },
						]}
					/>
				</>
			}
			recent={data.recent.slice(0, 8).map((row) => {
				const entry = history.find(
					(item) => item.episode_id === row.episode_id,
				);
				const excluded =
					entry?.play_status === "abandoned" ||
					entry?.play_status === "invalid";
				return (
					<li key={row.episode_id}>
						<GameRow
							title={entry?.game ?? "Game"}
							date={entry?.played_at}
							selected={selected === row.episode_id}
							onClick={() => onSelect(row.episode_id)}
							status={<PlayStatus status={entry?.play_status} />}
						>
							<span className="rd-game-row__wide">
								<b>Suggested help order</b>
								{row.order.map((code, index) => (
									<span className="rd-help-label" key={code}>
										{index + 1}.{" "}
										{HELP_STYLE[code as keyof typeof HELP_STYLE]?.name ??
											"Help"}
									</span>
								))}
							</span>
							<span className="rd-game-row__wide">
								<b>Independent retest</b>
								{excluded
									? "Not counted"
									: entry?.in_progress
										? "Awaiting result"
										: answerLabel(row.after, "Not retested")}
							</span>
						</GameRow>
					</li>
				);
			})}
		/>
	);
}

export function GainTab({
	series,
	history,
	selected,
	onSelect,
}: {
	series: GainSeries | null;
	history: HistoryEntry[];
	selected: string | null;
	onSelect(id: string): void;
}) {
	const data = series ?? emptyGain();
	return (
		<ModelTab
			title="Independence Gain"
			question="After help is removed, can the child do it alone?"
			top={<BeforeAfter grid={data.grid} />}
			kpis={
				<>
					<KpiTile label="Fair tests" value={String(data.kpis.fair_tests)} />
					<KpiTile
						label="Could do it alone"
						value={pct(data.kpis.alone.value)}
						detail={`${data.kpis.alone.count} games`}
					/>
					<KpiTile label="Fair-test rate" value={pct(data.kpis.fair_rate)} />
				</>
			}
			large={
				<RunningRateBand
					points={data.points}
					selected={selected}
					onSelect={onSelect}
				/>
			}
			small={
				<DotStrip
					title="By game"
					ariaLabel="Fair tests in date order for each game area."
					rows={data.by_game.map((row) => ({
						label: row.game,
						points: row.points,
					}))}
				/>
			}
			recent={data.recent.slice(0, 8).map((row) => {
				const entry = history.find(
					(item) => item.episode_id === row.episode_id,
				);
				return (
					<li key={row.episode_id}>
						<GameRow
							title={entry?.game ?? "Game"}
							date={entry?.played_at}
							selected={selected === row.episode_id}
							onClick={() => onSelect(row.episode_id)}
							status={<PlayStatus status={entry?.play_status} />}
						>
							<span>
								<b>1st try, alone</b>
								{answerLabel(row.before)}
							</span>
							<span>
								<b>Retry after help, alone</b>
								{answerLabel(row.after, "Not retested")}
							</span>
							<span className="rd-game-row__wide">
								<b>Independence gain</b>
								{row.gain === 1
									? "+1 · Learned with help"
									: row.gain === 0
										? "0 · Not yet"
										: "Not measured"}
							</span>
						</GameRow>
					</li>
				);
			})}
		/>
	);
}

function emptyMisconception(): MisconceptionSeries {
	return {
		kpis: {
			analysed: 0,
			top_reason: { label: "", count: 0 },
			mean_confidence: null,
		},
		points: [],
		top_reasons: [],
		memory: {
			with_history: { count: 0, mean: null },
			without: { count: 0, mean: null },
		},
		recent: [],
	};
}

function emptySupport(): SupportSeries {
	return {
		kpis: {
			sessions: 0,
			first_help_worked: { value: 0, count: 0 },
			skills_with_best_help: 0,
		},
		points: [],
		worked: [],
		drivers: { reason: 0, history: 0, fixed: 0 },
		recent: [],
	};
}

function emptyGain(): GainSeries {
	return {
		kpis: { fair_tests: 0, alone: { value: null, count: 0 }, fair_rate: null },
		points: [],
		grid: { wrong_then_right: 0, wrong_then_wrong: 0, right_first: 0 },
		by_game: [],
		recent: [],
	};
}
