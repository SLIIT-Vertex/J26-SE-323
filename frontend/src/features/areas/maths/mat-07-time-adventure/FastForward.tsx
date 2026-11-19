import { type CSSProperties, useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { ICONS } from "./studioArt";
import { AnalogClock, Art, Icon } from "./studioParts";
import {
	clockText,
	durationAnswer,
	durationResponse,
	durationText,
	fromMinutes,
	type StudioTask,
	toMinutes,
} from "./studioRules";
import { hourChime, studioSounds } from "./studioSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const STEPS = [
	{ minutes: -60, label: "පැය 1", icon: ICONS.rewind },
	{ minutes: -5, label: "මි. 5", icon: ICONS.rewind },
	{ minutes: 5, label: "මි. 5", icon: ICONS.forward },
	{ minutes: 60, label: "පැය 1", icon: ICONS.forward },
] as const;

/**
 * Fast Forward & Rewind: the editing room's magic film reel moves the movie's time in 5-minute and
 * 1-hour steps. Every time the minutes pass 59, the clock rolls to the next hour (60 minutes are
 * 1 hour) with a chime; rewinding past 00 breaks an hour back into 60 minutes. A little sapling
 * grows into a tree as the film runs forward.
 */
export function FastForward({
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
	const elapsed = task.kind === "elapsed";
	const base =
		task.kind === "elapsed"
			? toMinutes(task.start)
			: task.kind === "arith"
				? toMinutes(task.left)
				: 0;
	const answer = durationAnswer(task);
	const target =
		task.kind === "elapsed"
			? toMinutes(answer ?? { hours: 0, minutes: 0 })
			: task.kind === "arith"
				? (task.operation === "add" ? 1 : -1) * toMinutes(task.right)
				: 0;
	const [delta, setDelta] = useState(demo ? target : 0);
	const [crossed, setCrossed] = useState(demo);
	const [flash, setFlash] = useState<"up" | "down" | null>(null);
	const value = base + delta;

	useEffect(() => {
		if (demo || delta === 0) {
			onResponse(null);
			return;
		}
		onResponse(durationResponse(task, elapsed ? delta : value, crossed));
	}, [demo, delta, value, crossed, elapsed, task, onResponse]);

	const step = (minutes: number) => {
		if (demo) return;
		const next = delta + minutes;
		if (base + next < 0 || (elapsed && next < 0)) {
			studioSounds.play("boing");
			return;
		}
		evidence.note("move");
		studioSounds.play(minutes > 0 ? "forward" : "rewind", { volume: 0.6 });
		studioSounds.play("tick", { delay: 0.1 });
		// The hour changes when the minutes roll past 59 (or back past 00) in a 5-minute step.
		const hourChanged =
			Math.abs(minutes) < 60 &&
			Math.floor((base + next) / 60) !== Math.floor(value / 60);
		if (hourChanged) {
			hourChime();
			setCrossed(true);
			setFlash(minutes > 0 ? "up" : "down");
		} else setFlash(null);
		setDelta(next);
	};

	const growth = Math.min(1, Math.abs(delta) / 120);
	const clock = fromMinutes(((value % 1440) + 1440) % 1440);
	const range = Math.max(Math.abs(target) * 1.4, 60);
	const spot = (minutes: number) =>
		`${Math.min(100, Math.max(0, (Math.abs(minutes) / range) * 100))}%`;
	const message = demo
		? "චිත්‍රපටය ඉස්සරහට යනකොට මිනිත්තු 60ක් පැය 1ක් වෙනවා."
		: flash === "up"
			? "මිනිත්තු 60 = පැය 1! ඔරලෝසුව ඊළඟ පැයට ගියා."
			: flash === "down"
				? "පැය 1 = මිනිත්තු 60! පැයක් මිනිත්තු 60කට කැඩුවා."
				: task.kind === "elapsed"
					? `${clockText(task.start)} සිට ${clockText(task.end)} වෙනකම් ඉස්සරහට යමු!`
					: task.kind === "arith" && task.operation === "add"
						? `${durationText(task.right)}ක් ඉස්සරහට යමු!`
						: task.kind === "arith"
							? `${durationText(task.right)}ක් ආපස්සට යමු!`
							: "";

	return (
		<div
			className="fast-forward"
			data-demo={demo || undefined}
			data-flash={flash ?? undefined}
		>
			<p className="studio-message" role="status">
				{message}
			</p>
			<div className="ff-screen">
				{elapsed ? (
					<>
						<AnalogClock
							hour={clock.hours % 12 || 12}
							minute={clock.minutes}
							label={`චිත්‍රපටයේ වෙලාව ${clockText(clock)}`}
						/>
						<span className="ff-digital">
							<small>චිත්‍රපටයේ වෙලාව</small>
							<strong>{clockText(clock)}</strong>
						</span>
					</>
				) : (
					<span className="ff-digital">
						<small>දර්ශනයේ දිග</small>
						<strong>{durationText(fromMinutes(value))}</strong>
					</span>
				)}
				<span className="ff-moved">
					<small>{delta >= 0 ? "ඉස්සරහට ගියේ" : "ආපස්සට ගියේ"}</small>
					<strong>{durationText(fromMinutes(Math.abs(delta)))}</strong>
				</span>
				<span
					className="ff-tree"
					aria-hidden="true"
					style={{ "--grow": growth } as CSSProperties}
				>
					<Art
						art={growth >= 0.5 ? "tree" : "sapling"}
						className="ff-tree-art"
					/>
				</span>
			</div>
			<div className="ff-track" aria-hidden="true">
				<span className="ff-reel" />
				<span className="ff-pawn" style={{ left: spot(delta) }}>
					<Art art="pawnBlue" />
				</span>
				{(hint || demo) && (
					<span className="ff-pawn ff-target" style={{ left: spot(target) }}>
						<Art art="pawnRed" />
					</span>
				)}
			</div>
			<div className="ff-buttons">
				{STEPS.map((button) => (
					<button
						type="button"
						key={button.minutes}
						className="ff-step"
						data-direction={button.minutes > 0 ? "forward" : "rewind"}
						disabled={demo}
						aria-label={`${button.label} ${button.minutes > 0 ? "ඉස්සරහට" : "ආපස්සට"}`}
						onClick={() => step(button.minutes)}
					>
						<Icon src={button.icon} />
						{button.label}
					</button>
				))}
				{!demo && (
					<button
						type="button"
						className="ff-again"
						aria-label="මුල ඉඳන්"
						disabled={delta === 0}
						onClick={() => {
							studioSounds.play("back");
							setDelta(0);
							setCrossed(false);
							setFlash(null);
						}}
					>
						<Icon src={ICONS.again} />
					</button>
				)}
			</div>
		</div>
	);
}
