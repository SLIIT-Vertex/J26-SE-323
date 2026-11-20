import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art, BLOCK_LABEL, BlockPile, type BlockSize } from "./villageParts";
import {
	metrePieces,
	roadResponse,
	solvedWorking,
	type VillageTask,
} from "./villageRules";
import { villageSounds } from "./villageSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const SIZES: BlockSize[] = ["km", 100, 10, 1];
const METRES: Record<BlockSize, number> = { km: 1000, 100: 100, 10: 10, 1: 1 };

/** Blocks of a distance, by size. */
const blocksOf = (km: number, metres: number): Record<BlockSize, number> => {
	const { hundreds, tens, ones } = metrePieces(metres);
	return { km, 100: hundreds, 10: tens, 1: ones };
};

type Road = {
	km: number;
	metres: number;
	/** Adding: blocks still in the toy box. Subtracting: blocks still to take away. */
	waiting: Record<BlockSize, number>;
	/** The metres when the last toy-box block went on (adding). */
	metreTotal: number;
	exchanged: boolean;
};

function startRoad(task: VillageTask): Road {
	return {
		km: task.left.km,
		metres: task.left.m,
		waiting: blocksOf(task.right.km, task.right.m),
		metreTotal: task.left.m,
		exchanged: false,
	};
}

function finishedRoad(task: VillageTask): Road {
	const working = solvedWorking(task, task.operation);
	return {
		km: working.km,
		metres:
			task.operation === "add" && working.exchanged
				? working.metres - 1000
				: working.metres,
		waiting: { km: 0, 100: 0, 10: 0, 1: 0 },
		metreTotal: working.metres,
		exchanged: working.exchanged,
	};
}

/**
 * සෙල්ලම් ගෙදර පාර හදමු! The toy road is made of 1 km, 100 m, 10 m and 1 m blocks. Adding: the
 * toy box's blocks join the road; ten 100 m blocks then swap for one 1 km block. Taking away: the
 * blocks to remove are listed; when the metre blocks run short, one 1 km block opens into ten
 * 100 m blocks. When the road is right, the little red car drives across it.
 */
