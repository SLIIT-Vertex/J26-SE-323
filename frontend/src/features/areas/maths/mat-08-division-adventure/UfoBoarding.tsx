import { useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { colourAt } from "./spaceArt";
import {
	Alien,
	Art,
	BundlePile,
	type BundleSize,
	DigitDial,
	UfoRow,
} from "./spaceParts";
import {
	boardingResponse,
	digitsOf,
	perShipNumber,
	placeName,
	type SpaceTask,
} from "./spaceRules";
import { spaceSounds } from "./spaceSounds";

const SIZES: BundleSize[] = [100, 10, 1];

/** The waiting guests by bundle: stations of 100, shuttles of 10 and single aliens. */
export function GuestPiles({
	dividend,
	kind,
}: {
	dividend: number;
	kind: "alien" | "star";
}) {
	const digits = digitsOf(dividend);
	const sizes = SIZES.slice(3 - digits.length);
	return (
		<div className="guest-piles">
			{sizes.map((size, column) => (
				<BundlePile
					key={size}
					size={size}
					count={digits[column] ?? 0}
					kind={kind}
					max={6}
				/>
			))}
			<strong className="guest-total">= {dividend}</strong>
		</div>
	);
}

/**
 * UFO Boarding Chaos: the guests wait in stations, shuttles and singles; the child dials how
 * many go into EACH UFO, place by place (hundreds, tens, ones), then launches. Nothing is checked
 * before the launch; then the UFOs fly off together, or wobble while Nimo scratches his head.
 * Any guests left over ride with Nimo in his little pod.
 */
export function UfoBoarding({
	task,
	prompt,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: SpaceTask;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const width = digitsOf(task.dividend).length;
	const [perShip, setPerShip] = useState<number[]>(() => Array(width).fill(0));
	const [touched, setTouched] = useState(false);
	const playing = outcome === "playing";
	const each = perShipNumber(perShip);
	const leftover = task.dividend - each * task.divisor;
	const sent = outcome !== "playing";
	const nimo =
		outcome === "correct"
			? "nimoCheer"
			: outcome === "wrong"
				? "nimoThink"
				: "nimoIdle";
	const instruction =
		outcome === "correct"
			? "නියමයි! යානා ඔක්කොම එකට ඉගිලුණා!"
			: outcome === "wrong"
				? "අපොයි! යානාවල අමුත්තන් ගාණ පැටලුණා."
				: `${returning ? "අලුත් ගමනක්! " : ""}${prompt}`;

	return (
		<div className="ufo-boarding" data-outcome={outcome}>
			<p className="space-scroll" role="status">
				{instruction}
			</p>
			<div className="boarding-deck">
				<div className="boarding-guests">
					<small>බලාගෙන ඉන්න අමුත්තන්</small>
					<GuestPiles dividend={task.dividend} kind="alien" />
				</div>
				<UfoRow
					count={task.divisor}
					labels={Array.from({ length: task.divisor }, () =>
						sent ? each : "?",
					)}
					launched={outcome === "correct"}
					wobble={outcome === "wrong"}
				>
					{(index) =>
						sent && (
							<span className="ufo-riders" aria-hidden="true">
								<Alien colour={colourAt(index)} />
								<Alien colour={colourAt(index + 2)} />
							</span>
						)
					}
				</UfoRow>
				<div className="boarding-controls">
					<span className="boarding-question">එක් යානයකට කී දෙනාද?</span>
					<div className="boarding-dials">
						{perShip.map((value, column) => (
							<DigitDial
								// biome-ignore lint/suspicious/noArrayIndexKey: the place is the identity.
								key={column}
								label={placeName(column, width)}
								value={value}
								disabled={!playing}
								onChange={(next) => {
									evidence.note("digit", column);
									setTouched(true);
									setPerShip(
										perShip.map((digit, at) => (at === column ? next : digit)),
									);
								}}
							/>
						))}
						<strong className="boarding-each">= {each}</strong>
					</div>
				</div>
				<div
					className="nimo-pod"
					data-filled={(sent && leftover > 0) || undefined}
				>
					<Art art={nimo} className="nimo-pod-nimo" />
					<span className="nimo-pod-label">
						නිමෝ එක්ක:{" "}
						<strong className="nimo-pod-count">
							{sent ? Math.max(0, leftover) : "?"}
						</strong>
					</span>
				</div>
			</div>
			<button
				type="button"
				className="game-action boarding-launch"
				disabled={busy || !touched || !playing}
				onClick={() => {
					spaceSounds.play("launch");
					onSubmit(boardingResponse(task, perShip));
				}}
			>
				🚀 පුරවලා ඉගිලවමු!
			</button>
		</div>
	);
}
