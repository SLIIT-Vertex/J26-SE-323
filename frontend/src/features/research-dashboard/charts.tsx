import type { ReactNode } from "react";

/** One help style, used the same way on every chart and legend. */
export const HELP_STYLE = {
	visual_guidance: { name: "Visual hint", glyph: "eye" },
	step_by_step_guidance: {
		name: "Question-by-question guidance",
		glyph: "ask",
	},
	conceptual_reexplanation: { name: "Explain the idea again", glyph: "idea" },
	simpler_same_game: { name: "Easier version first", glyph: "down" },
	prerequisite_repair: { name: "Practise the skill underneath", glyph: "loop" },
	worked_parallel_example: { name: "Watch a solved example", glyph: "play" },
} as const;

export type HelpCode = keyof typeof HELP_STYLE;
type Glyph = (typeof HELP_STYLE)[HelpCode]["glyph"];

const ACCENT = "var(--rd-accent)";
const GREY = "#94a3b8";
const GOOD = "var(--rd-good)";
const BAD = "var(--rd-bad)";

export function pct(value: number | null | undefined): string {
	if (value == null || Number.isNaN(value)) return "—";
	return `${Math.round(value * 100)}%`;
}

export function shortDate(value: string | null | undefined): string {
	if (!value) return "";
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return "";
	return date.toLocaleDateString("en-GB", {
		day: "numeric",
		month: "short",
		timeZone: "Asia/Colombo",
	});
}

function helpOf(code: string | null | undefined) {
	return HELP_STYLE[code as HelpCode];
}

export function HelpGlyph({ kind }: { kind: Glyph }) {
	if (kind === "eye") {
		return (
			<svg viewBox="0 0 16 16" aria-hidden="true" className="rd-glyph">
				<path
					d="M1 8s2.5-4 7-4 7 4 7 4-2.5 4-7 4-7-4-7-4z"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.4"
				/>
				<circle cx="8" cy="8" r="2" fill="currentColor" />
			</svg>
		);
	}
	if (kind === "ask") {
		return (
			<svg viewBox="0 0 16 16" aria-hidden="true" className="rd-glyph">
				<path
					d="M5 6a3 3 0 1 1 4.2 2.7C8.4 9.2 8 9.6 8 10.2"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.4"
					strokeLinecap="round"
				/>
				<circle cx="8" cy="12.4" r="0.8" fill="currentColor" />
			</svg>
		);
	}
	if (kind === "idea") {
		return (
			<svg viewBox="0 0 16 16" aria-hidden="true" className="rd-glyph">
				<circle
					cx="8"
					cy="7"
					r="3.2"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.4"
				/>
				<path
					d="M6.4 10.2h3.2M7 12.2h2"
					stroke="currentColor"
					strokeWidth="1.4"
					strokeLinecap="round"
				/>
			</svg>
		);
	}
	if (kind === "down") {
		return (
			<svg viewBox="0 0 16 16" aria-hidden="true" className="rd-glyph">
				<path
					d="M8 2v9M4.5 8.5 8 12l3.5-3.5"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.6"
					strokeLinecap="round"
					strokeLinejoin="round"
				/>
			</svg>
		);
	}
	if (kind === "loop") {
		return (
			<svg viewBox="0 0 16 16" aria-hidden="true" className="rd-glyph">
				<path
					d="M12.5 6A4.5 4.5 0 1 0 13 9"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.4"
					strokeLinecap="round"
				/>
				<path
					d="M11 6.2h2.4V3.8"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.4"
					strokeLinecap="round"
				/>
			</svg>
		);
	}
	return (
		<svg viewBox="0 0 16 16" aria-hidden="true" className="rd-glyph">
			<path d="M5 3.5v9l8-4.5-8-4.5z" fill="currentColor" />
		</svg>
	);
}

export function HelpMark({
	code,
	large = false,
}: {
	code: string | null | undefined;
	large?: boolean;
}) {
	const style = helpOf(code);
	if (!style) return null;
	return (
		<span className={large ? "rd-help is-large" : "rd-help"} title={style.name}>
			<HelpGlyph kind={style.glyph} />
			<span className="sr-only">{style.name}</span>
		</span>
	);
}

function DataTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
	return (
		<table className="sr-only">
			<thead>
				<tr>
					{headers.map((header) => (
						<th key={header}>{header}</th>
					))}
				</tr>
			</thead>
			<tbody>
				{rows.map((row, position) => (
					// Rows are a fixed, read-only snapshot; two games can share every visible cell.
					// biome-ignore lint/suspicious/noArrayIndexKey: static table, order never changes
					<tr key={position}>
						{row.map((cell, index) => (
							<td key={`${headers[index]}-${cell}`}>{cell}</td>
						))}
					</tr>
				))}
			</tbody>
		</table>
	);
}

function ChartShell({
	title,
	ariaLabel,
	headers,
	rows,
	empty,
	large = false,
	height = 180,
	children,
}: {
	title: string;
	ariaLabel: string;
	headers: string[];
	rows: string[][];
	empty?: string;
	large?: boolean;
	height?: number;
	children?: ReactNode;
}) {
	return (
		<figure className={large ? "rd-chart is-large" : "rd-chart"}>
			<figcaption>{title}</figcaption>
			{empty ? (
				<div className="rd-chart__empty">
					<p>{empty}</p>
				</div>
			) : (
				<svg role="img" aria-label={ariaLabel} viewBox={`0 0 320 ${height}`}>
					{children}
				</svg>
			)}
			<DataTable headers={headers} rows={rows.length ? rows : [["—"]]} />
		</figure>
	);
}

function tickIndexes(count: number): number[] {
	if (count <= 6) return [...Array(count).keys()];
	return [...Array(6).keys()].map((index) =>
		Math.round((index * (count - 1)) / 5),
	);
}

export function KpiTile({
	label,
	value,
	detail,
}: {
	label: string;
	value: string;
	detail?: string;
}) {
	return (
		<li className="rd-kpi">
			<strong className="rd-num">{value}</strong>
			<span>{label}</span>
			{detail ? <small className="rd-tick">{detail}</small> : null}
		</li>
	);
}

