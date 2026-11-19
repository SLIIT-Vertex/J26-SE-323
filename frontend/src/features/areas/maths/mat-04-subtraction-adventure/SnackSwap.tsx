import { type CSSProperties, useEffect, useMemo, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { PACK_ART } from "./cafeArt";
import { Pile, StoryPick } from "./cafeParts";
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
import { burstSparkle, cafeSounds } from "./cafeSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

/**
 * Magical Snack Swap: the snacks sit in trays of boxes (100), packets (10) and singles. The monster's
 * order is given tray by tray; when a tray has too few, the child opens one pack from the tray on
 * its left, which bursts into ten. What stays in the trays is the answer.
 */
export function SnackSwap({
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
	const upper = topValue === null ? null : digitsOf(topValue, width);
	const lower = bottomValue === null ? null : digitsOf(bottomValue, width);
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
	const [given, setGiven] = useState<boolean[]>(() =>
		Array.from({ length: width }, () => demo),
	);
	const [short, setShort] = useState<number | null>(null);
	const [burst, setBurst] = useState<number | null>(null);

	const working = upper ? workingDigits(upper, opens) : [];
	const stock = working.map((count, column) =>
		given[column] ? count - (lower?.[column] ?? 0) : count,
	);
	const done = given.every(Boolean);

	useEffect(() => {
		if (demo || !done || topValue === null || bottomValue === null) {
			onResponse(null);
			return;
		}
		// Every tray has given its share: what is left in each tray is that answer digit.
		const left = workingDigits(digitsOf(topValue, width), opens);
		const eaten = digitsOf(bottomValue, width);
		onResponse(
			cafeResponse(
				order,
				top,
				left.map((count, column) => count - (eaten[column] ?? 0)),
				opens,
			),
		);
	}, [demo, done, topValue, bottomValue, width, opens, top, order, onResponse]);

	const pickTop = (source: Source) => {
		if (demo) return;
		evidence.note("move");
		if (source !== bigger) {
			// A help game may say so: the smaller order cannot give the bigger one.
			cafeSounds.play("boing");
			setShort(-1);
			return;
		}
		cafeSounds.play("pick");
		setShort(null);
		setTop(source);
	};
	const open = (column: number) => {
		if (demo || !upper || column >= width - 1) return;
		if ((stock[column] ?? 0) <= 0) {
			cafeSounds.play("boing");
			return;
		}
		evidence.note("carry");
		cafeSounds.play("unwrap");
		cafeSounds.play("burst", { delay: 0.25, volume: 0.6 });
		burstSparkle();
		setOpens([...opens, column]);
		setBurst(column + 1);
		setShort(null);
	};
	const give = (column: number) => {
		if (demo || !lower || given[column]) return;
		evidence.note("digit", column);
		if ((working[column] ?? 0) < (lower[column] ?? 0)) {
			cafeSounds.play("boing");
			setShort(column);
			return;
		}
		cafeSounds.play("chomp");
		setShort(null);
		setGiven(given.map((value, at) => value || at === column));
	};
	const startOver = () => {
		if (demo) return;
		cafeSounds.play("back");
		setOpens([]);
		setGiven(Array.from({ length: width }, () => false));
		setShort(null);
	};

	const place = short !== null && short >= 0 ? order.places[short] : undefined;
	const message = demo
		? "පැකට්ටුවක් ඇරියම, ඒක දහයක් වෙනවා."
		: short === -1
			? "ඒ ඇණවුම පොඩියි! ලොකු ඇණවුමෙන් පටන් ගමු."
			: order.story && !top
				? "කාගේ ඇණවුම ලොකුද? ඒක තෝරන්න!"
				: place === "ones"
					? "තනි කෑම මදිද? දහයේ පැකට්ටුවක් විවෘත කරමු!"
					: place
						? `${PLACE_NAMES[place]} මදිද? වම් පැත්තෙන් එකක් විවෘත කරමු!`
						: done
							? "නියමයි! ඉතිරි කෑම තැටිවල තියෙනවා."
							: "රාක්ෂයාට ඇණවුම තැටියෙන් තැටියට දෙමු!";

	return (
		<div className="snack-swap" data-demo={demo || undefined}>
			<p className="snack-message" role="status">
				{message}
			</p>
			{order.story && !demo && (
				<StoryPick order={order} top={top} onPick={pickTop} />
			)}
			{numbers && (
				<p className="snack-order">
					<span className="snack-order-chip">තිබුණා {numbers.top}</span>
					<span className="snack-order-chip">ඇණවුම {numbers.bottom}</span>
				</p>
			)}
			{upper && lower && (
				<div
					className="snack-trays"
					style={{ "--columns": width } as CSSProperties}
				>
					{order.places.map((placeName, column) => (
						<div
							key={placeName}
							className="snack-tray"
							data-short={short === column || undefined}
							data-burst={burst === column || undefined}
							onAnimationEnd={() => setBurst(null)}
						>
							<span className="snack-tray-name">{PLACE_NAMES[placeName]}</span>
							<span className="snack-tray-pile" aria-hidden="true">
								<Pile art={PACK_ART[placeName]} count={stock[column] ?? 0} />
							</span>
							<strong className="snack-count">{stock[column]}</strong>
							{column < width - 1 && (
								<button
									type="button"
									className="snack-open"
									data-ghost={
										(hint && !demo && solved?.opens.includes(column)) ||
										undefined
									}
									disabled={demo || (stock[column] ?? 0) <= 0}
									aria-label={`${PLACE_NAMES[placeName]} එකක් විවෘත කරන්න`}
									onClick={() => open(column)}
								>
									විවෘත කරන්න ➜
								</button>
							)}
							<button
								type="button"
								className="snack-give"
								data-given={given[column] || undefined}
								disabled={demo || given[column]}
								aria-label={`${PLACE_NAMES[placeName]} තැටියෙන් ${lower[column]} ක් දෙන්න`}
								onClick={() => give(column)}
							>
								{given[column]
									? `✓ ${lower[column]}`
									: `${lower[column]} ක් දෙන්න`}
							</button>
						</div>
					))}
				</div>
			)}
			{!demo && (opens.length > 0 || given.some(Boolean)) && (
				<button type="button" className="snack-again" onClick={startOver}>
					↺ මුල ඉඳන්
				</button>
			)}
		</div>
	);
}
