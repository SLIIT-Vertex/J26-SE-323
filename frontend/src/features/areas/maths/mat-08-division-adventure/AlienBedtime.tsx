import { type CSSProperties, useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { colourAt } from "./spaceArt";
import { Alien, Art, Ufo } from "./spaceParts";
import { type SpaceTask, sharingResponse } from "./spaceRules";
import { spaceSounds } from "./spaceSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

/** Up to this many sleepy aliens are drawn on the pad; the number beside them is exact. */
const DRAWN = 20;

/**
 * Bouncy Alien Bedtime (the most visible help): baby aliens bounce on the pad, and each sleeping pod
 * must get the same number. Tapping a pod bounces one alien into it; with many aliens a "10 each"
 * button helps. When fewer are left than there are pods, the rest snuggle into Nimo's little pod.
 */
export function AlienBedtime({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	task: SpaceTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const share = Math.floor(task.dividend / task.divisor);
	const [beds, setBeds] = useState<number[]>(() =>
		Array(task.divisor).fill(demo ? share : 0),
	);
	const [withNimo, setWithNimo] = useState(
		demo ? task.dividend - share * task.divisor : 0,
	);
	const [jumped, setJumped] = useState<number | null>(null);
	const onPad =
		task.dividend - beds.reduce((sum, count) => sum + count, 0) - withNimo;
	const done = onPad === 0;
	const equal = beds.every((count) => count === beds[0]);

	useEffect(() => {
		onResponse(demo || !done ? null : sharingResponse(task, beds, withNimo));
	}, [demo, done, task, beds, withNimo, onResponse]);

	const put = (bed: number, count = 1) => {
		if (demo || onPad < count) return;
		evidence.note("move");
		spaceSounds.play("boing");
		setJumped(bed);
		setBeds(beds.map((value, at) => (at === bed ? value + count : value)));
	};
	const round = (count: number) => {
		if (demo || onPad < count * task.divisor) return;
		evidence.note("move");
		spaceSounds.play("beam");
		setBeds(beds.map((value) => value + count));
	};
	const toNimo = () => {
		if (demo || onPad === 0 || onPad >= task.divisor) return;
		evidence.note("move");
		spaceSounds.play("snore");
		setWithNimo(withNimo + onPad);
	};
	const takeBack = (bed: number) => {
		if (demo || (beds[bed] ?? 0) === 0) return;
		spaceSounds.play("back");
		setBeds(beds.map((value, at) => (at === bed ? value - 1 : value)));
	};

	const message = demo
		? `පැටව් ${task.dividend} දෙනා ඇඳන් ${task.divisor}ට ${share} බැගින්.`
		: done
			? equal
				? "නියමයි! හැමෝම එකම විදියට නිදි! 💤"
				: "අයියෝ! ඇඳන්වල එක ගාණක් නෑ. ආපහු ගන්න."
			: `පැටව් ${task.dividend} දෙනා ඇඳන් ${task.divisor}ට සමානව බෙදමු!`;

	return (
		<div
			className="alien-bedtime"
			data-demo={demo || undefined}
			data-sleeping={(done && equal) || undefined}
		>
			<p className="space-message" role="status">
				{message}
			</p>
			<div className="bedtime-pad">
				{Array.from({ length: Math.min(DRAWN, onPad) }, (_, at) => (
					<span
						// biome-ignore lint/suspicious/noArrayIndexKey: the babies are interchangeable.
						key={at}
						className="bedtime-baby"
						style={{ "--at": at } as CSSProperties}
					>
						<Alien colour={colourAt(at)} />
					</span>
				))}
				<strong className="bedtime-count">{onPad}</strong>
			</div>
			<div
				className="bedtime-pods"
				style={{ "--pods": task.divisor } as CSSProperties}
			>
				{beds.map((count, bed) => (
					<div
						// biome-ignore lint/suspicious/noArrayIndexKey: the pod order is the identity.
						key={bed}
						className="bedtime-pod"
						data-jump={jumped === bed || undefined}
						onAnimationEnd={() => setJumped(null)}
					>
						<button
							type="button"
							className="bedtime-pod-button"
							disabled={demo || onPad === 0}
							data-ghost={
								(hint && !demo && count < share && onPad > 0) || undefined
							}
							aria-label={`ඇඳ ${bed + 1}ට පැටියෙක් (දැන් ${count})`}
							onClick={() => put(bed)}
						>
							<Art art="dome" className="bedtime-dome" />
							<span className="bedtime-sleepers" aria-hidden="true">
								{Array.from({ length: Math.min(6, count) }, (_, at) => (
									// biome-ignore lint/suspicious/noArrayIndexKey: sleepers are interchangeable.
									<Alien key={at} colour={colourAt(bed)} />
								))}
							</span>
							<Ufo colour={colourAt(bed)} />
						</button>
						<span className="bedtime-pod-label">
							ඇඳ {bed + 1}: <strong>{count}</strong>
						</span>
						{!demo && count > 0 && (
							<button
								type="button"
								className="bedtime-back"
								aria-label={`ඇඳ ${bed + 1}න් පැටියෙක් ආපහු`}
								onClick={() => takeBack(bed)}
							>
								↩
							</button>
						)}
					</div>
				))}
			</div>
			{!demo && (
				<div className="bedtime-buttons">
					{task.dividend >= 10 * task.divisor && (
						<button
							type="button"
							className="bedtime-round"
							disabled={onPad < 10 * task.divisor}
							onClick={() => round(10)}
						>
							හැම ඇඳකටම 10 බැගින්
						</button>
					)}
					<button
						type="button"
						className="bedtime-round"
						disabled={onPad < task.divisor}
						onClick={() => round(1)}
					>
						හැම ඇඳකටම 1 බැගින්
					</button>
					<button
						type="button"
						className="bedtime-nimo"
						disabled={onPad === 0 || onPad >= task.divisor}
						data-ghost={
							(hint && onPad > 0 && onPad < task.divisor) || undefined
						}
						onClick={toNimo}
					>
						💤 ඉතිරි අය නිමෝ ළඟට ({withNimo})
					</button>
				</div>
			)}
		</div>
	);
}
