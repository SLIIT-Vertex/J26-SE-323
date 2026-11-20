import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { BundlePile, type BundleSize, UfoRow } from "./spaceParts";
import {
	boardingResponse,
	digitsOf,
	placeName,
	type SpaceTask,
} from "./spaceRules";
import { spaceSounds } from "./spaceSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const SIZES: BundleSize[] = [100, 10, 1];

type Board = {
	/** Star bundles still on the splitter, per place (left to right). */
	pile: number[];
	/** Rounds dealt per place: every UFO got this many bundles of that place. */
	dealt: number[];
	/** The place being shared now. */
	place: number;
};

const start = (dividend: number): Board => {
	const digits = digitsOf(dividend);
	return { pile: digits, dealt: digits.map(() => 0), place: 0 };
};

/** The whole sharing done right: for the worked example. */
function finished(dividend: number, divisor: number): Board {
	const board = start(dividend);
	for (let place = 0; place < board.pile.length; place++) {
		const rounds = Math.floor((board.pile[place] ?? 0) / divisor);
		board.dealt[place] = rounds;
		board.pile[place] = (board.pile[place] ?? 0) - rounds * divisor;
		if (place < board.pile.length - 1) {
			board.pile[place + 1] =
				(board.pile[place + 1] ?? 0) + (board.pile[place] ?? 0) * 10;
			board.pile[place] = 0;
		}
	}
	board.place = board.pile.length - 1;
	return board;
}

/**
 * Star Splitter: the stars wait in bundles of 100, 10 and 1. "One each" gives every UFO one bundle
 * of the place being shared; when fewer bundles are left than there are UFOs, the splitting beam
 * breaks them into ten smaller bundles each. Stars left at the end stay with Nimo. What each UFO got
 * of every place is the long-division working.
 */
export function StarSplitter({
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
	const width = digitsOf(task.dividend).length;
	const sizes = SIZES.slice(3 - width);
	const [board, setBoard] = useState<Board>(() =>
		demo ? finished(task.dividend, task.divisor) : start(task.dividend),
	);
	const [nudge, setNudge] = useState<string | null>(null);
	const here = board.pile[board.place] ?? 0;
	const last = board.place === width - 1;
	const canDeal = here >= task.divisor;
	const done = last && !canDeal;
	const each = board.dealt.reduce(
		(total, rounds, place) => total + rounds * (sizes[place] ?? 1),
		0,
	);

	useEffect(() => {
		onResponse(demo || !done ? null : boardingResponse(task, board.dealt));
	}, [demo, done, task, board.dealt, onResponse]);

	const deal = () => {
		if (demo) return;
		if (!canDeal) {
			spaceSounds.play("boing");
			setNudge("හැම යානයකටම දෙන්න තරම් පොකුරු නෑ. කඩමු!");
			return;
		}
		evidence.note("move");
		spaceSounds.play("beam");
		setNudge(null);
		setBoard({
			...board,
			pile: board.pile.map((count, place) =>
				place === board.place ? count - task.divisor : count,
			),
			dealt: board.dealt.map((count, place) =>
				place === board.place ? count + 1 : count,
			),
		});
	};
	const split = () => {
		if (demo || last) return;
		if (canDeal) {
			spaceSounds.play("boing");
			setNudge("තවම හැම යානයකටම එකක් බැගින් දෙන්න පුළුවන්!");
			return;
		}
		evidence.note("carry");
		spaceSounds.play("split");
		setNudge(
			here > 0
				? `${sizes[board.place]} පොකුරු ${here} → ${sizes[board.place + 1]} පොකුරු ${here * 10}`
				: null,
		);
		setBoard({
			...board,
			pile: board.pile.map((count, place) =>
				place === board.place
					? 0
					: place === board.place + 1
						? count + here * 10
						: count,
			),
			place: board.place + 1,
		});
	};

	const size = sizes[board.place] ?? 1;
	const message = demo
		? `${task.dividend} ÷ ${task.divisor}: හැම යානයකටම ${each}යි.`
		: nudge
			? nudge
			: done
				? `නියමයි! හැම යානයකටම තරු ${each} බැගින්.`
				: canDeal
					? `${size} පොකුරු යානා ${task.divisor}ට එක බැගින් බෙදමු!`
					: "ලොකු තරු පොකුර කුඩා පොකුරුවලට කඩමු!";

	return (
		<div
			className="star-splitter"
			data-demo={demo || undefined}
			data-done={done || undefined}
		>
			<p className="space-message" role="status">
				{message}
			</p>
			<div className="splitter-pile">
				{sizes.map((bundle, place) => (
					<span
						key={bundle}
						className="splitter-place"
						data-here={place === board.place || undefined}
					>
						<small>{placeName(place, width)}</small>
						<BundlePile
							size={bundle}
							count={board.pile[place] ?? 0}
							kind="star"
						/>
					</span>
				))}
			</div>
			{!demo && !done && (
				<div className="splitter-buttons">
					<button
						type="button"
						className="splitter-deal"
						data-ghost={(hint && canDeal) || undefined}
						onClick={deal}
					>
						⭐ හැම යානයකටම {size} බැගින් එකක්
					</button>
					{!last && (
						<button
							type="button"
							className="splitter-split"
							data-ghost={(hint && !canDeal) || undefined}
							onClick={split}
						>
							✂️ පොකුරු කඩමු ({size} → {sizes[board.place + 1]})
						</button>
					)}
				</div>
			)}
			<UfoRow
				count={task.divisor}
				labels={Array.from({ length: task.divisor }, () => each)}
			>
				{() => (
					<span className="splitter-cargo">
						{sizes.map((bundle, place) =>
							(board.dealt[place] ?? 0) > 0 ? (
								<BundlePile
									key={bundle}
									size={bundle}
									count={board.dealt[place] ?? 0}
									kind="star"
									max={4}
								/>
							) : null,
						)}
					</span>
				)}
			</UfoRow>
			{done && (
				<p className="splitter-left">
					නිමෝ එක්ක ඉතිරි: <strong>{here}</strong>
				</p>
			)}
		</div>
	);
}
