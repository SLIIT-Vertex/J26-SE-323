import { useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import { type FactoryHandle, mountFactory } from "./factoryScene";
import {
	allFed,
	bundle,
	canBundle,
	digitsByPower,
	emptyFactory,
	type FactoryState,
	factoryResponse,
	feed,
	PLACE_NAME_BY_POWER,
	solveFactory,
} from "./factoryRules";
import { skySounds } from "./skySounds";
import type { useMoveEvidence } from "./useMoveEvidence";

type Evidence = ReturnType<typeof useMoveEvidence>;

/**
 * The Number Factory: feed each number into the machine, bundle every ten blocks into the next
 * place with the lever under its bin, then set the output wheels to the total. As a worked
 * example (`demo`) it shows the finished machine and cannot be touched.
 */
export function NumberFactory({
	addends,
	demo = false,
	hint = false,
	reducedMotion,
	evidence,
	onResponse,
}: {
	addends: readonly number[];
	demo?: boolean;
	/** Show the answer faintly behind unset output wheels (a help stage). */
	hint?: boolean;
	reducedMotion: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const total = addends.reduce((sum, value) => sum + value, 0);
	const [factory, setFactory] = useState<FactoryState>(() =>
		demo ? solveFactory(addends) : emptyFactory(addends),
	);
	const [output, setOutput] = useState<Array<number | null>>(() =>
		demo
			? digitsByPower(total, factory.places)
			: factory.counts.map(() => null),
	);
	const current = useRef(factory);
	const host = useRef<HTMLDivElement>(null);
	const scene = useRef<FactoryHandle | null>(null);
	const powers = Array.from(
		{ length: factory.places },
		(_, at) => factory.places - 1 - at,
	);
	const answer = digitsByPower(total, factory.places);
	const fedAll = allFed(factory);

	useEffect(() => {
		onResponse(demo ? null : factoryResponse(factory, output));
	}, [demo, factory, output, onResponse]);

	const places = factory.places;
	useEffect(() => {
		const element = host.current;
		if (!element) return;
		let disposed = false;
		let handle: FactoryHandle | null = null;
		mountFactory(element, places, reducedMotion)
			.then((mounted) => {
				handle = mounted;
				if (disposed) {
					mounted.destroy();
					return;
				}
				scene.current = mounted;
				mounted.show(current.current.counts, { type: "set" });
			})
			// No canvas (tests, very old browsers): the buttons still play the whole factory.
			.catch(() => undefined);
		return () => {
			disposed = true;
			handle?.destroy();
			scene.current = null;
			element.replaceChildren();
		};
	}, [places, reducedMotion]);

	const update = (next: FactoryState) => {
		current.current = next;
		setFactory(next);
	};

	const feedNumber = (index: number) => {
		const next = feed(current.current, addends, index);
		if (next === current.current) return;
		evidence.note("move");
		// The number's blocks clatter into their bins one after another.
		for (const delay of [0, 0.12, 0.24])
			skySounds.play("feed", { delay, volume: 0.8 });
		update(next);
		scene.current?.show(next.counts, { type: "feed" });
	};

	const pullLever = (power: number) => {
		evidence.note("carry");
		skySounds.play("lever");
		if (!canBundle(current.current, power)) {
			skySounds.play("refuse", { delay: 0.1, volume: 0.6 });
			scene.current?.refuse(power);
			return;
		}
		skySounds.play("bundle", { delay: 0.15 });
		const next = bundle(current.current, power);
		update(next);
		scene.current?.show(next.counts, { type: "bundle", from: power });
	};

	/** One tap turns a place's output digit on by one: ? → 0 → 1 … 9 → 0. */
	const turnWheel = (power: number) => {
		evidence.note("digit", power);
		skySounds.play("tick");
		setOutput((digits) =>
			digits.map((digit, at) =>
				at !== power ? digit : digit === null ? 0 : (digit + 1) % 10,
			),
		);
	};

	return (
		<div
			className="number-factory"
			data-demo={demo || undefined}
			style={{ "--places": places } as React.CSSProperties}
		>
			<div className="factory-feed">
				{addends.map((value, index) => (
					<button
						type="button"
						// biome-ignore lint/suspicious/noArrayIndexKey: number order is the identity and values may repeat.
						key={index}
						className="factory-card"
						data-fed={factory.fed[index] || undefined}
						disabled={demo || factory.fed[index]}
						aria-label={`${value} යන්ත්‍රයට දාන්න`}
						onClick={() => feedNumber(index)}
					>
						<strong>{value}</strong>
						<span aria-hidden="true">{factory.fed[index] ? "✓" : "⬇"}</span>
					</button>
				))}
				<p className="factory-legend">10 එකක් = දහය 1ක්</p>
			</div>
			<div className="factory-machine">
				<div className="factory-row factory-headers" aria-hidden="true">
					{powers.map((power) => (
						<span key={power} data-power={power}>
							{PLACE_NAME_BY_POWER[power]}
						</span>
					))}
				</div>
				<div className="factory-canvas" aria-hidden="true">
					<div ref={host} className="canvas-host" />
				</div>
				<div className="factory-row factory-levers">
					{powers.map((power) =>
						power < places - 1 ? (
							<button
								type="button"
								key={power}
								className="factory-lever"
								data-ready={canBundle(factory, power) || undefined}
								disabled={demo || !fedAll}
								aria-label={`${PLACE_NAME_BY_POWER[power]} 10ක් ${PLACE_NAME_BY_POWER[power + 1]} 1කට බඳින්න`}
								onClick={() => pullLever(power)}
							>
								<span aria-hidden="true">⬅ 10</span>
							</button>
						) : (
							<span key={power} />
						),
					)}
				</div>
				<fieldset className="factory-row factory-output" disabled={demo}>
					<legend>මුළු එකතුව</legend>
					{powers.map((power) => {
						const digit = output[power] ?? null;
						const ghost = hint && digit === null;
						return (
							<button
								type="button"
								key={power}
								className="factory-digit"
								data-ghost={ghost || undefined}
								aria-label={`${PLACE_NAME_BY_POWER[power]} ඉලක්කම වැඩි කරන්න`}
								onClick={() => turnWheel(power)}
							>
								<strong aria-live="polite">
									{digit ?? (ghost ? answer[power] : "?")}
								</strong>
								<span aria-hidden="true">▲</span>
							</button>
						);
					})}
				</fieldset>
			</div>
		</div>
	);
}
