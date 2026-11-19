import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { SPECTATORS } from "./carnivalArt";
import { ScoreWheels } from "./carnivalParts";
import {
	type CarnivalTask,
	carnivalResponse,
	digitsOf,
	numberFromDigits,
	type SeatBlock,
	seatBlocks,
} from "./carnivalRules";
import { carnivalSounds, countNote } from "./carnivalSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const BLOCK_NAMES: Record<SeatBlock["place"], string> = {
	hundreds: "සිය",
	tens: "දහය",
	ones: "එක",
};

/**
 * The Dancing Stadium: every stand has the same number of seats. The child places the seat blocks
 * (hundreds, tens and ones of one stand) into all the stands, sees each block's seats for all the
 * stands, then turns the score wheels to the whole stadium's seats. The right total starts the wave.
 */
export function DancingStadium({
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
	const multiplicand =
		task.kind === "story" ? task.groupSize : task.multiplicand;
	const stands = task.kind === "story" ? task.groupCount : task.multiplier;
	const blocks = seatBlocks(multiplicand);
	const width = task.kind === "written" ? task.width : 3;
	const product = multiplicand * stands;
	const [placed, setPlaced] = useState<Set<SeatBlock["place"]>>(
		() => new Set(demo ? blocks.map((block) => block.place) : []),
	);
	const [digits, setDigits] = useState<number[]>(() =>
		demo ? digitsOf(product, width) : Array(width).fill(0),
	);
	const [touched, setTouched] = useState(false);
	const allPlaced = blocks.every((block) => placed.has(block.place));
	const wave =
		allPlaced && numberFromDigits(digits) === product && (touched || demo);

	useEffect(() => {
		onResponse(
			demo || !allPlaced || !touched ? null : carnivalResponse(task, digits),
		);
	}, [demo, allPlaced, touched, task, digits, onResponse]);

	const place = (block: SeatBlock) => {
		if (demo || placed.has(block.place)) return;
		evidence.note("move");
		carnivalSounds.play("seat");
		countNote(placed.size + 3);
		setPlaced(new Set([...placed, block.place]));
	};

	const message = demo
		? `${multiplicand} × ${stands}: බ්ලොක් එකින් එක ගුණ කරලා එකතු කළා.`
		: !allPlaced
			? `පේළි ${stands}ටම පුටු ${multiplicand} බැගින්! බ්ලොක් ටික පේළිවලට දාමු.`
			: wave
				? "නියමයි! හැමෝම රැල්ල නටනවා!"
				: `පේළි ${stands}ටම පුටු කීයක් ඕනෑද?`;

	return (
		<div
			className="stadium"
			data-demo={demo || undefined}
			data-wave={wave || undefined}
		>
			<p className="carnival-message" role="status">
				{message}
			</p>
			<div className="stadium-blocks">
				<span className="stadium-split">
					{multiplicand} = {blocks.map((block) => block.value).join(" + ")}
				</span>
				{blocks.map((block) => (
					<button
						type="button"
						key={block.place}
						className="stadium-block"
						data-place={block.place}
						aria-pressed={placed.has(block.place)}
						data-ghost={
							(hint && !demo && !placed.has(block.place)) || undefined
						}
						disabled={demo || placed.has(block.place)}
						aria-label={`${BLOCK_NAMES[block.place]} බ්ලොක් ${block.value} පේළිවලට දාන්න`}
						onClick={() => place(block)}
					>
						{block.value}
					</button>
				))}
			</div>
			<div className="stadium-stands">
				{Array.from({ length: stands }, (_, row) => (
					<div
						// biome-ignore lint/suspicious/noArrayIndexKey: the stand order is the identity.
						key={row}
						className="stadium-stand"
						style={{ animationDelay: `${row * 80}ms` }}
					>
						<span className="stadium-stand-name">පේළිය {row + 1}</span>
						{blocks
							.filter((block) => placed.has(block.place))
							.map((block) => (
								<span
									key={block.place}
									className="stadium-seats"
									data-place={block.place}
								>
									<span aria-hidden="true">
										{SPECTATORS[(row + block.value) % SPECTATORS.length]}
									</span>
									{block.value}
								</span>
							))}
					</div>
				))}
			</div>
			<div className="stadium-sums">
				{blocks
					.filter((block) => placed.has(block.place))
					.map((block) => (
						<span
							key={block.place}
							className="stadium-sum"
							data-place={block.place}
						>
							{block.value} × {stands} = {block.value * stands}
						</span>
					))}
			</div>
			{allPlaced && (
				<div className="stadium-total">
					<span>මුළු පුටු</span>
					<ScoreWheels
						digits={digits}
						ghost={hint && !demo ? digitsOf(product, width) : undefined}
						disabled={demo}
						onChange={(next) => {
							evidence.note(
								"digit",
								next.findIndex((digit, at) => digit !== digits[at]),
							);
							setTouched(true);
							setDigits(next);
							if (numberFromDigits(next) === product)
								carnivalSounds.play("sparkle");
						}}
					/>
				</div>
			)}
		</div>
	);
}