export function DotTimeline({
	points,
	selected,
	onSelect,
	empty = "Appears after the first wrong answer.",
}: {
	points: {
		episode_id: string;
		at: string;
		game: string;
		confidence: number;
		repeat_reason: boolean;
		used_history: boolean;
		reason: string;
	}[];
	selected?: string | null;
	onSelect?(id: string): void;
	empty?: string;
}) {
	const ordered = points
		.filter(
			(point) =>
				Number.isFinite(point.confidence) &&
				point.confidence >= 0 &&
				point.confidence <= 1,
		)
		.slice()
		.sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
	const plot = ordered.map((point, index) => ({
		...point,
		x: 42 + (index * 252) / Math.max(ordered.length - 1, 1),
		y: 20 + (1 - point.confidence) * 128,
	}));
	return (
		<div className="rd-confidence">
			<ChartShell
				large
				height={200}
				title="Confidence over games"
				ariaLabel="Line graph of confidence in the predicted reason, from zero to one hundred percent. Games run from oldest to newest."
				headers={["Game", "Date", "Confidence", "History"]}
				rows={ordered.map((point) => [
					point.game,
					shortDate(point.at),
					pct(point.confidence),
					point.used_history ? "Previous answers used" : "This answer only",
				])}
				empty={plot.length ? undefined : empty}
			>
				{[0, 0.5, 1].map((value) => (
					<g key={value}>
						<line
							x1="42"
							x2="300"
							y1={20 + (1 - value) * 128}
							y2={20 + (1 - value) * 128}
							stroke="#e2e8f0"
						/>
						<text
							x="36"
							y={24 + (1 - value) * 128}
							textAnchor="end"
							fill="#5b6475"
						>
							{pct(value)}
						</text>
					</g>
				))}
				<line
					x1="42"
					x2="300"
					y1={20 + 0.6 * 128}
					y2={20 + 0.6 * 128}
					stroke={GREY}
					strokeDasharray="4 3"
				/>
				<polyline
					className="rd-confidence-line"
					points={plot.map((point) => `${point.x},${point.y}`).join(" ")}
					fill="none"
					stroke={ACCENT}
					strokeWidth="2"
					vectorEffect="non-scaling-stroke"
				/>
				{plot.map((point) => (
					<g
						key={point.episode_id}
						data-episode={point.episode_id}
						data-selected={selected === point.episode_id}
					>
						<circle
							cx={point.x}
							cy={point.y}
							r={selected === point.episode_id ? 5 : 3}
							fill={point.used_history ? ACCENT : "#fff"}
							stroke={ACCENT}
							strokeWidth="1.5"
						/>
						<title>
							{point.game}: {pct(point.confidence)} on {shortDate(point.at)}.{" "}
							{point.reason}.{" "}
							{point.used_history
								? "Previous answers used"
								: "This answer only"}
						</title>
					</g>
				))}
				{plot.length > 0 && (
					<>
						<text x="42" y="174" fill="#5b6475">
							{shortDate(plot[0].at)}
						</text>
						<text x="294" y="174" textAnchor="end" fill="#5b6475">
							{shortDate(plot[plot.length - 1].at)}
						</text>
						<text x="168" y="194" textAnchor="middle" fill="#5b6475">
							Games · oldest → newest
						</text>
					</>
				)}
			</ChartShell>
			<div className="rd-chart-legend">
				<span>● Previous answers used</span>
				<span>○ This answer only</span>
				<span>Dashed line: 40% confidence</span>
			</div>
			{onSelect && ordered.length > 0 && (
				<label className="rd-chart-picker">
					Inspect a game
					<select
						value={
							selected && ordered.some((point) => point.episode_id === selected)
								? selected
								: ""
						}
						onChange={(event) =>
							event.target.value && onSelect(event.target.value)
						}
					>
						<option value="">Choose a game</option>
						{ordered.map((point, index) => (
							<option key={point.episode_id} value={point.episode_id}>
								{index + 1}. {point.game} · {shortDate(point.at)} ·{" "}
								{pct(point.confidence)}
							</option>
						))}
					</select>
				</label>
			)}
		</div>
	);
}

export function RunningRateBand({
	points,
	selected,
	onSelect,
	empty = "Appears after the first fair test.",
}: {
	points: {
		episode_id: string;
		at: string;
		gain: number;
		running_rate: number;
		low: number;
		high: number;
	}[];
	selected?: string | null;
	onSelect?(id: string): void;
	empty?: string;
}) {
	const coords = points.map((point, index) => {
		const x = 36 + (index * 260) / Math.max(points.length - 1, 1);
		const y = (value: number) => 16 + (1 - value) * 120;
		return {
			...point,
			x,
			y: y(point.running_rate),
			low: y(point.low),
			high: y(point.high),
		};
	});
	const band = coords
		.map((point) => `${point.x},${point.high}`)
		.concat([...coords].reverse().map((point) => `${point.x},${point.low}`))
		.join(" ");
	return (
		<ChartShell
			large
			title="Can the child do it alone? Over time"
			ariaLabel="Running share of fair tests the child could do alone, with a shaded uncertainty band."
			headers={["Date", "Running share", "Low", "High"]}
			rows={points.map((point) => [
				shortDate(point.at),
				pct(point.running_rate),
				pct(point.low),
				pct(point.high),
			])}
			empty={points.length ? undefined : empty}
		>
			{coords.length > 1 && (
				<polygon points={band} fill="var(--rd-accent-soft)" stroke="none" />
			)}
			<polyline
				points={coords.map((point) => `${point.x},${point.y}`).join(" ")}
				fill="none"
				stroke={ACCENT}
				strokeWidth="2"
			/>
			{coords.map((point) => (
				// biome-ignore lint/a11y/noStaticElementInteractions: SVG chart mark
				<g
					key={point.episode_id}
					className="rd-mark-in"
					data-episode={point.episode_id}
					data-selected={selected === point.episode_id}
					onClick={() => onSelect?.(point.episode_id)}
				>
					<circle cx={point.x} cy="148" r="3" fill={point.gain ? GOOD : GREY} />
					<title>
						{pct(point.running_rate)} on {shortDate(point.at)}, between{" "}
						{pct(point.low)} and {pct(point.high)}
					</title>
				</g>
			))}
			{tickIndexes(points.length).map((index) => (
				<text
					key={points[index].episode_id}
					x={coords[index].x}
					y="170"
					textAnchor="middle"
					fill={GREY}
					fontSize="11"
				>
					{shortDate(points[index].at)}
				</text>
			))}
		</ChartShell>
	);
}

