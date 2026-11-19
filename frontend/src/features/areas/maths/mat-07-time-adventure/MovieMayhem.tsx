import { useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { type Actor, ICONS } from "./studioArt";
import { ActorSprite, Art, Icon } from "./studioParts";
import {
	clockText,
	conversionResponse,
	durationResponse,
	durationText,
	fromMinutes,
	pad,
	periodText,
	type StudioTask,
} from "./studioRules";
import { studioSounds } from "./studioSounds";

/** The filmstrip pieces: an hour reel and 10- and 5-minute strips. */
export const PIECES = [
	{ minutes: 60, label: "පැය 1 රීලය" },
	{ minutes: 10, label: "මිනිත්තු 10" },
	{ minutes: 5, label: "මිනිත්තු 5" },
] as const;

/**
 * The filmstrip builder: the child builds a scene's length from hour reels and minute strips. It
 * shows only the pieces and their hours and minutes (60 minutes are written as an hour), never
 * whether the length is right.
 */
export function FilmstripBuilder({
	pieces,
	disabled = false,
	onChange,
}: {
	pieces: readonly number[];
	disabled?: boolean;
	onChange(pieces: number[]): void;
}) {
	const total = pieces.reduce((sum, piece) => sum + piece, 0);
	return (
		<div className="filmstrip-builder">
			<div className="filmstrip" aria-live="polite">
				{pieces.length === 0 && (
					<span className="filmstrip-empty">ෆිල්ම් කෑලි දාමු</span>
				)}
				{pieces.map((piece, at) => (
					<span
						// biome-ignore lint/suspicious/noArrayIndexKey: the piece order is the identity.
						key={at}
						className="film-piece"
						data-minutes={piece}
					>
						{piece === 60 ? "1 h" : piece}
					</span>
				))}
			</div>
			<strong className="filmstrip-total">
				{durationText(fromMinutes(total))}
			</strong>
			<div className="filmstrip-buttons">
				{PIECES.map((piece) => (
					<button
						type="button"
						key={piece.minutes}
						className="film-add"
						data-minutes={piece.minutes}
						disabled={disabled}
						onClick={() => {
							studioSounds.play("reel");
							onChange([...pieces, piece.minutes]);
						}}
					>
						+ {piece.label}
					</button>
				))}
				<button
					type="button"
					className="film-remove"
					disabled={disabled || pieces.length === 0}
					aria-label="අන්තිම කෑල්ල අයින් කරන්න"
					onClick={() => {
						studioSounds.play("back");
						onChange(pieces.slice(0, -1));
					}}
				>
					↩
				</button>
			</div>
		</div>
	);
}

/** Hours and minutes wheels for a 24-hour clock (minutes in fives). */
export function ClockWheels({
	hours,
	minutes,
	disabled = false,
	onChange,
}: {
	hours: number;
	minutes: number;
	disabled?: boolean;
	onChange(hours: number, minutes: number): void;
}) {
	const turn = (part: "hours" | "minutes", step: 1 | -1) => {
		studioSounds.play("tick");
		if (part === "hours") onChange((hours + step + 24) % 24, minutes);
		else onChange(hours, (minutes + step * 5 + 60) % 60);
	};
	return (
		<div className="clock-wheels">
			{(["hours", "minutes"] as const).map((part, at) => (
				<div key={part} className="clock-wheel">
					<button
						type="button"
						disabled={disabled}
						aria-label={`${part === "hours" ? "පැය" : "මිනිත්තු"} වැඩි කරන්න`}
						onClick={() => turn(part, 1)}
					>
						▲
					</button>
					<strong>{pad(part === "hours" ? hours : minutes)}</strong>
					<button
						type="button"
						disabled={disabled}
						aria-label={`${part === "hours" ? "පැය" : "මිනිත්තු"} අඩු කරන්න`}
						onClick={() => turn(part, -1)}
					>
						▼
					</button>
					{at === 0 && <span className="clock-colon">:</span>}
				</div>
			))}
		</div>
	);
}

/**
 * Movie Time Mayhem: the scene card on the movie set. The child works out how long a scene took (or
 * a call-sheet time on the 24-hour clock, or two scenes' lengths together or apart), builds it, and
 * shouts "action". Only then do the actors perform: a happy scene, or a silly slip.
 */
export function MovieMayhem({
	task,
	prompt,
	actor,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: StudioTask;
	prompt: string;
	actor: Actor;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const [pieces, setPieces] = useState<number[]>([]);
	const [exchanged, setExchanged] = useState(false);
	const [wheels, setWheels] = useState({
		hours: 0,
		minutes: 0,
		touched: false,
	});
	const playing = outcome === "playing";
	const total = pieces.reduce((sum, piece) => sum + piece, 0);
	const response =
		task.kind === "convert"
			? wheels.touched
				? conversionResponse(wheels.hours, wheels.minutes)
				: null
			: pieces.length > 0
				? durationResponse(task, total, exchanged)
				: null;

	const instruction =
		outcome === "correct"
			? "නියමයි! දර්ශනය රූගත කළා!"
			: outcome === "wrong"
				? "අපොයි! වෙලාව ටිකක් පැටලුණා."
				: `${returning ? "අලුත් දර්ශනයක්! " : ""}${prompt}`;

	return (
		<div className="movie-mayhem" data-outcome={outcome}>
			<p className="studio-scroll" role="status">
				{instruction}
			</p>
			<Art art="street" className="movie-set" />
			<ActorSprite
				actor={actor}
				move={
					outcome === "correct"
						? "cheer"
						: outcome === "wrong"
							? "slip"
							: "idle"
				}
				className="movie-actor"
			/>
			<Art art="nimoDirector" className="movie-nimo" />
			<Art art="owl" className="movie-owl" />
			<div className="scene-card">
				<span className="scene-ribbon">
					<Icon src={ICONS.clapper} /> දර්ශනය
				</span>
				{task.kind === "elapsed" && (
					<div className="scene-times">
						<span className="scene-time">
							<small>පටන් ගත්තේ</small>
							<strong>{clockText(task.start)}</strong>
						</span>
						<span className="scene-arrow">➜</span>
						<span className="scene-time">
							<small>අවසන් වුණේ</small>
							<strong>{clockText(task.end)}</strong>
						</span>
						<span className="scene-arrow">➜</span>
						<span className="scene-time scene-ask">
							<small>ගත වූ කාලය</small>
							<strong>?</strong>
						</span>
					</div>
				)}
				{task.kind === "arith" && (
					<div className="scene-times">
						<span className="scene-time">
							<small>දර්ශනය 1</small>
							<strong>{durationText(task.left)}</strong>
						</span>
						<span className="scene-arrow">
							{task.operation === "add" ? "+" : "−"}
						</span>
						<span className="scene-time">
							<small>දර්ශනය 2</small>
							<strong>{durationText(task.right)}</strong>
						</span>
						<span className="scene-arrow">=</span>
						<span className="scene-time scene-ask">
							<small>{task.operation === "add" ? "එකට" : "වෙනස"}</small>
							<strong>?</strong>
						</span>
					</div>
				)}
				{task.kind === "convert" && (
					<div className="scene-times">
						<span className="scene-time">
							<small>කැඳවීම් පත්‍රය</small>
							<strong>{periodText(task.hour, task.minute, task.period)}</strong>
						</span>
						<span className="scene-arrow">➜</span>
						<span className="scene-time scene-ask">
							<small>පැය 24 ඔරලෝසුව</small>
							<ClockWheels
								hours={wheels.hours}
								minutes={wheels.minutes}
								disabled={!playing}
								onChange={(hours, minutes) => {
									evidence.note("digit", hours !== wheels.hours ? 0 : 1);
									setWheels({ hours, minutes, touched: true });
								}}
							/>
						</span>
					</div>
				)}
				{task.kind !== "convert" && (
					<FilmstripBuilder
						pieces={pieces}
						disabled={!playing}
						onChange={(next) => {
							evidence.note("move");
							setPieces(next);
						}}
					/>
				)}
				{task.kind === "arith" && (
					<button
						type="button"
						className="scene-exchange"
						aria-pressed={exchanged}
						disabled={!playing}
						onClick={() => {
							evidence.note("carry");
							studioSounds.play("swap");
							setExchanged(!exchanged);
						}}
					>
						⇄ මිනිත්තු 60 = පැය 1 හුවමාරුව කළා
					</button>
				)}
			</div>
			<button
				type="button"
				className="game-action scene-send"
				disabled={busy || !response || !playing}
				onClick={() => {
					if (!response) return;
					studioSounds.play("clap");
					onSubmit(response);
				}}
			>
				🎬 රූගත කරමු!
			</button>
		</div>
	);
}
