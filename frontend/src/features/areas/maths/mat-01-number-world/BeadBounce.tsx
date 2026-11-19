import { type CSSProperties, useEffect, useMemo, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { TOY_ART_KEYS, toyArtReady, toyArtUrl } from "./toyArt";
import {
	beadResponse,
	emptyLine,
	emptyRods,
	numberFromRods,
	type ParadeLine,
	PLACE_NAMES,
	paradeResponse,
	placeToy,
	rodPower,
	rodsFromNumber,
	spaced,
	stepRod,
} from "./toyRules";
import { beadMelody, beadNote, toySounds } from "./toySounds";
import { TOY_NAMES } from "./ToyParadeMission";

type Evidence = ReturnType<typeof useMoveEvidence>;

/** Rod centres across the reused wooden frame, as fractions of its width. */
const ROD_X = [0.131, 0.2765, 0.4265, 0.575, 0.724, 0.871];

/**
 * The Bead Bounce toy, build mode: tap a rod to drop a bead on it (each bead plays a note), tap
 * "−" to take one off. As a worked example it shows the finished number and cannot be touched.
 */
export function BeadBuilder({
	number,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	number: number;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const target = rodsFromNumber(number);
	const [rods, setRods] = useState<number[]>(() =>
		demo ? target : emptyRods(),
	);
	const [touched, setTouched] = useState(false);
	const built = numberFromRods(rods);

	useEffect(() => {
		onResponse(demo || !touched ? null : beadResponse(rods));
	}, [demo, touched, rods, onResponse]);

	const change = (rod: number, delta: 1 | -1) => {
		if (demo) return;
		const next = stepRod(rods, rod, delta);
		if (next[rod] === rods[rod]) return;
		evidence.note(delta > 0 ? "move" : "digit", rodPower(rod));
		beadNote(rod, next[rod] ?? 0);
		setRods(next);
		setTouched(true);
		if (numberFromRods(next) === number) {
			beadMelody();
			toySounds.play("sparkle", { delay: 0.7, volume: 0.5 });
		}
	};

	return (
		<div
			className="bead-toy"
			data-demo={demo || undefined}
			data-bead-art={toyArtReady("bead") || undefined}
		>
			<div className="bead-frame">
				{toyArtReady("abacusFrame") ? (
					<img src={toyArtUrl("abacusFrame")} alt="" />
				) : (
					<div className="bead-frame-shape" />
				)}
				{rods.map((beads, rod) => (
					<button
						type="button"
						// biome-ignore lint/suspicious/noArrayIndexKey: rod order is the place identity.
						key={rod}
						className="bead-rod"
						data-rod={rod}
						disabled={demo}
						style={{ left: `${(ROD_X[rod] ?? 0) * 100}%` } as CSSProperties}
						aria-label={`${PLACE_NAMES[rodPower(rod)]} දණ්ඩට බෝලයක් දාන්න (දැන් ${beads})`}
						onClick={() => change(rod, 1)}
					>
						{Array.from(
							{ length: Math.max(beads, hint ? (target[rod] ?? 0) : 0) },
							(_, at) => (
								<span
									// biome-ignore lint/suspicious/noArrayIndexKey: beads on a rod are interchangeable.
									key={at}
									className="bead"
									data-ghost={at >= beads || undefined}
									style={{ "--rod": rod } as CSSProperties}
								/>
							),
						)}
					</button>
				))}
			</div>
			<div className="bead-controls">
				{rods.map((beads, rod) => (
					<div
						// biome-ignore lint/suspicious/noArrayIndexKey: rod order is the place identity.
						key={rod}
						className="bead-control"
						style={{ left: `${(ROD_X[rod] ?? 0) * 100}%` } as CSSProperties}
					>
						<span>{PLACE_NAMES[rodPower(rod)]}</span>
						<button
							type="button"
							disabled={demo || beads === 0}
							aria-label={`${PLACE_NAMES[rodPower(rod)]} දණ්ඩෙන් බෝලයක් ඉවත් කරන්න`}
							onClick={() => change(rod, -1)}
						>
							−
						</button>
					</div>
				))}
			</div>
			<p className="bead-readout">
				<span>ඔබ සෑදූ අංකය</span>
				<strong aria-live="polite">{spaced(built)}</strong>
			</p>
		</div>
	);
}

/**
 * Bead Bounce, compare mode (help on a parade): every toy's number is shown as bead columns so
 * the places can be compared, then the toys are put in order.
 */
export function BeadCompare({
	values,
	ascending,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	values: readonly number[];
	ascending: boolean;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const valuesKey = values.slice(0, 4).join(",");
	const shown = useMemo(() => valuesKey.split(",").map(Number), [valuesKey]);
	const sorted = shown
		.map((value, toy) => ({ value, toy }))
		.sort((a, b) => (ascending ? a.value - b.value : b.value - a.value));
	const [line, setLine] = useState<ParadeLine>(() =>
		demo ? sorted.map((entry) => entry.toy) : emptyLine(shown.length),
	);
	const [selected, setSelected] = useState<number | null>(null);
	const places = Math.max(...shown.map((value) => String(value).length), 1);

	useEffect(() => {
		onResponse(demo ? null : paradeResponse(line, shown));
	}, [demo, line, shown, onResponse]);

	const tapSlot = (slot: number) => {
		if (demo || selected === null) return;
		evidence.note("move");
		toySounds.play("place");
		setLine(placeToy(line, selected, slot));
		setSelected(null);
	};

	return (
		<div className="bead-compare" data-demo={demo || undefined}>
			<p className="bead-compare-direction">
				{ascending ? "කුඩාම අංකයේ සිට ලොකුම අංකයට" : "ලොකුම අංකයේ සිට කුඩාම අංකයට"}
			</p>
			<div className="bead-compare-toys">
				{shown.map((value, toy) => {
					const digits = String(value).padStart(places, " ").split("");
					return (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: toy order is the identity.
							key={toy}
							className="bead-compare-toy"
							data-toy={toy}
							data-placed={line.includes(toy) || undefined}
							aria-pressed={selected === toy}
							disabled={demo}
							aria-label={`${TOY_NAMES[toy]} ${spaced(value)}`}
							onClick={() => {
								toySounds.play("pick");
								setSelected(selected === toy ? null : toy);
							}}
						>
							<span className="bead-compare-head">
								{TOY_ART_KEYS[toy] && toyArtReady(TOY_ART_KEYS[toy]) && (
									<img src={toyArtUrl(TOY_ART_KEYS[toy])} alt="" />
								)}
								<strong>{spaced(value)}</strong>
							</span>
							<span className="mini-abacus">
								{digits.map((digit, column) => (
									<span
										// biome-ignore lint/suspicious/noArrayIndexKey: columns are place positions.
										key={column}
										className="mini-rod"
										data-power={places - 1 - column}
									>
										{Array.from(
											{ length: digit === " " ? 0 : Number(digit) },
											(_, at) => (
												<i
													// biome-ignore lint/suspicious/noArrayIndexKey: beads are interchangeable.
													key={at}
													style={{ "--rod": column } as CSSProperties}
												/>
											),
										)}
									</span>
								))}
							</span>
							<span className="mini-places" aria-hidden="true">
								{digits.map((_, column) => (
									// biome-ignore lint/suspicious/noArrayIndexKey: columns are place positions.
									<em key={column}>{PLACE_NAMES[places - 1 - column]}</em>
								))}
							</span>
						</button>
					);
				})}
			</div>
			<div className="bead-compare-slots">
				{line.map((toy, slot) => (
					<button
						type="button"
						// biome-ignore lint/suspicious/noArrayIndexKey: slot order is the identity.
						key={slot}
						className="bead-compare-slot"
						disabled={demo || selected === null}
						aria-label={`${slot + 1} වන තැන`}
						onClick={() => tapSlot(slot)}
					>
						{toy !== null ? (
							spaced(shown[toy] ?? 0)
						) : hint ? (
							<span data-ghost>{spaced(sorted[slot]?.value ?? 0)}</span>
						) : (
							slot + 1
						)}
					</button>
				))}
			</div>
		</div>
	);
}