export function ToyRoad({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	task: VillageTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const adding = task.operation === "add";
	const [road, setRoad] = useState<Road>(() =>
		demo ? finishedRoad(task) : startRoad(task),
	);
	const [nudge, setNudge] = useState<string | null>(null);
	const [sparkles, setSparkles] = useState(0);
	const waitingLeft = SIZES.some((size) => road.waiting[size] > 0);
	const metresToRemove = SIZES.slice(1).reduce(
		(total, size) => total + road.waiting[size] * METRES[size],
		0,
	);
	const canExchange = adding
		? !waitingLeft && road.metres >= 1000
		: road.km > 0 && road.metres < metresToRemove;
	const done = !waitingLeft && !(adding && road.metres >= 1000);

	useEffect(() => {
		onResponse(
			demo || !done
				? null
				: roadResponse(task, {
						operation: task.operation,
						metres: adding ? road.metreTotal : road.metres,
						exchanged: road.exchanged,
						km: road.km,
					}),
		);
	}, [demo, done, task, adding, road, onResponse]);

	const moveBlocks = (size: BlockSize) => {
		if (demo || road.waiting[size] === 0) return;
		if (adding) {
			evidence.note("move");
			villageSounds.play("block");
			const count = road.waiting[size];
			const metres =
				size === "km" ? road.metres : road.metres + count * METRES[size];
			setNudge(null);
			setRoad({
				...road,
				km: size === "km" ? road.km + count : road.km,
				metres,
				metreTotal: metres,
				waiting: { ...road.waiting, [size]: 0 },
			});
			return;
		}
		const short = size === "km" ? road.km < 1 : road.metres < METRES[size];
		if (short) {
			villageSounds.play("boing");
			setNudge("මීටර් මදිද? මේ ලොකු කෑල්ල මාරු කරමු!");
			return;
		}
		evidence.note("move");
		villageSounds.play("remove");
		setNudge(null);
		setRoad({
			...road,
			km: size === "km" ? road.km - 1 : road.km,
			metres: size === "km" ? road.metres : road.metres - METRES[size],
			waiting: { ...road.waiting, [size]: road.waiting[size] - 1 },
		});
	};
	const exchange = () => {
		if (demo || !canExchange) return;
		evidence.note("carry");
		villageSounds.play("exchange");
		setSparkles(sparkles + 1);
		setNudge("බලන්න! කිලෝමීටර 1ක් කියන්නේ මීටර් 1000ක්!");
		setRoad(
			adding
				? {
						...road,
						km: road.km + 1,
						metres: road.metres - 1000,
						exchanged: true,
					}
				: {
						...road,
						km: road.km - 1,
						metres: road.metres + 1000,
						exchanged: true,
					},
		);
	};

	useEffect(() => {
		if (done && !demo) villageSounds.play("car", { delay: 0.3 });
	}, [done, demo]);

	const shown = blocksOf(road.km, road.metres);
	const used = blocksOf(task.right.km, task.right.m);
	const message = demo
		? `${task.left.km} km ${task.left.m} m ${adding ? "+" : "−"} ${task.right.km} km ${task.right.m} m = ${road.km} km ${road.metres} m`
		: nudge
			? nudge
			: done
				? "නියමයි! කාර් එකට දැන් යන්න පුළුවන්!"
				: adding && !waitingLeft
					? "මීටර් 1000ක් = 1 km! 100 m කෑලි 10ක් මාරු කරමු."
					: "කාර් එකට පාරක් හදමු!";
	// The next right move, shown faintly on a help stage.
	const next: BlockSize | "exchange" | null = done
		? null
		: canExchange
			? "exchange"
			: (SIZES.find((size) => road.waiting[size] > 0) ?? null);

	return (
		<div
			className="toy-road"
			data-demo={demo || undefined}
			data-done={done || undefined}
		>
			<p className="village-message" role="status">
				{message}
			</p>
			<div className="toy-track">
				<Art art="grassLeft" className="toy-ground" />
				<Art art="toyCar" className="toy-car" />
				<div className="toy-blocks">
					{sparkles > 0 && (
						<Art key={sparkles} art="sparkle" className="toy-sparkle" />
					)}
					{SIZES.map((size) =>
						shown[size] > 0 ? (
							<BlockPile
								key={size}
								size={size}
								count={shown[size]}
								max={size === "km" ? 6 : 10}
							/>
						) : null,
					)}
				</div>
				<Art art="grassRight" className="toy-ground" />
				<Art art="flag" className="toy-flag" />
				<strong className="toy-total">
					= {road.km} km {road.metres} m
				</strong>
			</div>
			{!demo && !done && (
				<div className="toy-box">
					<small>{adding ? "සෙල්ලම් පෙට්ටිය:" : "අයින් කරන්න:"}</small>
					{SIZES.filter((size) => used[size] > 0).map((size) => (
						<button
							key={size}
							type="button"
							className="toy-box-pile"
							data-size={size}
							disabled={road.waiting[size] === 0}
							data-ghost={(hint && next === size) || undefined}
							aria-label={`${adding ? "පාරට" : "අයින් කරන්න"} ${BLOCK_LABEL[size]} (${road.waiting[size]})`}
							onClick={() => moveBlocks(size)}
						>
							<BlockPile size={size} count={road.waiting[size]} max={3} />
							<span className="toy-box-verb">{adding ? "➕" : "➖"}</span>
						</button>
					))}
					<button
						type="button"
						className="toy-exchange"
						disabled={!canExchange}
						data-ghost={(hint && next === "exchange") || undefined}
						onClick={exchange}
					>
						{adding ? "🔁 100 m × 10 → 1 km" : "🔁 1 km → 100 m × 10"}
					</button>
				</div>
			)}
		</div>
	);
}
