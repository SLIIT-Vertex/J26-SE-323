import { useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import { type CrystalFlightHandle, mountCrystalFlight } from "./crystalScene";
import { collect, crystalResponse, stepEnergy } from "./crystalRules";
import type { useMoveEvidence } from "./useMoveEvidence";

type Evidence = ReturnType<typeof useMoveEvidence>;

/**
 * Nimo's crystal flight: fly through every energy crystal, then set how much energy they make
 * together. As a worked example (`demo`) everything is collected and nothing can be touched.
 */
export function CrystalFlight({
	values,
	demo = false,
	hint = false,
	reducedMotion,
	evidence,
	onResponse,
}: {
	values: readonly number[];
	demo?: boolean;
	/** Show the total faintly while it is unset (a help stage). */
	hint?: boolean;
	reducedMotion: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const total = values.reduce((sum, value) => sum + value, 0);
	const [collected, setCollected] = useState<number[]>(() =>
		demo ? values.map((_, at) => at) : [],
	);
	const [energy, setEnergy] = useState<number | null>(demo ? total : null);
	const host = useRef<HTMLDivElement>(null);
	const scene = useRef<CrystalFlightHandle | null>(null);
	const latest = useRef({ collected, evidence });
	latest.current = { collected, evidence };
	const valuesKey = values.join(",");
	const allCollected = values.length > 0 && collected.length >= values.length;

	useEffect(() => {
		onResponse(demo ? null : crystalResponse(values.length, collected, energy));
	}, [demo, values.length, collected, energy, onResponse]);

	useEffect(() => {
		const element = host.current;
		if (!element) return;
		let disposed = false;
		let handle: CrystalFlightHandle | null = null;
		mountCrystalFlight(element, {
			values: valuesKey.split(",").map(Number),
			collected: latest.current.collected,
			still: demo,
			reducedMotion,
			onCollect: (index) => {
				latest.current.evidence.note("move");
				setCollected((current) => collect(current, index));
			},
		})
			.then((mounted) => {
				handle = mounted;
				if (disposed) mounted.destroy();
				else scene.current = mounted;
			})
			// No canvas (tests, very old browsers): the crystal buttons still play the flight.
			.catch(() => undefined);
		return () => {
			disposed = true;
			handle?.destroy();
			scene.current = null;
			element.replaceChildren();
		};
	}, [valuesKey, demo, reducedMotion]);

	const collectFromButton = (index: number) => {
		if (collected.includes(index)) return;
		evidence.note("move");
		scene.current?.collect(index);
		setCollected((current) => collect(current, index));
	};

	const turn = (delta: 1 | -1) => {
		evidence.note("digit", 0);
		setEnergy((current) => stepEnergy(current, delta));
	};

	return (
		<div className="crystal-flight" data-demo={demo || undefined}>
			<p className="crystal-instruction" role="status">
				{allCollected ? "මුළු ශක්තිය කීයද?" : "නිමෝව ස්ඵටික හරහා පියාසර කරවන්න!"}
			</p>
			<div className="crystal-canvas" aria-hidden="true">
				<div ref={host} className="canvas-host" />
			</div>
			<div className="crystal-controls">
				<div className="crystal-row">
					{values.map((value, index) => (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: crystal order is the identity and values may repeat.
							key={index}
							className="crystal"
							aria-pressed={collected.includes(index)}
							disabled={demo}
							aria-label={`ශක්තිය ${value} ඇති ස්ඵටිකය එකතු කරන්න`}
							onClick={() => collectFromButton(index)}
						>
							+{value}
						</button>
					))}
				</div>
				<fieldset className="crystal-total" disabled={demo || !allCollected}>
					<legend>මුළු ශක්තිය</legend>
					<button
						type="button"
						className="crystal-step"
						aria-label="ශක්තිය අඩු කරන්න"
						onClick={() => turn(-1)}
					>
						−
					</button>
					<strong
						aria-live="polite"
						data-ghost={(hint && energy === null) || undefined}
					>
						{energy ?? (hint ? total : "?")}
					</strong>
					<button
						type="button"
						className="crystal-step"
						aria-label="ශක්තිය වැඩි කරන්න"
						onClick={() => turn(1)}
					>
						+
					</button>
				</fieldset>
			</div>
		</div>
	);
}