export function HBarList({
	title,
	ariaLabel,
	rows,
	empty = "Appears after the first counted game.",
	suffix = "",
}: {
	title: string;
	ariaLabel: string;
	rows: {
		label: string;
		value: number;
		text: string;
		title?: string;
		star?: boolean;
	}[];
	empty?: string;
	suffix?: string;
}) {
	const max = Math.max(...rows.map((row) => row.value), 0.0001);
	return (
		<figure className="rd-chart rd-bar-list" aria-label={ariaLabel}>
			<figcaption>{title}</figcaption>
			{rows.length ? (
				<ul>
					{rows.map((row) => (
						<li key={row.label}>
							<div>
								<span>
									{row.star ? "★ " : ""}
									{row.label}
								</span>
								<strong>
									{row.text}
									{suffix}
								</strong>
							</div>
							<span className="rd-bar-track" aria-hidden="true">
								<i
									style={{
										width: `${Math.max(0, Math.min(100, (row.value / max) * 100))}%`,
									}}
								/>
							</span>
						</li>
					))}
				</ul>
			) : (
				<p className="rd-empty">{empty}</p>
			)}
			<DataTable
				headers={["Label", "Value"]}
				rows={rows.map((row) => [row.label, row.text])}
			/>
		</figure>
	);
}

export function StackedBar100({
	title,
	ariaLabel,
	segments,
	empty = "Appears after the first help choice.",
}: {
	title: string;
	ariaLabel: string;
	segments: {
		label: string;
		value: number;
		tone: "accent" | "soft" | "grey";
	}[];
	empty?: string;
}) {
	const total = segments.reduce((sum, segment) => sum + segment.value, 0);
	let cursor = 16;
	const fills = { accent: ACCENT, soft: "#a5b4fc", grey: GREY };
	return (
		<ChartShell
			title={title}
			ariaLabel={ariaLabel}
			headers={["Rule", "Games"]}
			rows={segments.map((segment) => [segment.label, String(segment.value)])}
			empty={total ? undefined : empty}
			height={120}
		>
			{segments.map((segment) => {
				const width = total ? (segment.value / total) * 288 : 0;
				const x = cursor;
				cursor += width;
				return (
					<g key={segment.label}>
						<rect
							x={x}
							y="36"
							width={Math.max(width, 0)}
							height="28"
							fill={fills[segment.tone]}
						/>
						<title>
							{segment.label}: {segment.value}
						</title>
					</g>
				);
			})}
			{segments.map((segment, index) => (
				<text
					key={segment.label}
					x="16"
					y={88 + index * 14}
					fill="#334155"
					fontSize="11"
				>
					{segment.label} {segment.value}
				</text>
			))}
		</ChartShell>
	);
}

