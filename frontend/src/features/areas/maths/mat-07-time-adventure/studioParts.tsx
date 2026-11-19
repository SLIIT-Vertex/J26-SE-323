import type { CSSProperties, PointerEvent } from "react";
import {
	ACTOR_FRAMES,
	type Actor,
	actorStrip,
	type StudioArtKey,
	studioArtReady,
	studioArtUrl,
} from "./studioArt";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: StudioArtKey;
	className?: string;
}) {
	return studioArtReady(art) ? (
		<img className={className} src={studioArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} studio-shape`} data-art={art} />
	);
}

/** A white icon tinted to the current text colour. */
export function Icon({ src, className }: { src: string; className?: string }) {
	return (
		<span
			className={`studio-icon ${className ?? ""}`}
			aria-hidden="true"
			style={{ maskImage: `url("${src}")`, WebkitMaskImage: `url("${src}")` }}
		/>
	);
}

export type ActorMove = "idle" | "walk" | "cheer" | "jump" | "slip";

/** One movie actor (a sprite strip of nine frames); the move picks which frames play. */
export function ActorSprite({
	actor,
	move,
	className,
}: {
	actor: Actor;
	move: ActorMove;
	className?: string;
}) {
	const frame =
		move === "jump"
			? ACTOR_FRAMES.indexOf("jump")
			: move === "slip"
				? ACTOR_FRAMES.indexOf("fallDown")
				: 0;
	return (
		<span
			className={`studio-actor ${className ?? ""}`}
			data-move={move}
			aria-hidden="true"
			style={
				{
					backgroundImage: `url("${actorStrip(actor)}")`,
					"--frame": frame,
				} as CSSProperties
			}
		/>
	);
}

const point = (minuteOrHour: number, of: number, radius: number) => {
	const angle = ((minuteOrHour / of) * 360 - 90) * (Math.PI / 180);
	return {
		x: 200 + radius * Math.cos(angle),
		y: 200 + radius * Math.sin(angle),
	};
};

/**
 * An analogue clock face. With `onDrag`, the child drags either hand: the minute hand snaps to five
 * minutes, the hour hand to whole hours.
 */
export function AnalogClock({
	hour,
	minute,
	ghost,
	label,
	onDrag,
}: {
	hour: number;
	minute: number;
	ghost?: { hour: number; minute: number };
	label: string;
	onDrag?(hand: "hour" | "minute", value: number): void;
}) {
	const hourTurn = (hour % 12) + minute / 60;
	const hourTip = point(hourTurn, 12, 105);
	const minuteTip = point(minute, 60, 160);
	const drag =
		(hand: "hour" | "minute") => (event: PointerEvent<SVGElement>) => {
			if (!onDrag) return;
			const svg = (event.currentTarget as SVGElement).ownerSVGElement;
			if (!svg) return;
			const move = (clientX: number, clientY: number) => {
				const box = svg.getBoundingClientRect();
				const x = ((clientX - box.left) / box.width) * 400 - 200;
				const y = ((clientY - box.top) / box.height) * 400 - 200;
				const turn = ((Math.atan2(y, x) * 180) / Math.PI + 90 + 360) % 360;
				if (hand === "minute")
					onDrag("minute", (Math.round(turn / 30) * 5) % 60);
				else onDrag("hour", Math.round(turn / 30) % 12 || 12);
			};
			const onMove = (moveEvent: globalThis.PointerEvent) =>
				move(moveEvent.clientX, moveEvent.clientY);
			const onUp = () => {
				window.removeEventListener("pointermove", onMove);
				window.removeEventListener("pointerup", onUp);
			};
			window.addEventListener("pointermove", onMove);
			window.addEventListener("pointerup", onUp);
			event.preventDefault();
		};
	return (
		<svg
			className="studio-clock"
			viewBox="0 0 400 400"
			role="img"
			aria-label={label}
		>
			<circle cx="200" cy="200" r="190" className="studio-clock-rim" />
			<circle cx="200" cy="200" r="172" className="studio-clock-face" />
			{Array.from({ length: 60 }, (_, mark) => {
				const outer = point(mark, 60, 168);
				const inner = point(mark, 60, mark % 5 === 0 ? 150 : 160);
				return (
					<line
						// biome-ignore lint/suspicious/noArrayIndexKey: the minute mark is the identity.
						key={mark}
						x1={inner.x}
						y1={inner.y}
						x2={outer.x}
						y2={outer.y}
						className={
							mark % 5 === 0 ? "studio-clock-five" : "studio-clock-one"
						}
					/>
				);
			})}
			{Array.from({ length: 12 }, (_, at) => {
				const spot = point(at + 1, 12, 125);
				return (
					<text
						// biome-ignore lint/suspicious/noArrayIndexKey: the hour number is the identity.
						key={at}
						x={spot.x}
						y={spot.y}
						className="studio-clock-number"
						textAnchor="middle"
						dominantBaseline="central"
					>
						{at + 1}
					</text>
				);
			})}
			{ghost && (
				<g className="studio-clock-ghost">
					<line
						x1="200"
						y1="200"
						{...tipOf(point((ghost.hour % 12) + ghost.minute / 60, 12, 105))}
					/>
					<line x1="200" y1="200" {...tipOf(point(ghost.minute, 60, 160))} />
				</g>
			)}
			<line
				x1="200"
				y1="200"
				x2={hourTip.x}
				y2={hourTip.y}
				className="studio-clock-hour"
			/>
			<line
				x1="200"
				y1="200"
				x2={minuteTip.x}
				y2={minuteTip.y}
				className="studio-clock-minute"
			/>
			{onDrag && (
				<>
					<circle
						cx={hourTip.x}
						cy={hourTip.y}
						r="34"
						className="studio-clock-grip"
						data-hand="hour"
						onPointerDown={drag("hour")}
					/>
					<circle
						cx={minuteTip.x}
						cy={minuteTip.y}
						r="34"
						className="studio-clock-grip"
						data-hand="minute"
						onPointerDown={drag("minute")}
					/>
				</>
			)}
			<circle cx="200" cy="200" r="12" className="studio-clock-pin" />
		</svg>
	);
}

const tipOf = (spot: { x: number; y: number }) => ({ x2: spot.x, y2: spot.y });
