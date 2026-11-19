import { useEffect, useState } from "react";
import { AddButtons, FilmTrack } from "./MovieMayhem";
import { AnalogClock, Art } from "./studioParts";
import {
	addPiece,
	durationText,
	filmMinutes,
	fromMinutes,
	type Piece,
} from "./studioRules";
import { studioSounds } from "./studioSounds";

const STEP_MS = 900;
/** The example: 07:00 to 08:10 — seven 10-minute strips, six of them snap into an hour reel. */
const SCRIPT: Array<Piece | "look" | "film" | "done"> = [
	"look",
	10,
	10,
	10,
	10,
	10,
	10,
	10,
	"film",
	"done",
];

/** Remembered on this phone, so the demo plays once by itself (the ? button replays it). */
const SEEN_KEY = "mindbridge.movie-studio-demo-seen";

export function demoSeen(): boolean {
	try {
		return localStorage.getItem(SEEN_KEY) === "1";
	} catch {
		return false;
	}
}

function markSeen() {
	try {
		localStorage.setItem(SEEN_KEY, "1");
	} catch {
		// Private mode: the demo will simply play again next time.
	}
}

/**
 * How to play, shown once: Nimo films an example scene. A pointing hand taps the film buttons, the
 * strips snap into an hour reel at 60 minutes, and the scene is filmed. Nothing here is scored.
 */
export function StudioDemo({
	reducedMotion,
	onDone,
}: {
	reducedMotion: boolean;
	onDone(): void;
}) {
	const [step, setStep] = useState(reducedMotion ? SCRIPT.length - 1 : 0);
	const [pieces, setPieces] = useState<Piece[]>(() =>
		reducedMotion ? [60, 10] : [],
	);
	const [flash, setFlash] = useState<string | null>(null);
	const action = SCRIPT[step];

	useEffect(() => {
		if (action === "done") return;
		const timer = setTimeout(
			() => {
				const next = SCRIPT[step + 1];
				if (typeof next === "number") {
					studioSounds.play("reel");
					const result = addPiece(pieces, next);
					setFlash(result.merged ? "මිනිත්තු 60 = පැය 1!" : null);
					if (result.merged) studioSounds.play("swap", { delay: 0.2 });
					setPieces(result.pieces);
				}
				if (next === "film") studioSounds.play("clap");
				if (next === "done") studioSounds.play("sparkle");
				setStep(step + 1);
			},
			step === 0 ? STEP_MS * 2 : STEP_MS,
		);
		return () => clearTimeout(timer);
	}, [step, action, pieces]);

	const finish = () => {
		markSeen();
		studioSounds.play("tap");
		onDone();
	};
	const building = typeof action === "number";
	const message =
		action === "look"
			? "① ඔරලෝසු දෙක බලමු: 07:00 සිට 08:10 වෙනකම්."
			: building
				? "② ෆිල්ම් කෑලි දාලා දර්ශනයේ දිග හදමු."
				: action === "film"
					? "③ රූගත කරමු!"
					: `නියමයි! දර්ශනය ${durationText(fromMinutes(filmMinutes(pieces)))}යි.`;

	return (
		<div className="studio-demo" data-step={String(action)}>
			<p className="studio-scroll" role="status">
				{message}
			</p>
			<Art
				art={action === "done" ? "nimoCheer" : "nimoDirector"}
				className="movie-nimo"
			/>
			<div className="scene-card">
				<span className="scene-ribbon">ආදර්ශ දර්ශනය</span>
				<div className="scene-top">
					<span className="scene-frame" aria-hidden="true">
						🦖
					</span>
					<span
						className="scene-clock"
						data-cue={action === "look" || undefined}
					>
						<small>පටන් ගත්තේ</small>
						<AnalogClock hour={7} minute={0} label="පටන් ගත්තේ 07:00" />
						<strong className="scene-reading">07:00</strong>
					</span>
					<span className="scene-arrow">➜</span>
					<span
						className="scene-clock"
						data-cue={action === "look" || undefined}
					>
						<small>අවසන් වුණේ</small>
						<AnalogClock hour={8} minute={10} label="අවසන් වුණේ 08:10" />
						<strong className="scene-reading">08:10</strong>
					</span>
				</div>
				<FilmTrack
					pieces={pieces}
					start={{ hours: 7, minutes: 0 }}
					flash={flash}
				/>
				<div className="film-controls">
					<AddButtons
						disabled
						cue={building || action === "look" ? 10 : null}
						onAdd={() => undefined}
					/>
				</div>
			</div>
			<span className="demo-film" data-cue={action === "film" || undefined}>
				🎬 රූගත කරමු!
			</span>
			<div className="demo-actions">
				{action === "done" ? (
					<button type="button" className="game-action" onClick={finish}>
						දැන් ඔබේ වාරය!
					</button>
				) : (
					<button type="button" className="demo-skip" onClick={finish}>
						මම දන්නවා ➜
					</button>
				)}
			</div>
		</div>
	);
}
