import { useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import { CarryLock } from "./CarryLock";
import { mountSkyCity, type SkyCityHandle } from "./skyCityScene";
import {
	applyLockAction,
	CRATE_LABELS,
	emptyLock,
	equationText,
	lockResponse,
} from "./skyRules";
import type { useMoveEvidence } from "./useMoveEvidence";

export type MissionOutcome = "playing" | "correct" | "wrong";

/**
 * The city mission: load the three airship crates into the warehouse, then set the warehouse lock
 * to their total. Mounted fresh for every question (`key` = item revision).
 */
export function SkyCityMission({
	addends,
	returning,
	outcome,
	busy,
	reducedMotion,
	evidence,
	onSubmit,
}: {
	addends: readonly number[];
	/** True for the question after training. */
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const host = useRef<HTMLDivElement>(null);
	const scene = useRef<SkyCityHandle | null>(null);
	const [loaded, setLoaded] = useState<number[]>([]);
	const [lock, setLock] = useState(emptyLock);
	const allLoaded = addends.length > 0 && loaded.length >= addends.length;
	const latest = useRef({ addends, evidence });
	latest.current = { addends, evidence };
	const addendsKey = addends.join(",");
	const response = lockResponse(lock);

	useEffect(() => {
		const element = host.current;
		if (!element) return;
		let disposed = false;
		let handle: SkyCityHandle | null = null;
		mountSkyCity(element, {
			addends: addendsKey.split(",").map(Number),
			reducedMotion,
			onCrateLoaded: (index) => {
				latest.current.evidence.note("move");
				setLoaded((current) =>
					current.includes(index) ? current : [...current, index],
				);
			},
		})
			.then((mounted) => {
				handle = mounted;
				if (disposed) mounted.destroy();
				else scene.current = mounted;
			})
			// No canvas (tests, very old browsers): the HTML board still plays the whole mission.
			.catch(() => undefined);
		return () => {
			disposed = true;
			handle?.destroy();
			scene.current = null;
			element.replaceChildren();
		};
	}, [addendsKey, reducedMotion]);

	useEffect(() => {
		if (outcome === "playing")
			scene.current?.pose(allLoaded ? "think" : "idle");
	}, [allLoaded, outcome]);

	useEffect(() => {
		if (outcome === "correct") scene.current?.celebrate();
		if (outcome === "wrong") scene.current?.stayLocked();
	}, [outcome]);

	const loadFromBoard = (index: number) => {
		if (loaded.includes(index)) return;
		evidence.note("move");
		scene.current?.loadCrate(index);
		setLoaded((current) => [...current, index]);
	};

	const instruction =
		outcome === "correct"
			? "නියමයි! ගබඩාව ඇරුණා!"
			: outcome === "wrong"
				? "අපොයි! දොර තවම වැසිලා."
				: allLoaded
					? "ගබඩා දොර අරින්න, මුළු එකතුව අගුලට දාන්න!"
					: returning
						? "නිමෝ ආපසු ආවා! අලුත් බඩු පෙට්ටි තුනම ගබඩාවට ගෙන යන්න!"
						: "බඩු පෙට්ටි තුනම ගබඩාවට ගෙන යන්න!";

	return (
		<div
			className="sky-mission"
			data-mission-step={allLoaded ? "lock" : "load"}
			data-outcome={outcome}
		>
			<div ref={host} className="sky-canvas" aria-hidden="true" />
			<p className="sky-scroll" role="status">
				{instruction}
			</p>
			<section className="sky-board" aria-label="බඩු ගණන">
				<h2>බඩු ගණන</h2>
				<ul>
					{addends.map((value, index) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: crate letter order is the identity.
						<li key={index}>
							<button
								type="button"
								data-loaded={loaded.includes(index) || undefined}
								disabled={loaded.includes(index) || outcome !== "playing"}
								aria-label={`${CRATE_LABELS[index]} පෙට්ටිය ${value} ගබඩාවට ගෙන යන්න`}
								onClick={() => loadFromBoard(index)}
							>
								<span
									className="sky-crate-letter"
									data-crate={CRATE_LABELS[index]}
								>
									{CRATE_LABELS[index]}
								</span>
								<strong>{value}</strong>
								{loaded.includes(index) && <span aria-hidden="true">✓</span>}
							</button>
						</li>
					))}
				</ul>
			</section>
			<ol className="sky-chain" aria-label="ගබඩාවට ආ බඩු">
				{loaded.map((index, position) => (
					<li key={index}>
						{position === 0 ? "" : "+"}
						{addends[index]}
					</li>
				))}
			</ol>
			{allLoaded && (
				<section className="sky-lock-panel" aria-label="ගබඩා අගුල">
					<p className="sky-equation">{equationText(addends)}</p>
					<CarryLock
						lock={lock}
						disabled={busy || outcome !== "playing"}
						onAction={(action) => {
							evidence.note(action.type, action.place);
							setLock((current) => applyLockAction(current, action));
						}}
					/>
					<button
						type="button"
						className="sky-action"
						disabled={busy || !response || outcome !== "playing"}
						onClick={() => response && onSubmit(response)}
					>
						දොර අරින්න
					</button>
				</section>
			)}
		</div>
	);
}
