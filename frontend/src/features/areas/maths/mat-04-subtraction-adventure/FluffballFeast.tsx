import { useEffect, useMemo, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { PACK_ART } from "./cafeArt";
import {
	type MonsterMood,
	Monsters,
	OrderBoard,
	Pile,
	StoryPick,
} from "./cafeParts";
import {
	biggerSource,
	type CafeOrder,
	cafeResponse,
	digitsOf,
	operands,
	PLACE_NAMES,
	type Source,
	solveColumns,
	workingDigits,
} from "./cafeRules";
import { biteNote, burstSparkle, cafeSounds } from "./cafeSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const NEXT_COLUMN_MS = 900;

/**
 * Feed the Fluffballs (the most visible help): one column at a time, the little monsters eat that
 * column's snacks one by one and the rest stay on the plate. When the plate has too few, Nimo
 * brings one pack from the next column, which bursts into ten. What is left becomes that column's
 * answer digit.
 */
export function FluffballFeast({
	order,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	order: CafeOrder;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const width = order.places.length;
	const bigger = biggerSource(order);
	const [top, setTop] = useState<Source | null>(() => (demo ? bigger : null));
	const numbers = operands(order, order.story ? top : null);
	const topValue = numbers?.top ?? null;
	const bottomValue = numbers?.bottom ?? null;
	const solved = useMemo(
		() =>
			topValue === null || bottomValue === null
				? null
				: solveColumns(topValue, bottomValue, width),
		[topValue, bottomValue, width],
	);
	const [opens, setOpens] = useState<number[]>(() =>
		demo && solved ? solved.opens : [],
	);
	const [left, setLeft] = useState<Array<number | null>>(() =>
		demo && solved ? solved.digits : Array.from({ length: width }, () => null),
	);
	const [column, setColumn] = useState(() => (demo ? -1 : width - 1));
	const [eaten, setEaten] = useState(0);
	const [mood, setMood] = useState<MonsterMood>("idle");
	const [wrongPick, setWrongPick] = useState(false);
	const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
	useEffect(() => () => clearTimeout(timer.current), []);

	const upper = topValue === null ? null : digitsOf(topValue, width);
	const lower = bottomValue === null ? null : digitsOf(bottomValue, width);
	const working = upper ? workingDigits(upper, opens) : [];
	const need = lower?.[column] ?? 0;
	const plate = (working[column] ?? 0) - eaten;
	const place = order.places[column];
	const tooFew = column >= 0 && (working[column] ?? 0) < need;
	const canBring = tooFew && column > 0 && (working[column - 1] ?? 0) > 0;
	const done = left.every((digit) => digit !== null);

	useEffect(() => {
		onResponse(demo || !done ? null : cafeResponse(order, top, left, opens));
	}, [demo, done, left, opens, top, order, onResponse]);

	const pickTop = (source: Source) => {
		if (demo) return;
		evidence.note("move");
		if (source !== bigger) {
			cafeSounds.play("boing");
			setWrongPick(true);
			return;
		}
		cafeSounds.play("pick");
		setWrongPick(false);
		setTop(source);
	};
	const feed = () => {
		if (demo || column < 0 || !lower || eaten >= need) return;
		if (plate <= 0) {
			cafeSounds.play("boing");
			return;
		}
		evidence.note("move");
		cafeSounds.play("chomp", { volume: 0.7 });
		biteNote(eaten);
		const ate = eaten + 1;
		setEaten(ate);
		setMood("eating");
		if (ate < need) return;
		// This column is finished: what is still on the plate is its answer digit.
		const digits = [...left];
		digits[column] = (working[column] ?? 0) - ate;
		setLeft(digits);
		setMood("happy");
		cafeSounds.play("sparkle", { delay: 0.2, volume: 0.5 });
		timer.current = setTimeout(() => {
			setColumn(column - 1);
			setEaten(0);
			setMood("idle");
		}, NEXT_COLUMN_MS);
	};
	const bring = () => {
		if (demo || !canBring) return;
		evidence.note("carry");
		cafeSounds.play("unwrap");
		burstSparkle();
		setOpens([...opens, column - 1]);
	};
	const skipEmpty = () => {
		// A column the monsters eat nothing from (0 to eat): everything stays.
		if (demo || column < 0 || need !== 0) return;
		const digits = [...left];
		digits[column] = working[column] ?? 0;
		setLeft(digits);
		setColumn(column - 1);
	};

	const message = demo
		? "කන ගාණ අඩු වෙනකොට ඉතිරිය පේනවා."
		: wrongPick
			? "ඒ ඇණවුම පොඩියි! ලොකු ඇණවුමෙන් පටන් ගමු."
			: order.story && !top
				? "කාගේ ඇණවුම ලොකුද? ඒක තෝරන්න!"
				: done
					? "නියමයි! රාක්ෂ පැටව්න්ගේ බඩ පිරුණා!"
					: place
						? `${PLACE_NAMES[place]} තීරුව: රාක්ෂ පැටව්න්ට ${need} ක් කන්න දෙමු!`
						: "";

	return (
		<div className="fluff-feast" data-demo={demo || undefined}>
			<p className="snack-message" role="status">
				{message}
			</p>
			{order.story && !demo && (
				<StoryPick order={order} top={top} onPick={pickTop} />
			)}
			{numbers && (
				<div className="fluff-board">
					<OrderBoard
						places={order.places}
						top={numbers.top}
						bottom={numbers.bottom}
						topLabel="තිබුණා"
						bottomLabel="කනවා"
						opens={opens}
						digits={left}
						selected={column >= 0 ? column : null}
						disabled
					/>
				</div>
			)}
			{numbers && (
				<Monsters
					mood={mood}
					onTap={column >= 0 && !done ? () => feed() : undefined}
				/>
			)}
			{numbers && column >= 0 && place && (
				<div className="fluff-plate" data-too-few={tooFew || undefined}>
					<span className="fluff-left">
						<small>ඉතිරි කෑම</small>
						<strong>{plate}</strong>
					</span>
					<button
						type="button"
						className="fluff-pile"
						disabled={eaten >= need || plate <= 0}
						aria-label="කෑමක් දෙන්න"
						onClick={feed}
					>
						<Pile art={PACK_ART[place]} count={plate} />
					</button>
					<span className="fluff-eaten">
						කෑවා {eaten} / {need}
					</span>
					{canBring && (
						<button
							type="button"
							className="fluff-bring"
							data-ghost={hint || undefined}
							onClick={bring}
						>
							{PLACE_NAMES[order.places[column - 1] ?? "tens"]} එකක් ගෙනෙමු ➜
						</button>
					)}
					{need === 0 && (
						<button type="button" className="fluff-bring" onClick={skipEmpty}>
							කන්න දෙයක් නෑ. ඊළඟට ➜
						</button>
					)}
				</div>
			)}
		</div>
	);
}
