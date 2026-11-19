import { type CSSProperties, useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art, ScoreWheels } from "./carnivalParts";
import {
	type CarnivalTask,
	carnivalResponse,
	groupsOf,
	STORY_EMOJI,
	wheelCount,
} from "./carnivalRules";
import { carnivalSounds } from "./carnivalSounds";

const LAP_MS = 1100;
const BOOST_LAP_MS = 450;

/** The scoreboard words for a task: what one group is and what the groups are. */
export function scoreLabels(task: CarnivalTask): {
	each: string;
	count: string;
	icon: string;
} {
	if (task.kind !== "story" || task.asset === "lap")
		return { each: "ලකුණු / වටය", count: "වට ගණන", icon: "🏁" };
	if (task.asset === "balloon")
		return {
			each: "බැලූන් / පොකුර",
			count: "පොකුරු ගණන",
			icon: STORY_EMOJI.balloon,
		};
	if (task.asset === "medal")
		return { each: "පදක්කම් / පේළිය", count: "පේළි ගණන", icon: STORY_EMOJI.medal };
	return { each: "කොඩි / වැල", count: "වැල් ගණන", icon: STORY_EMOJI.flag };
}

/**
 * Nimo's Turbo Race: the kart zooms the laps (tap for a turbo boost) and every lap pops a lap
 * stamp with that lap's points, but never a running total. At the finish booth the child turns the
 * score wheels to the total; nothing is checked until the score is sent to the scoreboard.
 */
export function TurboRace({
	task,
	prompt,
	returning,
	outcome,
	busy,
	reducedMotion,
	evidence,
	onSubmit,
}: {
	task: CarnivalTask;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const { count: laps, size } = groupsOf(task);
	const [lap, setLap] = useState(reducedMotion ? laps : 0);
	const [boost, setBoost] = useState(false);
	const [digits, setDigits] = useState<number[]>(() =>
		Array(wheelCount(task)).fill(0),
	);
	const [touched, setTouched] = useState(false);
	const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
	const racing = lap < laps;
	const playing = outcome === "playing";
	const labels = scoreLabels(task);

	// One timer per lap: each finished lap starts the next.
	useEffect(() => {
		if (lap >= laps) return;
		timer.current = setTimeout(
			() => {
				carnivalSounds.play("lap");
				setLap((done) => done + 1);
				setBoost(false);
			},
			boost ? BOOST_LAP_MS : LAP_MS,
		);
		return () => clearTimeout(timer.current);
	}, [lap, laps, boost]);

	useEffect(() => {
		if (!racing) carnivalSounds.play("zoom");
	}, [racing]);

	const turbo = () => {
		if (!racing || boost) return;
		carnivalSounds.play("boost");
		setBoost(true);
	};

	const instruction =
		outcome === "correct"
			? "නියමයි! ලකුණු පුවරුව දැල්වුණා!"
			: outcome === "wrong"
				? "අපොයි! ලකුණු ටිකක් පැටලුණා."
				: racing
					? "රේස් එක යනවා! ටර්බෝ එකට තට්ටු කරන්න!"
					: `${returning ? "අලුත් රේස් එකක්! " : ""}${prompt}`;

	return (
		<div
			className="turbo-race"
			data-outcome={outcome}
			data-racing={racing || undefined}
		>
			<p className="carnival-scroll" role="status">
				{instruction}
			</p>
			<div className="race-track" aria-hidden="true">
				<Art art="rivalBanana" className="race-rival race-rival-1" />
				<Art art="rivalTurtle" className="race-rival race-rival-2" />
				<span
					key={lap}
					className="race-kart"
					data-boost={boost || undefined}
					style={
						{
							"--lap-ms": `${boost ? BOOST_LAP_MS : LAP_MS}ms`,
						} as CSSProperties
					}
				>
					<Art art="dust" className="race-dust" />
					<Art art="nimoKart" className="race-kart-art" />
				</span>
			</div>
			<ol className="race-stamps" aria-label="වට">
				{Array.from({ length: laps }, (_, at) => (
					<li
						// biome-ignore lint/suspicious/noArrayIndexKey: the lap order is the identity.
						key={at}
						data-done={at < lap || undefined}
					>
						<span aria-hidden="true">{labels.icon}</span>
						{at < lap ? size : ""}
					</li>
				))}
			</ol>
			{racing ? (
				<button
					type="button"
					className="game-action race-turbo"
					disabled={boost}
					onClick={turbo}
				>
					ටර්බෝ! 🚀
				</button>
			) : (
				<div className="race-booth">
					<div className="race-board">
						<span>
							<strong>{size}</strong>
							<small>{labels.each}</small>
						</span>
						<span className="race-times">×</span>
						<span>
							<strong>{laps}</strong>
							<small>{labels.count}</small>
						</span>
						<span className="race-times">=</span>
						<span className="race-total">
							<strong>?</strong>
							<small>මුළු ගණන</small>
						</span>
					</div>
					<ScoreWheels
						digits={digits}
						disabled={!playing}
						onChange={(next) => {
							evidence.note(
								"digit",
								next.findIndex((digit, at) => digit !== digits[at]),
							);
							setTouched(true);
							setDigits(next);
						}}
					/>
					<button
						type="button"
						className="game-action race-send"
						disabled={busy || !touched || !playing}
						onClick={() => {
							carnivalSounds.play("tap");
							onSubmit(carnivalResponse(task, digits));
						}}
					>
						ලකුණු පුවරුවට!
					</button>
				</div>
			)}
		</div>
	);
}