export function RangeBar({
	label,
	value,
	interval,
	reference,
	lowerBetter = false,
}: {
	label: string;
	value: number | null;
	interval?: [number, number] | null;
	reference?: { value: number; label: string } | null;
	lowerBetter?: boolean;
}) {
	const mark =
		value == null ? null : Math.max(0, Math.min(1, value)) * 240 + 40;
	const low = interval ? Math.max(0, interval[0]) * 240 + 40 : null;
	const high = interval ? Math.min(1, interval[1]) * 240 + 40 : null;
	const ref = reference ? reference.value * 240 + 40 : null;
	return (
		<span className="rd-range-wrap">
			<svg
				className="rd-range"
				role="img"
				aria-label={label}
				viewBox="0 0 320 36"
			>
				<rect x="40" y="14" width="240" height="8" rx="4" fill="#e2e8f0" />
				{low != null && high != null && (
					<rect
						x={low}
						y="14"
						width={Math.max(high - low, 2)}
						height="8"
						fill="#c7d2fe"
					/>
				)}
				{mark != null && (
					<rect x={mark} y="8" width="3" height="20" fill={ACCENT} />
				)}
				{ref != null && (
					<path d={`M${ref} 6l4 5h-8z`} fill={GREY}>
						<title>
							{reference?.label} {pct(reference?.value)}
						</title>
					</path>
				)}
				<title>
					{label}:{" "}
					{lowerBetter ? (value == null ? "—" : value.toFixed(2)) : pct(value)}
				</title>
			</svg>
			<table className="sr-only">
				<tbody>
					<tr>
						<td>{label}</td>
						<td>{value == null ? "—" : String(value)}</td>
					</tr>
				</tbody>
			</table>
		</span>
	);
}

export function PairedBars({
	title,
	ariaLabel,
	rows,
	empty = "Appears when both orders have been checked.",
}: {
	title: string;
	ariaLabel: string;
	rows: {
		label: string;
		accent: { value: number | null; interval: [number, number] | null };
		grey: { value: number | null; interval: [number, number] | null };
	}[];
	empty?: string;
}) {
	const ready = rows.some(
		(row) => row.accent.value != null || row.grey.value != null,
	);
	return (
		<ChartShell
			large
			title={title}
			ariaLabel={ariaLabel}
			headers={["Check", "Model-chosen", "Fixed order"]}
			rows={rows.map((row) => [
				row.label,
				pct(row.accent.value),
				pct(row.grey.value),
			])}
			empty={ready ? undefined : empty}
			height={150}
		>
			{rows.map((row, index) => (
				<g key={row.label}>
					<text x="4" y={28 + index * 56} fill="#334155" fontSize="11">
						{row.label}
					</text>
					<rect
						x="8"
						y={34 + index * 56}
						width={(row.accent.value ?? 0) * 180}
						height="10"
						fill={ACCENT}
					/>
					<rect
						x="8"
						y={50 + index * 56}
						width={(row.grey.value ?? 0) * 180}
						height="10"
						fill={GREY}
					/>
					<title>
						{row.label}: model-chosen {pct(row.accent.value)}, fixed order{" "}
						{pct(row.grey.value)}
					</title>
				</g>
			))}
		</ChartShell>
	);
}

export function Grid2x2({
	title,
	ariaLabel,
	cells,
}: {
	title: string;
	ariaLabel: string;
	cells: { label: string; value: number; tone?: "good" | "bad" | "grey" }[];
}) {
	const fill = { good: GOOD, bad: BAD, grey: GREY };
	return (
		<ChartShell
			title={title}
			ariaLabel={ariaLabel}
			headers={["Result", "Games"]}
			rows={cells.map((cell) => [cell.label, String(cell.value)])}
			height={140}
		>
			{cells.slice(0, 4).map((cell, index) => {
				const x = 16 + (index % 2) * 150;
				const y = 16 + Math.floor(index / 2) * 60;
				return (
					<g key={cell.label}>
						<text
							x={x}
							y={y + 28}
							fill={fill[cell.tone ?? "grey"]}
							fontSize="22"
							fontWeight="700"
						>
							{cell.value}
						</text>
						<text x={x} y={y + 46} fill="#334155" fontSize="11">
							{cell.label}
						</text>
					</g>
				);
			})}
		</ChartShell>
	);
}

