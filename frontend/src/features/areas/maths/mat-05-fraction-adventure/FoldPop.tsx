import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { PAINTS } from "./bookArt";
import { Art, Frac, PaintPots, Sheet, type SheetShape } from "./bookParts";
import {
	type BookPage,
	foldsNeeded,
	pageFraction,
	partCount,
	partsResponse,
} from "./bookRules";
import { bloomNote, bookSounds } from "./bookSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const FOLD_MS = 450;

/** How many parts the sheet shows after `folds` folds. */
function partsAfter(page: BookPage, folds: number): number {
	if (folds <= 0) return 1;
	if (page.kind === "tenths") return 10;
	return folds === 1 && partCount(page) === 4 ? 2 : partCount(page);
}

/**
 * Fold & Pop (the most visible help): one sheet of paper. Each fold shows the equal parts
 * (a whole → halves → quarters, or a strip folded into ten), then the child paints the parts
 * Pipi asks for. Painting exactly that many makes a paper butterfly pop out of the page.
 */
export function FoldPop({
	page,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	page: BookPage;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const needed = foldsNeeded(page);
	const [folds, setFolds] = useState(demo ? needed : 0);
	const [folding, setFolding] = useState(false);
	const [n, d] = pageFraction(page);
	const [painted, setPainted] = useState<Set<number>>(
		() => new Set(demo ? Array.from({ length: n }, (_, at) => at) : []),
	);
	const [colours, setColours] = useState<Map<number, string>>(
		() =>
			new Map(
				demo ? Array.from({ length: n }, (_, at) => [at, PAINTS[0]]) : [],
			),
	);
	const [colour, setColour] = useState<string>(PAINTS[0]);
	const shape: SheetShape =
		page.kind === "tenths"
			? page.representation
			: page.kind === "shading"
				? page.representation
				: "rectangle";
	const folded = folds >= needed;
	const popped = folded && painted.size === n;

	useEffect(() => {
		onResponse(demo ? null : partsResponse(page, painted));
	}, [demo, page, painted, onResponse]);

	const fold = () => {
		if (demo || folded || folding) return;
		evidence.note("move");
		bookSounds.play("fold");
		setFolding(true);
		setTimeout(() => {
			setFolds((count) => count + 1);
			setFolding(false);
		}, FOLD_MS);
	};
	const paint = (part: number) => {
		if (demo || !folded) return;
		evidence.note("digit", part);
		const next = new Set(painted);
		const tints = new Map(colours);
		if (next.has(part)) {
			next.delete(part);
			tints.delete(part);
			bookSounds.play("back", { volume: 0.6 });
		} else {
			next.add(part);
			tints.set(part, colour);
			bookSounds.play("paint");
			bloomNote(next.size);
			if (next.size === n) bookSounds.play("magic", { delay: 0.25 });
		}
		setPainted(next);
		setColours(tints);
	};

	const parts = partsAfter(page, folds);
	const foldLabel =
		page.kind === "tenths"
			? "දහයට නමමු!"
			: folds === 0
				? "දෙකට නමමු!"
				: "ආයෙත් දෙකට නමමු!";
	const message = demo ? (
		<>
			සමාන කොටස් {d}න් <Frac n={n} d={d} /> ක් පාට කළා.
		</>
	) : !folded ? (
		"කඩදාසිය සමාන කොටස්වලට නමමු!"
	) : popped ? (
		"මැජික්! කඩදාසි සමනලයා පණ ලැබුවා!"
	) : (
		<>
			කඩදාසි කොටසින් <Frac n={n} d={d} /> ක් පාට කරමු!
		</>
	);

	return (
		<div
			className="fold-pop"
			data-demo={demo || undefined}
			data-folding={folding || undefined}
		>
			<p className="book-message" role="status">
				{message}
			</p>
			<div className="fold-stage">
				<Sheet
					shape={shape}
					parts={parts}
					painted={folded ? painted : new Set()}
					colours={colours}
					ghost={
						hint && folded && !demo
							? Array.from({ length: n }, (_, at) => at)
							: []
					}
					disabled={demo || !folded}
					label={`කොටස් ${parts}ක කඩදාසිය`}
					onPart={folded ? paint : undefined}
				/>
				{popped && <Art art="butterfly" className="fold-butterfly" />}
				{popped && <Art art="magic" className="fold-magic" />}
			</div>
			<div className="fold-tools">
				{!folded && !demo && (
					<button
						type="button"
						className="fold-button"
						data-ghost={hint || undefined}
						disabled={folding}
						onClick={fold}
					>
						{foldLabel}
					</button>
				)}
				{folded && !demo && (
					<PaintPots
						colour={colour}
						onPick={(next) => {
							bookSounds.play("pick");
							setColour(next);
						}}
					/>
				)}
			</div>
		</div>
	);
}
