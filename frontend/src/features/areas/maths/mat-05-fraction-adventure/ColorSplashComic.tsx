import { type CSSProperties, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { PAINTS } from "./bookArt";
import { Art, Frac, PaintPots, Sheet, Splat } from "./bookParts";
import {
	type BookPage,
	pageFraction,
	partsResponse,
	tableResponse,
} from "./bookRules";
import { bloomNote, bookSounds } from "./bookSounds";

type Painting = { painted: Set<number>; colours: Map<number, string> };

/**
 * Flowers per row. A row never divides the garden evenly (12 flowers are rows of 5, 5 and 2), so
 * the rows never show a half or a quarter: the garden itself does not give the answer away.
 */
export function gardenColumns(total: number): number {
	// Small gardens use rows of 5 so the last row is never a lonely flower or two.
	const sizes = total <= 12 ? [5, 7, 3] : [7, 6, 5];
	for (const columns of sizes)
		if (columns < total && total % columns !== 0) return columns;
	return Math.max(1, total);
}
const blank = (): Painting => ({ painted: new Set(), colours: new Map() });

/**
 * The Color Splash Comic: Pipi asks for a fraction of the page and the child paints exactly that
 * much. The quarter garden is three pages on the same flowers (1/4, then 2/4, then 3/4); the tenth
 * panels are one page. Painting shows no right or wrong; the comic comes alive only after the page
 * is finished and checked.
 */
export function ColorSplashComic({
	page,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	page: BookPage;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const pageCount = page.kind === "quarter_table" ? 3 : 1;
	const [paintings, setPaintingsState] = useState<Painting[]>(() =>
		Array.from({ length: pageCount }, blank),
	);
	const current = useRef(paintings);
	const setPaintings = (next: Painting[]) => {
		current.current = next;
		setPaintingsState(next);
	};
	const [step, setStep] = useState(0);
	const [colour, setColour] = useState<string>(PAINTS[0]);
	const playing = outcome === "playing";
	const response =
		page.kind === "quarter_table"
			? tableResponse(
					page.total,
					paintings.map((painting) => painting.painted),
				)
			: partsResponse(page, paintings[0]?.painted ?? new Set());
	const [n, d] = pageFraction(page, step);
	const painting = paintings[step] ?? blank();

	const toggle = (spot: number) => {
		if (!playing) return;
		const pages = current.current.map((item) => ({
			painted: new Set(item.painted),
			colours: new Map(item.colours),
		}));
		const here = pages[step];
		if (!here) return;
		evidence.note("digit", step * 100 + spot);
		if (here.painted.has(spot)) {
			here.painted.delete(spot);
			here.colours.delete(spot);
			bookSounds.play("back", { volume: 0.6 });
		} else {
			here.painted.add(spot);
			here.colours.set(spot, colour);
			bookSounds.play("paint");
			bloomNote(here.painted.size);
		}
		setPaintings(pages);
	};
	const turn = (to: number) => {
		if (to < 0 || to >= pageCount) return;
		bookSounds.play("page");
		setStep(to);
	};

	const instruction =
		outcome === "correct" ? (
			"නියමයි! චිත්‍රය පණ ලැබුවා!"
		) : outcome === "wrong" ? (
			"අපොයි! පාට ගණන ටිකක් පැටලුණා."
		) : (
			<>
				{returning ? "අලුත් පිටුවක්! " : ""}
				{page.kind === "quarter_table" ? `මල් ${page.total}න් ` : "කොටස් 10න් "}
				<Frac n={n} d={d} /> ක් පාට කරමු!
			</>
		);

	return (
		<div className="comic" data-outcome={outcome}>
			<Art art="pipi" className="comic-pipi" />
			<Art art="nimoPainter" className="comic-nimo" />
			<div className="comic-book">
				<p className="comic-ask" role="status">
					{instruction}
				</p>
				{page.kind === "quarter_table" ? (
					<div
						className="comic-garden"
						style={
							{
								"--flowers": gardenColumns(page.total),
								"--flower": page.total > 16 ? 124 : 150,
							} as CSSProperties
						}
					>
						{Array.from({ length: page.total }, (_, flower) => {
							const painted = painting.painted.has(flower);
							return (
								<button
									type="button"
									// biome-ignore lint/suspicious/noArrayIndexKey: flower order is the identity.
									key={flower}
									className="comic-flower"
									aria-pressed={painted}
									aria-label={`${flower + 1} වන මල`}
									disabled={!playing}
									onClick={() => toggle(flower)}
								>
									{painted && (
										<Splat
											colour={painting.colours.get(flower) ?? colour}
											index={flower}
										/>
									)}
									<Art
										art={painted ? "flowerPainted" : "flowerBlank"}
										className="comic-flower-art"
									/>
								</button>
							);
						})}
					</div>
				) : (
					<div
						className="comic-panels"
						data-shape={page.kind === "tenths" ? page.representation : "strip"}
					>
						<Sheet
							shape={page.kind === "tenths" ? page.representation : "strip"}
							parts={10}
							painted={painting.painted}
							colours={painting.colours}
							disabled={!playing}
							label="කොටස් 10ක චිත්‍රය"
							onPart={toggle}
						/>
					</div>
				)}
				{pageCount > 1 && (
					<div className="comic-pages">
						<button
							type="button"
							className="comic-turn"
							disabled={step === 0}
							onClick={() => turn(step - 1)}
						>
							◀ කලින් පිටුව
						</button>
						<span className="comic-dots" role="status">
							<span className="book-sr-only">{`පිටුව ${step + 1} / ${pageCount}`}</span>
							{Array.from({ length: pageCount }, (_, at) => (
								<span
									// biome-ignore lint/suspicious/noArrayIndexKey: page order is the identity.
									key={at}
									data-here={at === step || undefined}
									data-done={
										(paintings[at]?.painted.size ?? 0) > 0 || undefined
									}
								/>
							))}
						</span>
						<button
							type="button"
							className="comic-turn"
							disabled={step === pageCount - 1}
							onClick={() => turn(step + 1)}
						>
							ඊළඟ පිටුව ▶
						</button>
					</div>
				)}
			</div>
			<PaintPots
				colour={colour}
				disabled={!playing}
				onPick={(paint) => {
					bookSounds.play("pick");
					setColour(paint);
				}}
			/>
			<button
				type="button"
				className="game-action comic-finish"
				disabled={busy || !response || !playing}
				onClick={() => {
					if (!response) return;
					bookSounds.play("book");
					onSubmit(response);
				}}
			>
				චිත්‍රය අවසන්!
			</button>
		</div>
	);
}
