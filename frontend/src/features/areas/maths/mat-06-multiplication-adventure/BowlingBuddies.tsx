import { type CSSProperties, useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art } from "./carnivalParts";
import {
	type CarnivalTask,
	carnivalResponse,
	digitsOf,
	groupsOf,
} from "./carnivalRules";
import { carnivalSounds, countNote } from "./carnivalSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const ROLL_MS = 700;

/**
 * Bowling Buddies (the most visible help): one lane per group. The child sets up every lane with
 * the same number of giggling pins, then rolls: the ball knocks down one lane at a time and the
 * counter climbs by one group each time (3 → 6 → 9 → 12), so the total is what the groups make.
 */
export function BowlingBuddies({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	task: CarnivalTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const { count: lanes, size } = groupsOf(task);
	const [ready, setReady] = useState<boolean[]>(() => Array(lanes).fill(demo));
	const [knocked, setKnocked] = useState(demo ? lanes : 0);
	const [rolling, setRolling] = useState(false);
	const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
	useEffect(() => () => clearTimeout(timer.current), []);
	const allReady = ready.every(Boolean);
	const done = knocked >= lanes;
	const total = knocked * size;

	useEffect(() => {
		onResponse(
			demo || !done ? null : carnivalResponse(task, digitsOf(lanes * size, 3)),
		);
	}, [demo, done, task, lanes, size, onResponse]);

	useEffect(() => {
		if (!rolling) return;
		if (knocked >= lanes) {
			setRolling(false);
			carnivalSounds.play("sparkle", { delay: 0.2 });
			return;
		}
		timer.current = setTimeout(() => {
			carnivalSounds.play("pins");
			countNote(knocked + 1);
			setKnocked((count) => count + 1);
		}, ROLL_MS);
	}, [rolling, knocked, lanes]);

	const setUp = (lane: number) => {
		if (demo || ready[lane]) return;
		evidence.note("move");
		carnivalSounds.play("pick");
		setReady(ready.map((value, at) => value || at === lane));
	};
	const roll = () => {
		if (demo || !allReady || rolling || done) return;
		evidence.note("move");
		carnivalSounds.play("roll");
		setRolling(true);
	};

	const nextLane = ready.indexOf(false);
	const message = demo
		? `පේළි ${lanes}යි, එක පේළියකට කූරු ${size}යි.`
		: !allReady
			? `එක පේළියකට කූරු ${size}ක් දාමු!`
			: done
				? `නියමයි! කූරු ${lanes * size}ම පෙරළුණා!`
				: "හැම පේළියම සූදානම්! බෝලය ගහමු!";

	return (
		<div
			className="bowling"
			data-demo={demo || undefined}
			data-rolling={rolling || undefined}
		>
			<p className="carnival-message" role="status">
				{message}
			</p>
			<div
				className="bowling-lanes"
				style={{ "--lanes": Math.min(lanes, 6) } as CSSProperties}
			>
				{ready.map((isReady, lane) => (
					<button
						type="button"
						// biome-ignore lint/suspicious/noArrayIndexKey: the lane order is the identity.
						key={lane}
						className="bowling-lane"
						data-ready={isReady || undefined}
						data-knocked={lane < knocked || undefined}
						data-ghost={(hint && !demo && lane === nextLane) || undefined}
						disabled={demo || isReady}
						aria-label={`${lane + 1} වන පේළියට කූරු ${size}ක් දාන්න`}
						onClick={() => setUp(lane)}
					>
						<span className="bowling-lane-name">පේළිය {lane + 1}</span>
						<span className="bowling-pins" aria-hidden="true">
							{isReady &&
								Array.from({ length: size }, (_, pin) => (
									<Art
										// biome-ignore lint/suspicious/noArrayIndexKey: pins are interchangeable.
										key={pin}
										art={lane < knocked ? "pinDown" : "pinUp"}
										className="bowling-pin"
									/>
								))}
						</span>
						<strong className="bowling-lane-count">
							{isReady ? size : "?"}
						</strong>
					</button>
				))}
			</div>
			<div className="bowling-score">
				<span className="bowling-sum">
					{Array.from({ length: knocked }, () => size).join(" + ") || "0"}
					{knocked > 0 && ` = ${total}`}
				</span>
				{done && (
					<strong className="bowling-times">
						{lanes} × {size} = {lanes * size}
					</strong>
				)}
			</div>
			{!demo && allReady && !done && (
				<button
					type="button"
					className="bowling-roll"
					disabled={rolling}
					onClick={roll}
				>
					බෝලය ගහමු! 🎳
				</button>
			)}
		</div>
	);
}
