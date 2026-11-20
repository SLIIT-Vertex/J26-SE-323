import type { CSSProperties } from "react";
import {
	alienUrl,
	type Colour,
	colourAt,
	type SpaceArtKey,
	spaceArtReady,
	spaceArtUrl,
	ufoUrl,
} from "./spaceArt";
import { spaceSounds } from "./spaceSounds";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: SpaceArtKey;
	className?: string;
}) {
	return spaceArtReady(art) ? (
		<img className={className} src={spaceArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} space-shape`} data-art={art} />
	);
}

export function Alien({
	colour,
	className,
}: {
	colour: Colour;
	className?: string;
}) {
	return (
		<img
			className={`space-alien ${className ?? ""}`}
			src={alienUrl(colour)}
			alt=""
		/>
	);
}

export function Ufo({
	colour,
	className,
}: {
	colour: Colour;
	className?: string;
}) {
	return (
		<img
			className={`space-ufo ${className ?? ""}`}
			src={ufoUrl(colour)}
			alt=""
		/>
	);
}

export type BundleSize = 100 | 10 | 1;

/**
 * One bundle: a single alien (or star), a shuttle of ten, or a station of a hundred. The
 * number on it is the bundle's size, so a child can count by it.
 */
export function Bundle({
	size,
	kind,
	colour = 0,
}: {
	size: BundleSize;
	kind: "alien" | "star";
	colour?: number;
}) {
	if (size === 1)
		return kind === "alien" ? (
			<Alien colour={colourAt(colour)} className="bundle-one" />
		) : (
			<span className="bundle-star" aria-hidden="true">
				⭐
			</span>
		);
	return (
		<span
			className="bundle"
			data-size={size}
			data-kind={kind}
			aria-hidden="true"
		>
			<Art
				art={kind === "star" ? "starBundle" : size === 100 ? "station" : "shuttle"}
				className="bundle-ship"
			/>
			<strong className="bundle-size">{size}</strong>
		</span>
	);
}

/** Bundles of one size, drawn up to `max` (the count beside them is always exact). */
export function BundlePile({
	size,
	count,
	kind,
	max = 9,
}: {
	size: BundleSize;
	count: number;
	kind: "alien" | "star";
	max?: number;
}) {
	const shown = Math.min(max, Math.max(0, count));
	return (
		<span className="bundle-pile" data-size={size}>
			{Array.from({ length: shown }, (_, at) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: bundles of one size are interchangeable.
				<Bundle key={at} size={size} kind={kind} colour={at} />
			))}
			{count > shown && <b className="bundle-more">+{count - shown}</b>}
			<small className="bundle-count">× {count}</small>
		</span>
	);
}

/** A big digit dial (0–9): ▲ and ▼ turn it, 9 wraps to 0. */
export function DigitDial({
	value,
	label,
	icon,
	disabled = false,
	onChange,
}: {
	value: number;
	label: string;
	icon?: React.ReactNode;
	disabled?: boolean;
	onChange(value: number): void;
}) {
	const turn = (step: 1 | -1) => {
		spaceSounds.play("tick");
		onChange((value + step + 10) % 10);
	};
	return (
		<span className="digit-dial">
			<small>
				{icon}
				{label}
			</small>
			<button
				type="button"
				disabled={disabled}
				aria-label={`${label} වැඩි කරන්න`}
				onClick={() => turn(1)}
			>
				▲
			</button>
			<strong className="digit-dial-value">{value}</strong>
			<button
				type="button"
				disabled={disabled}
				aria-label={`${label} අඩු කරන්න`}
				onClick={() => turn(-1)}
			>
				▼
			</button>
		</span>
	);
}

/** A row of numbered UFOs with whatever each carries. */
export function UfoRow({
	count,
	labels,
	launched = false,
	wobble = false,
	children,
}: {
	count: number;
	labels: ReadonlyArray<string | number>;
	launched?: boolean;
	wobble?: boolean;
	children?(index: number): React.ReactNode;
}) {
	return (
		<div
			className="ufo-row"
			style={{ "--ufos": count } as CSSProperties}
			data-launched={launched || undefined}
			data-wobble={wobble || undefined}
		>
			{Array.from({ length: count }, (_, index) => `ufo-${index}`).map(
				(id, index) => (
					<div
						key={id}
						className="ufo-slot"
						style={{ "--at": index } as CSSProperties}
					>
						<div className="ufo-cargo">{children?.(index)}</div>
						<Ufo colour={colourAt(index)} />
						<span className="ufo-label">{labels[index] ?? "?"}</span>
					</div>
				),
			)}
		</div>
	);
}
