import type { CSSProperties } from "react";
import {
	type BookArtKey,
	bookArtReady,
	bookArtUrl,
	PAINTS,
	SPLATS,
} from "./bookArt";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: BookArtKey;
	className?: string;
}) {
	return bookArtReady(art) ? (
		<img className={className} src={bookArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} book-shape`} data-art={art} />
	);
}

/** A fraction written the school way, numerator over denominator. */
export function Frac({ n, d }: { n: number; d: number }) {
	return (
		<span className="book-frac" role="img" aria-label={`${d} න් ${n}`}>
			<span>{n}</span>
			<span>{d}</span>
		</span>
	);
}

/** A paint splat in the given colour (the white splat art, tinted). */
export function Splat({ colour, index }: { colour: string; index: number }) {
	const url = SPLATS[index % SPLATS.length];
	return (
		<span
			className="book-splat"
			aria-hidden="true"
			style={
				{
					"--paint": colour,
					maskImage: `url("${url}")`,
					WebkitMaskImage: `url("${url}")`,
				} as CSSProperties
			}
		/>
	);
}

/** The four paint pots; the brush paints with the chosen one. */
export function PaintPots({
	colour,
	disabled = false,
	onPick,
}: {
	colour: string;
	disabled?: boolean;
	onPick(colour: string): void;
}) {
	return (
		<div className="book-pots">
			{PAINTS.map((paint, index) => (
				<button
					type="button"
					key={paint}
					className="book-pot"
					aria-pressed={colour === paint}
					aria-label={`පාට ${index + 1}`}
					disabled={disabled}
					style={{ "--paint": paint } as CSSProperties}
					onClick={() => onPick(paint)}
				>
					<Splat colour={paint} index={index} />
				</button>
			))}
		</div>
	);
}

export type SheetShape = "rectangle" | "circle" | "strip";

/** The outline of each equal part of a sheet: halves, quarters or tenths. */
function partPaths(shape: SheetShape, parts: number): string[] {
	if (shape === "strip")
		return Array.from({ length: parts }, (_, at) => {
			const width = 1000 / parts;
			return `M${at * width} 0 h${width} v200 h${-width} Z`;
		});
	if (shape === "rectangle") {
		if (parts === 2)
			return ["M0 0 h200 v400 h-200 Z", "M200 0 h200 v400 h-200 Z"];
		return [
			"M0 0 h200 v200 h-200 Z",
			"M200 0 h200 v200 h-200 Z",
			"M0 200 h200 v200 h-200 Z",
			"M200 200 h200 v200 h-200 Z",
		];
	}
	return Array.from({ length: parts }, (_, at) => {
		const angle = (turn: number) =>
			((turn * 360) / parts - 90) * (Math.PI / 180);
		const [x1, y1] = [
			200 + 196 * Math.cos(angle(at)),
			200 + 196 * Math.sin(angle(at)),
		];
		const [x2, y2] = [
			200 + 196 * Math.cos(angle(at + 1)),
			200 + 196 * Math.sin(angle(at + 1)),
		];
		const large = parts === 1 ? 1 : 0;
		return `M200 200 L${x1.toFixed(1)} ${y1.toFixed(1)} A196 196 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z`;
	});
}

/** Where a wedge's tap button sits on a circle sheet (percent of the sheet). */
function wedgeSpot(part: number, parts: number): CSSProperties {
	const middle = (((part + 0.5) * 360) / parts - 90) * (Math.PI / 180);
	const reach = parts <= 2 ? 0.25 : parts <= 4 ? 0.3 : 0.34;
	const size = parts <= 4 ? 34 : 18;
	return {
		left: `${50 + reach * 100 * Math.cos(middle) - size / 2}%`,
		top: `${50 + reach * 100 * Math.sin(middle) - size / 2}%`,
		width: `${size}%`,
		height: `${size}%`,
	};
}

/**
 * A sheet of paper divided into equal parts. Until it is folded (`parts` 1) it is one whole sheet;
 * painted parts take the chosen paint, and faint hint parts show where the answer would be.
 */
export function Sheet({
	shape,
	parts,
	painted,
	colours,
	ghost = [],
	disabled = false,
	label,
	onPart,
}: {
	shape: SheetShape;
	parts: number;
	painted: ReadonlySet<number>;
	colours: ReadonlyMap<number, string>;
	ghost?: readonly number[];
	disabled?: boolean;
	label: string;
	onPart?(part: number): void;
}) {
	const paths = partPaths(shape, parts);
	const view = shape === "strip" ? "0 0 1000 200" : "0 0 400 400";
	return (
		<div className="book-sheet" data-shape={shape} data-parts={parts}>
			<svg viewBox={view} role="img" aria-label={label}>
				{shape === "circle" ? (
					<circle cx="200" cy="200" r="196" className="book-sheet-paper" />
				) : (
					<rect
						width={shape === "strip" ? 1000 : 400}
						height={shape === "strip" ? 200 : 400}
						className="book-sheet-paper"
					/>
				)}
				{paths.map((path, part) => (
					<path
						// biome-ignore lint/suspicious/noArrayIndexKey: the part order is the identity.
						key={part}
						d={path}
						className="book-sheet-part"
						data-painted={painted.has(part) || undefined}
						data-ghost={
							(!painted.has(part) && ghost.includes(part)) || undefined
						}
						style={{ fill: painted.has(part) ? colours.get(part) : undefined }}
					/>
				))}
			</svg>
			{onPart && parts > 1 && (
				<div className="book-sheet-hits" data-shape={shape}>
					{paths.map((_, part) => (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: the part order is the identity.
							key={part}
							className="book-sheet-hit"
							data-part={part}
							aria-pressed={painted.has(part)}
							aria-label={`${part + 1} වන කොටස`}
							disabled={disabled}
							style={shape === "circle" ? wedgeSpot(part, parts) : undefined}
							onClick={() => onPart(part)}
						/>
					))}
				</div>
			)}
		</div>
	);
}
