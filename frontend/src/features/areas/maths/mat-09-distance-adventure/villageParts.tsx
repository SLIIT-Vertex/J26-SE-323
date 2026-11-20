import type { ReactNode } from "react";
import {
	type VillageArtKey,
	villageArtReady,
	villageArtUrl,
} from "./villageArt";
import { villageSounds } from "./villageSounds";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: VillageArtKey;
	className?: string;
}) {
	return villageArtReady(art) ? (
		<img className={className} src={villageArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} village-shape`} data-art={art} />
	);
}

/** A big digit dial (0–9): ▲ and ▼ turn it, 9 wraps to 0. */
export function DigitDial({
	value,
	label,
	disabled = false,
	ghost = false,
	onChange,
}: {
	value: number;
	label: string;
	disabled?: boolean;
	/** A help stage: the dial shows the answer faintly. */
	ghost?: boolean;
	onChange(value: number): void;
}) {
	const turn = (step: 1 | -1) => {
		villageSounds.play("tick");
		onChange((value + step + 10) % 10);
	};
	return (
		<span className="digit-dial" data-ghost={ghost || undefined}>
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

/** The digits of a number, `width` long (leading zeros kept). */
export const digitsOf = (value: number, width: number) =>
	String(Math.max(0, value))
		.padStart(width, "0")
		.slice(-width)
		.split("")
		.map(Number);

export const numberOf = (digits: readonly number[]) =>
	digits.reduce((total, digit) => total * 10 + digit, 0);

/** A distance written on a little wooden tag. */
export function DistanceTag({
	km,
	m,
	className,
}: {
	km: number;
	m: number;
	className?: string;
}) {
	return (
		<span className={`distance-tag ${className ?? ""}`}>
			{km} km {m} m
		</span>
	);
}

export type BlockSize = "km" | 100 | 10 | 1;

export const BLOCK_LABEL: Record<BlockSize, string> = {
	km: "1 km",
	100: "100 m",
	10: "10 m",
	1: "1 m",
};

/** One toy road block: a long 1 km brick, or a shorter 100 m, 10 m or 1 m brick. */
export function Block({ size }: { size: BlockSize }) {
	return (
		<span className="toy-block" data-size={size} aria-hidden="true">
			<span className="toy-block-label">{BLOCK_LABEL[size]}</span>
		</span>
	);
}

/** Blocks of one size, drawn up to `max` (the count beside them is always exact). */
export function BlockPile({
	size,
	count,
	max = 10,
	children,
}: {
	size: BlockSize;
	count: number;
	max?: number;
	children?: ReactNode;
}) {
	const shown = Math.min(max, Math.max(0, count));
	return (
		<span className="block-pile" data-size={size}>
			{Array.from({ length: shown }, (_, at) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: blocks of one size are interchangeable.
				<Block key={at} size={size} />
			))}
			<small className="block-count">× {count}</small>
			{children}
		</span>
	);
}