export function DotStrip({
	title,
	ariaLabel,
	rows,
	empty = "Appears after the first fair test.",
}: {
	title: string;
	ariaLabel: string;
	rows: { label: string; points: number[] }[];
	empty?: string;
}) {
	const shown = rows.slice(0, 10);
	const extra = rows.length - shown.length;
	return (
		<ChartShell
			title={title}
			ariaLabel={ariaLabel}
			headers={["Game", "Results"]}
			rows={rows.map((row) => [row.label, row.points.join(" ")])}
			empty={rows.length ? undefined : empty}
			height={Math.max(120, shown.length * 22 + (extra > 0 ? 36 : 16))}
		>
			{shown.map((row, index) => (
				<g key={row.label}>
					<text x="4" y={18 + index * 22} fill="#334155" fontSize="11">
						{row.label}
					</text>
					{row.points.map((point, position) => (
						<circle
							// Results are a fixed, ordered list; the same result can repeat.
							// biome-ignore lint/suspicious/noArrayIndexKey: position is the identity
							key={position}
							cx={150 + position * 12}
							cy={14 + index * 22}
							r="4"
							fill={point ? GOOD : GREY}
						>
							<title>
								{row.label}: {point ? "could do it alone" : "still needed help"}
							</title>
						</circle>
					))}
				</g>
			))}
			{extra > 0 && (
				<text x="4" y={18 + shown.length * 22} fill={GREY} fontSize="11">
					+{extra} more
				</text>
			)}
		</ChartShell>
	);
}

export function WeeklyBars({
	weeks,
	empty = "Appears after the first finished game.",
}: {
	weeks: { label: string; alone: number; still: number; right: number }[];
	empty?: string;
}) {
	const max = Math.max(
		...weeks.map((week) => week.alone + week.still + week.right),
		1,
	);
	return (
		<ChartShell
			large
			title="Games over time"
			ariaLabel="Finished games each week: alone after help, still needed help, or right first time."
			headers={[
				"Week",
				"Alone after help",
				"Still needed help",
				"Right first time",
			]}
			rows={weeks.map((week) => [
				week.label,
				String(week.alone),
				String(week.still),
				String(week.right),
			])}
			empty={weeks.length ? undefined : empty}
		>
			{weeks.map((week, index) => {
				const x = 28 + index * (270 / Math.max(weeks.length, 1));
				const width = Math.max(12, 240 / Math.max(weeks.length, 1) - 8);
				const scale = 120 / max;
				const rightH = week.right * scale;
				const stillH = week.still * scale;
				const aloneH = week.alone * scale;
				let y = 140;
				const bands = [
					{ h: rightH, fill: GREY, name: "right first time" },
					{ h: stillH, fill: BAD, name: "still needed help" },
					{ h: aloneH, fill: GOOD, name: "could do it alone" },
				];
				return (
					<g key={week.label}>
						{bands.map((band) => {
							y -= band.h;
							return (
								<rect
									key={band.name}
									x={x}
									y={y}
									width={width}
									height={band.h}
									fill={band.fill}
								>
									<title>
										{week.label}: {band.name}{" "}
										{band.h ? Math.round(band.h / scale) : 0}
									</title>
								</rect>
							);
						})}
						{tickIndexes(weeks.length).includes(index) && (
							<text x={x} y="162" fill={GREY} fontSize="11">
								{week.label}
							</text>
						)}
					</g>
				);
			})}
		</ChartShell>
	);
}

export function ReliabilityPlot({
	bins,
}: {
	bins: {
		from: number;
		to: number;
		count: number;
		confidence: number;
		agreement: number;
	}[];
}) {
	if (bins.length < 1) return null;
	return (
		<ChartShell
			title="Does confidence match later answers?"
			ariaLabel="Stated confidence against how often the reason was confirmed later."
			headers={["Confidence", "Confirmed later", "Games"]}
			rows={bins.map((bin) => [
				pct(bin.confidence),
				pct(bin.agreement),
				String(bin.count),
			])}
		>
			<line
				x1="28"
				y1="150"
				x2="300"
				y2="16"
				stroke={GREY}
				strokeDasharray="4 3"
			/>
			{bins.map((bin) => (
				<circle
					key={`${bin.from}-${bin.to}`}
					cx={28 + bin.confidence * 272}
					cy={150 - bin.agreement * 134}
					r="5"
					fill={ACCENT}
				>
					<title>
						{pct(bin.confidence)} confidence, confirmed {pct(bin.agreement)},{" "}
						{bin.count} games
					</title>
				</circle>
			))}
		</ChartShell>
	);
}
