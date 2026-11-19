import { useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { ICONS } from "./studioArt";
import { AnalogClock, Art, Icon } from "./studioParts";
import {
	addPiece,
	type Clock,
	clockText,
	conversionResponse,
	durationResponse,
	durationText,
	filmMinutes,
	fromMinutes,
	layFilm,
	type Piece,
	pad,
	periodText,
	type StudioTask,
	snipHour,
	snipTen,
	sortFilm,
} from "./studioRules";
import { studioSounds } from "./studioSounds";

const PIECE_NAMES: Record<Piece, string> = {
	60: "පැය 1",
	10: "මිනිත්තු 10",
	5: "මිනිත්තු 5",
};

/** One piece of film: an hour is a round reel, minutes are strips (longer for 10, shorter for 5). */
export function FilmPiece({
	piece,
	onTap,
	label,
	bare = false,
}: {
	piece: Piece;
	onTap?(): void;
	label?: string;
	/** Small pieces in the cut pile carry no label. */
	bare?: boolean;
}) {
	const body = (
		<>
			<span className="film-piece-art" aria-hidden="true" />
			{!bare && (
				<span className="film-piece-text">
					{piece === 60 ? "පැය 1" : piece}
				</span>
			)}
		</>
	);
	return onTap ? (
		<button
			type="button"
			className="film-piece"
			data-minutes={piece}
			aria-label={label}
			onClick={onTap}
		>
			{body}
		</button>
	) : (
		<span className="film-piece" data-minutes={piece}>
			{body}
		</span>
	);
}

/** The film track: it starts at the scene's start clock (if any) and the pieces lie along it. */
export function FilmTrack({
	pieces,
	start,
	flash,
	onPieceTap,
}: {
	pieces: readonly Piece[];
	start?: Clock;
	flash?: string | null;
	onPieceTap?(at: number): void;
}) {
	return (
		<div className="film-track" data-flash={flash ? "" : undefined}>
			{start && <span className="film-start">▶ {clockText(start)}</span>}
			<div className="film-pieces">
				{pieces.length === 0 && (
					<span className="film-empty">ෆිල්ම් කෑලි මෙතනට එනවා</span>
				)}
				{pieces.map((piece, at) => (
					<FilmPiece
						// biome-ignore lint/suspicious/noArrayIndexKey: the piece order is the identity.
						key={at}
						piece={piece}
						label={onPieceTap ? `${PIECE_NAMES[piece]} කපා ඉවත් කරන්න` : undefined}
						onTap={onPieceTap ? () => onPieceTap(at) : undefined}
					/>
				))}
			</div>
			{flash && <span className="film-flash">{flash}</span>}
		</div>
	);
}

/** The three big "add film" buttons. */
export function AddButtons({
	disabled = false,
	onAdd,
}: {
	disabled?: boolean;
	onAdd(piece: Piece): void;
}) {
	return (
		<div className="film-add-row">
			{([60, 10, 5] as const).map((piece) => (
				<button
					type="button"
					key={piece}
					className="film-add"
					data-minutes={piece}
					disabled={disabled}
					aria-label={`${PIECE_NAMES[piece]} ෆිල්ම් එක දාන්න`}
					onClick={() => onAdd(piece)}
				>
					<span className="film-piece" data-minutes={piece} aria-hidden="true">
						<span className="film-piece-art" />
					</span>
					+ {PIECE_NAMES[piece]}
				</button>
			))}
		</div>
	);
}

/** A small picture clock with its digital time underneath. */
function ClockCard({ label, clock }: { label: string; clock: Clock }) {
	return (
		<span className="scene-clock">
			<small>{label}</small>
			<AnalogClock
				hour={clock.hours % 12 || 12}
				minute={clock.minutes}
				label={`${label} ${clockText(clock)}`}
			/>
			<strong className="scene-reading">{clockText(clock)}</strong>
		</span>
	);
}

type Film = {
	pieces: Piece[];
	cut: Piece[];
	merged: boolean;
	snipped: boolean;
};

/**
 * Movie Time Mayhem: one scene of Nimo's movie.
 * - How long did it take? The track starts at the start clock; the child lays hour reels and minute
 *   strips along it. Ten-minute strips snap into an hour reel when they reach 60 minutes.
 * - Two scenes together: the child lays both scenes' film; the strips snap into hours the same way.
 * - How much longer? The long scene's film is already laid; the child cuts the short scene's length
 *   off, snipping an hour reel into six 10-minute strips when the minutes run short.
 * - A call-sheet time: set the 24-hour clock.
 * Nothing is checked until the scene is filmed; then Nimo cheers, or scratches his head.
 */
export function MovieMayhem({
	task,
	prompt,
	scene,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: StudioTask;
	prompt: string;
	/** The picture of what this scene films. */
	scene: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const cutting = task.kind === "arith" && task.operation === "subtract";
	const [history, setHistory] = useState<Film[]>(() => [
		{
			pieces:
				cutting && task.kind === "arith"
					? layFilm(task.left.hours * 60 + task.left.minutes)
					: [],
			cut: [],
			merged: false,
			snipped: false,
		},
	]);
	const film = history.at(-1) as Film;
	const [flash, setFlash] = useState<string | null>(null);
	const [wheels, setWheels] = useState({
		hours: 0,
		minutes: 0,
		touched: false,
	});
	const playing = outcome === "playing";
	const push = (next: Film, message: string | null = null) => {
		setHistory([...history, next]);
		setFlash(message);
	};

	const add = (piece: Piece) => {
		evidence.note("move");
		studioSounds.play("reel");
		const { pieces, merged } = addPiece(film.pieces, piece);
		if (merged) studioSounds.play("swap", { delay: 0.2 });
		push(
			{ ...film, pieces, merged: film.merged || merged },
			merged ? "මිනිත්තු 60 = පැය 1!" : null,
		);
	};
	const cut = (at: number) => {
		if (!playing) return;
		evidence.note("digit", at);
		studioSounds.play("pick");
		const piece = film.pieces[at] as Piece;
		push({
			...film,
			pieces: film.pieces.filter((_, index) => index !== at),
			cut: sortFilm([...film.cut, piece]),
		});
	};
	const snip = (hour: boolean) => {
		evidence.note("carry");
		studioSounds.play("swap");
		push(
			{
				...film,
				pieces: hour ? snipHour(film.pieces) : snipTen(film.pieces),
				snipped: film.snipped || hour,
			},
			hour ? "පැය 1 = මිනිත්තු 60!" : "මිනිත්තු 10 = 5 + 5",
		);
	};
	const undo = () => {
		studioSounds.play("back");
		setHistory(history.length > 1 ? history.slice(0, -1) : history);
		setFlash(null);
	};

	const built = filmMinutes(film.pieces);
	const givenHours =
		task.kind === "arith" ? task.left.hours + task.right.hours : 0;
	const response: ConstructedResponse | null =
		task.kind === "convert"
			? wheels.touched
				? conversionResponse(wheels.hours, wheels.minutes)
				: null
			: task.kind === "elapsed"
				? film.pieces.length
					? durationResponse(task, built, false)
					: null
				: cutting
					? film.cut.length
						? durationResponse(task, built, film.snipped)
						: null
					: film.pieces.length
						? durationResponse(
								task,
								built,
								film.merged ||
									film.pieces.filter((piece) => piece === 60).length >
										givenHours,
							)
						: null;

	const nimo =
		outcome === "correct"
			? "nimoCheer"
			: outcome === "wrong"
				? "nimoThink"
				: "nimoDirector";
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
			<Art art={nimo} className="movie-nimo" />
			<div className="scene-card">
				<span className="scene-ribbon">
					<Icon src={ICONS.clapper} /> දර්ශනය
				</span>
				<div className="scene-top">
					<span className="scene-frame" aria-hidden="true">
						{scene}
					</span>
					{task.kind === "elapsed" && (
						<>
							<ClockCard label="පටන් ගත්තේ" clock={task.start} />
							<span className="scene-arrow">➜</span>
							<ClockCard label="අවසන් වුණේ" clock={task.end} />
						</>
					)}
					{task.kind === "arith" && (
						<>
							<span className="scene-length">
								<small>{cutting ? "දිගු දර්ශනය" : "දර්ශනය 1"}</small>
								<strong className="scene-reading">
									{durationText(task.left)}
								</strong>
							</span>
							<span className="scene-arrow">{cutting ? "−" : "+"}</span>
							<span className="scene-length">
								<small>{cutting ? "කෙටි දර්ශනය" : "දර්ශනය 2"}</small>
								<strong className="scene-reading">
									{durationText(task.right)}
								</strong>
							</span>
						</>
					)}
					{task.kind === "convert" && (
						<>
							<span className="scene-clock">
								<small>කැඳවීම් පත්‍රය</small>
								<AnalogClock
									hour={task.hour}
									minute={task.minute}
									label={periodText(task.hour, task.minute, task.period)}
								/>
								<strong className="scene-reading">
									{task.period === "am" ? "☀️" : "🌙"}{" "}
									{periodText(task.hour, task.minute, task.period)}
								</strong>
							</span>
							<span className="scene-arrow">➜</span>
							<span className="scene-clock">
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
						</>
					)}
				</div>
				{task.kind !== "convert" && (
					<>
						<FilmTrack
							pieces={film.pieces}
							start={task.kind === "elapsed" ? task.start : undefined}
							flash={flash}
							onPieceTap={cutting && playing ? cut : undefined}
						/>
						<div className="film-controls">
							{cutting ? (
								<>
									<span className="film-cut-pile">
										<small>✂️ කපා ඉවත් කළා</small>
										<span>
											{film.cut.map((piece, at) => (
												// biome-ignore lint/suspicious/noArrayIndexKey: cut pieces are interchangeable.
												<FilmPiece key={at} piece={piece} bare />
											))}
										</span>
										<strong>
											{durationText(fromMinutes(filmMinutes(film.cut)))}
										</strong>
									</span>
									<button
										type="button"
										className="film-snip"
										disabled={!playing || !film.pieces.includes(60)}
										onClick={() => snip(true)}
									>
										✂️ පැය 1 → මිනිත්තු 10 × 6
									</button>
									<button
										type="button"
										className="film-snip"
										disabled={!playing || !film.pieces.includes(10)}
										onClick={() => snip(false)}
									>
										✂️ 10 → 5 + 5
									</button>
								</>
							) : (
								<AddButtons disabled={!playing} onAdd={add} />
							)}
							<button
								type="button"
								className="film-remove"
								disabled={!playing || history.length < 2}
								aria-label="අන්තිම දේ අහෝසි කරන්න"
								onClick={undo}
							>
								↩
							</button>
						</div>
						<p className="film-readout">
							{cutting ? "ඉතිරි ෆිල්ම් එක" : "ඔබේ ෆිල්ම් එක"}:{" "}
							<strong>{durationText(fromMinutes(built))}</strong>
						</p>
					</>
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
