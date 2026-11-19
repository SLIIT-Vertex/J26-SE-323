import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { AnalogClock, Art } from "./studioParts";
import {
	clockResponse,
	conversionResponse,
	pad,
	periodText,
	type StudioTask,
	to24,
	unitsResponse,
	unitText,
} from "./studioRules";
import { studioSounds } from "./studioSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

/**
 * The Tick-Tock Puppet Show (the most visible help). A big clock runs the puppet stage: the child
 * drags the hands (or taps the buttons) to set a time, and for 24-hour time picks morning or
 * afternoon — the sun or the moon puppet comes out and the board shows the 24-hour time. Unit
 * cards ("60 minutes" ↔ "1 hour") are matched by tapping one puppet card, then its partner.
 */
export function PuppetShow({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	task: StudioTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	if (task.kind === "units")
		return (
			<UnitPuppets
				task={task}
				demo={demo}
				hint={hint}
				evidence={evidence}
				onResponse={onResponse}
			/>
		);
	return (
		<ClockStage
			task={task}
			demo={demo}
			hint={hint}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}

function ClockStage({
	task,
	demo,
	hint,
	evidence,
	onResponse,
}: {
	task: StudioTask;
	demo: boolean;
	hint: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const target =
		task.kind === "convert"
			? { hour: task.hour, minute: task.minute, period: task.period }
			: task.kind === "clock"
				? { hour: task.hour, minute: task.minute, period: null }
				: { hour: 12, minute: 0, period: null };
	const converting = task.kind === "convert";
	const [hour, setHour] = useState(demo ? target.hour : 12);
	const [minute, setMinute] = useState(demo ? target.minute : 0);
	const [period, setPeriod] = useState<"am" | "pm" | null>(
		demo ? target.period : null,
	);
	const [touched, setTouched] = useState(false);
	const hour24 = period ? to24(hour, period) : null;
	const matched =
		hour === target.hour &&
		minute === target.minute &&
		(!converting || period === target.period);

	useEffect(() => {
		if (demo || !touched) {
			onResponse(null);
			return;
		}
		if (converting)
			onResponse(hour24 === null ? null : conversionResponse(hour24, minute));
		else onResponse(clockResponse(hour, minute));
	}, [demo, touched, converting, hour, minute, hour24, onResponse]);

	const set = (next: {
		hour?: number;
		minute?: number;
		period?: "am" | "pm";
	}) => {
		if (demo) return;
		evidence.note("move");
		studioSounds.play(next.period ? "pick" : "tick");
		if (next.hour !== undefined) setHour(next.hour);
		if (next.minute !== undefined) setMinute(next.minute);
		if (next.period) setPeriod(next.period);
		setTouched(true);
	};
	const night =
		period === "pm"
			? hour24 !== null && (hour24 >= 18 || hour24 < 6)
			: period === "am" && (hour === 12 || hour < 6);
	const message = demo
		? converting
			? `${periodText(target.hour, target.minute, target.period ?? "pm")} = ${pad(to24(target.hour, target.period ?? "pm"))}:${pad(target.minute)}`
			: `ඔරලෝසුව ${target.hour}:${pad(target.minute)}ට හැරෙව්වා.`
		: matched && touched
			? "නියමයි! රූකඩ සන්දර්ශනය පටන් ගත්තා!"
			: converting
				? `ඔරලෝසුවේ කටු ${periodText(target.hour, target.minute, target.period ?? "pm")}ට හරවමු!`
				: `ඔරලෝසුවේ කටු ${target.hour}:${pad(target.minute)}ට හරවමු!`;

	return (
		<div
			className="puppet-show"
			data-night={night || undefined}
			data-cheer={(matched && touched) || demo || undefined}
		>
			<p className="studio-message" role="status">
				{message}
			</p>
			<div className="puppet-stage">
				<Art art={night ? "moonPuppet" : "sunPuppet"} className="puppet-sky" />
				<Art art="cloud1" className="puppet-cloud puppet-cloud-1" />
				<Art art="cloud3" className="puppet-cloud puppet-cloud-2" />
				<AnalogClock
					hour={hour}
					minute={minute}
					label={`ඔරලෝසුව ${hour}:${pad(minute)}`}
					ghost={
						hint && !demo
							? { hour: target.hour, minute: target.minute }
							: undefined
					}
					onDrag={
						demo
							? undefined
							: (hand, value) =>
									set(hand === "hour" ? { hour: value } : { minute: value })
					}
				/>
				<div className="puppet-board">
					<strong className="puppet-reading">
						{converting ? (hour24 === null ? "--" : pad(hour24)) : pad(hour)}:
						{pad(minute)}
					</strong>
					{converting && (
						<div className="puppet-periods">
							{(["am", "pm"] as const).map((choice) => (
								<button
									type="button"
									key={choice}
									className="puppet-period"
									aria-pressed={period === choice}
									data-ghost={
										(hint &&
											!demo &&
											choice === target.period &&
											period !== choice) ||
										undefined
									}
									disabled={demo}
									onClick={() => set({ period: choice })}
								>
									{choice === "am" ? "☀️ පෙ.ව. (උදේ)" : "🌙 ප.ව. (දවල්/රෑ)"}
								</button>
							))}
						</div>
					)}
				</div>
			</div>
			{!demo && (
				<div className="puppet-buttons">
					<button
						type="button"
						onClick={() => set({ hour: (hour % 12) + 1 })}
						aria-label="පැය කටුව ඉස්සරහට"
					>
						පැය +1
					</button>
					<button
						type="button"
						onClick={() => set({ minute: (minute + 5) % 60 })}
						aria-label="මිනිත්තු කටුව ඉස්සරහට"
					>
						මිනිත්තු +5
					</button>
					<button
						type="button"
						onClick={() => set({ minute: (minute + 55) % 60 })}
						aria-label="මිනිත්තු කටුව ආපස්සට"
					>
						මිනිත්තු −5
					</button>
				</div>
			)}
		</div>
	);
}

/** The bigger unit each pair makes: "60 minutes" makes 1 hour, "365 days" an ordinary year. */
export function partnerUnit([count, unit]: [number, string]): string {
	const partners: Record<string, string> = {
		"60:seconds": "minutes",
		"60:minutes": "hours",
		"24:hours": "days",
		"7:days": "weeks",
		"4:weeks": "months",
		"12:months": "years",
		"365:days": "ordinary_years",
		"366:days": "leap_years",
	};
	return partners[`${count}:${unit}`] ?? "";
}

function UnitPuppets({
	task,
	demo,
	hint,
	evidence,
	onResponse,
}: {
	task: Extract<StudioTask, { kind: "units" }>;
	demo: boolean;
	hint: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const answer = task.left.map((pair) =>
		task.right.findIndex(([, unit]) => unit === partnerUnit(pair)),
	);
	const [matches, setMatches] = useState<Array<number | null>>(() =>
		demo ? answer : task.left.map(() => null),
	);
	const [picked, setPicked] = useState<number | null>(null);
	const complete = matches.every((match) => match !== null);

	useEffect(() => {
		onResponse(demo || !complete ? null : unitsResponse(matches as number[]));
	}, [demo, complete, matches, onResponse]);

	const pickLeft = (row: number) => {
		if (demo) return;
		studioSounds.play("pick");
		setPicked(row);
	};
	const pickRight = (column: number) => {
		if (demo || picked === null) return;
		evidence.note("move");
		studioSounds.play("tick");
		setMatches(
			matches.map((match, row) =>
				row === picked ? column : match === column ? null : match,
			),
		);
		setPicked(null);
	};

	return (
		<div
			className="puppet-show puppet-units"
			data-cheer={complete || undefined}
		>
			<p className="studio-message" role="status">
				{complete
					? "හැම කාඩ් එකටම යාළුවා හම්බුණා!"
					: "එක රූකඩ කාඩ් එකක් තෝරලා, ඒකට සමාන කාඩ් එක තෝරමු!"}
			</p>
			<div className="unit-columns">
				<div className="unit-column">
					{task.left.map((pair, row) => (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: the row order is the identity.
							key={row}
							className="unit-card"
							aria-pressed={picked === row}
							data-matched={matches[row] !== null || undefined}
							disabled={demo}
							onClick={() => pickLeft(row)}
						>
							<Art art="sunPuppet" className="unit-puppet" />
							{unitText(pair)}
							{matches[row] !== null && (
								<small>
									= {unitText(task.right[matches[row] ?? 0] ?? [0, ""])}
								</small>
							)}
						</button>
					))}
				</div>
				<div className="unit-column">
					{task.right.map((pair, column) => (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: the card order is the identity.
							key={column}
							className="unit-card unit-card-right"
							data-ghost={
								(hint && picked !== null && answer[picked] === column) ||
								undefined
							}
							disabled={demo || picked === null}
							onClick={() => pickRight(column)}
						>
							<Art art="moonPuppet" className="unit-puppet" />
							{unitText(pair)}
						</button>
					))}
				</div>
			</div>
		</div>
	);
}
