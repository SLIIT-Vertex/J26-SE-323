import { useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import {
	HOME_X,
	HOME_Y,
	mountParade,
	type ParadeHandle,
	SLOT_Y,
	TOY_SIZE,
} from "./paradeScene";
import {
	emptyLine,
	type ParadeLine,
	paradeResponse,
	placeToy,
	removeToy,
	spaced,
} from "./toyRules";
import { toySounds } from "./toySounds";

export const TOY_NAMES = ["රොබෝ", "ඩයිනෝ", "දුම්රිය", "ටෙඩී"] as const;

const percent = (value: number, of: number) => `${(value / of) * 100}%`;

/**
 * The Toy Parade: put the four toys in order before the curtain opens. Toys can be dragged on the
 * stage, or tapped and then a slot tapped (the buttons over the stage also serve screen readers).
 */
export function ToyParadeMission({
	values,
	ascending,
	returning,
	outcome,
	busy,
	reducedMotion,
	evidence,
	onSubmit,
}: {
	values: readonly number[];
	ascending: boolean;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const count = Math.min(4, values.length);
	const host = useRef<HTMLDivElement>(null);
	const scene = useRef<ParadeHandle | null>(null);
	const [line, setLine] = useState<ParadeLine>(() => emptyLine(count));
	const [selected, setSelectedState] = useState<number | null>(null);
	const picked = useRef<number | null>(null);
	const setSelected = (toy: number | null) => {
		picked.current = toy;
		setSelectedState(toy);
	};
	const current = useRef(line);
	current.current = line;
	const latest = useRef({ evidence });
	latest.current = { evidence };
	const valuesKey = values.slice(0, count).join(",");
	const response = paradeResponse(line, values);
	const playing = outcome === "playing";

	const put = (toy: number, slot: number | null) => {
		const next =
			slot === null
				? removeToy(current.current, toy)
				: placeToy(current.current, toy, slot);
		latest.current.evidence.note("move");
		toySounds.play(slot === null ? "back" : "place");
		if (slot !== null) toySounds.play("boing", { delay: 0.25, volume: 0.6 });
		current.current = next;
		setLine(next);
		setSelected(null);
		scene.current?.select(null);
		scene.current?.setLine(next, slot === null ? undefined : toy);
	};
	const tapToy = (toy: number) => {
		if (!playing) return;
		// A toy standing in a slot covers it: tapping it with another toy picked up swaps them.
		const standing = current.current.indexOf(toy);
		if (picked.current !== null && picked.current !== toy && standing !== -1) {
			put(picked.current, standing);
			return;
		}
		toySounds.play("pick");
		const next = picked.current === toy ? null : toy;
		setSelected(next);
		scene.current?.select(next);
	};
	const tapSlot = (slot: number) => {
		if (!playing || picked.current === null) return;
		put(picked.current, slot);
	};
	const handlers = useRef({ put, tapToy, tapSlot });
	handlers.current = { put, tapToy, tapSlot };

	useEffect(() => {
		const element = host.current;
		if (!element) return;
		let disposed = false;
		let handle: ParadeHandle | null = null;
		mountParade(element, {
			values: valuesKey.split(",").map(Number),
			reducedMotion,
			onDrop: (toy, slot) => {
				if (slot === null && !current.current.includes(toy)) {
					handle?.setLine(current.current);
					return;
				}
				handlers.current.put(toy, slot);
			},
			onTapToy: (toy) => handlers.current.tapToy(toy),
			onTapSlot: (slot) => handlers.current.tapSlot(slot),
		})
			.then((mounted) => {
				handle = mounted;
				if (disposed) mounted.destroy();
				else {
					scene.current = mounted;
					mounted.setLine(current.current);
				}
			})
			// No canvas (tests, very old browsers): the buttons still play the whole parade.
			.catch(() => undefined);
		return () => {
			disposed = true;
			handle?.destroy();
			scene.current = null;
			element.replaceChildren();
		};
	}, [valuesKey, reducedMotion]);

	useEffect(() => {
		if (outcome === "correct") scene.current?.march();
		if (outcome === "wrong") scene.current?.confused();
	}, [outcome]);

	const instruction =
		outcome === "correct"
			? "නියමයි! පෙළපාළිය පටන් ගත්තා!"
			: outcome === "wrong"
				? "අපොයි! සෙල්ලම් බඩු පටලැවිලා."
				: ascending
					? "කුඩාම අංකයේ සිට ලොකුම අංකයට පෙළගස්වන්න!"
					: "ලොකුම අංකයේ සිට කුඩාම අංකයට පෙළගස්වන්න!";

	return (
		<div
			className="toy-parade"
			data-outcome={outcome}
			data-selected={selected ?? undefined}
		>
			<div className="toy-canvas" aria-hidden="true">
				<div ref={host} className="canvas-host" />
			</div>
			<p className="toy-scroll" role="status">
				{returning && playing ? "නව සෙල්ලම් බඩු ආවා! " : ""}
				{instruction}
			</p>
			{values.slice(0, count).map((value, toy) => {
				const slot = line.indexOf(toy);
				const x = slot === -1 ? HOME_X[toy] : HOME_X[slot];
				const y = slot === -1 ? HOME_Y : SLOT_Y;
				return (
					<button
						type="button"
						// biome-ignore lint/suspicious/noArrayIndexKey: toy order is the identity.
						key={toy}
						className="toy-hit"
						data-toy={toy}
						aria-pressed={selected === toy}
						disabled={!playing}
						aria-label={`${TOY_NAMES[toy]} ${spaced(value)}`}
						style={{
							left: percent((x ?? 960) - TOY_SIZE / 2, 1920),
							top: percent(y - TOY_SIZE / 2, 1080),
						}}
						onClick={() => tapToy(toy)}
					/>
				);
			})}
			{line.map((toy, slot) => (
				<button
					type="button"
					// biome-ignore lint/suspicious/noArrayIndexKey: slot order is the identity.
					key={slot}
					className="toy-slot"
					data-filled={toy !== null || undefined}
					disabled={!playing || selected === null}
					aria-label={`${slot + 1} වන තැන`}
					style={{
						left: percent((HOME_X[slot] ?? 960) - 140, 1920),
						top: percent(SLOT_Y - 120, 1080),
					}}
					onClick={() => tapSlot(slot)}
				/>
			))}
			<p className="toy-direction" aria-hidden="true">
				<span>{ascending ? "කුඩා" : "ලොකු"}</span>
				<span className="toy-arrow">➜</span>
				<span>{ascending ? "ලොකු" : "කුඩා"}</span>
			</p>
			<button
				type="button"
				className="game-action toy-start"
				disabled={busy || !response || !playing}
				onClick={() => {
					if (!response) return;
					toySounds.play("tap");
					onSubmit(response);
				}}
			>
				පෙළපාළිය අරඹමු!
			</button>
		</div>
	);
}
