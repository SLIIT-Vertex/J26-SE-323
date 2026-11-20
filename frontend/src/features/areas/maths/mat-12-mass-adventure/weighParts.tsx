import type { CSSProperties, ReactNode } from "react";
import { type WeighArtKey, weighArtReady, weighArtUrl } from "./weighArt";
import { massText } from "./weighRules";
import { weighSounds } from "./weighSounds";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: WeighArtKey;
	className?: string;
}) {
	return weighArtReady(art) ? (
		<img className={className} src={weighArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} weigh-shape`} data-art={art} />
	);
}

const WEIGHT_COLOUR: Record<number, string> = {
	5: "#9aa5b1",
	10: "#7f8c8d",
	20: "#e67e22",
	50: "#f1c40f",
	100: "#e74c3c",
	200: "#5cb85c",
	500: "#3d8be0",
	1000: "#9b59b6",
	2000: "#16a085",
	5000: "#34495e",
};

/** A standard weight piece: a coloured block with a knob, its weight on a label. */
export function Weight({
	grams,
	className,
}: {
	grams: number;
	className?: string;
}) {
	const size = Math.round(54 + Math.log10(grams) * 22);
	return (
		<span
			className={`weight ${className ?? ""}`}
			data-grams={grams}
			style={
				{
					"--weight": WEIGHT_COLOUR[grams] ?? "#888",
					"--size": size,
				} as CSSProperties
			}
		>
			<i className="weight-knob" />
			<b className="weight-label">{massText(grams)}</b>
		</span>
	);
}

/** A mystery box with its weight on a tag (or "?" while unknown). */
export function Box({
	grams,
	className,
}: {
	grams: number | null;
	className?: string;
}) {
	return (
		<span className={`box ${className ?? ""}`}>
			<Art art="box" className="box-art" />
			<b className="box-tag">{grams === null ? "?" : massText(grams)}</b>
		</span>
	);
}

/** Nimo with a speech bubble: every instruction and every reaction is said by him. */
export function NimoSays({
	mood = "idle",
	children,
	className,
}: {
	mood?: "idle" | "cheer" | "think";
	children: ReactNode;
	className?: string;
}) {
	return (
		<div className={`nimo-says ${className ?? ""}`} data-mood={mood}>
			<Art
				art={
					mood === "cheer"
						? "nimoCheer"
						: mood === "think"
							? "nimoThink"
							: "nimoIdle"
				}
				className="nimo-says-art"
			/>
			<p className="nimo-says-bubble" role="status">
				{children}
			</p>
		</div>
	);
}

/** A cash-register keypad: digits, and ⌫ to rub one out. */
export function Keypad({
	disabled = false,
	onDigit,
	onRubOut,
}: {
	disabled?: boolean;
	onDigit(digit: number): void;
	onRubOut(): void;
}) {
	return (
		<div className="keypad" data-locked={disabled || undefined}>
			{[7, 8, 9, 4, 5, 6, 1, 2, 3, 0].map((digit) => (
				<button
					key={digit}
					type="button"
					className="keypad-key"
					disabled={disabled}
					onClick={() => {
						weighSounds.play("key");
						onDigit(digit);
					}}
				>
					{digit}
				</button>
			))}
			<button
				type="button"
				className="keypad-key keypad-rub"
				disabled={disabled}
				aria-label="මකන්න"
				onClick={() => {
					weighSounds.play("back");
					onRubOut();
				}}
			>
				⌫
			</button>
		</div>
	);
}

/** A cell of the bill the keypad types into. */
export function AmountCell({
	id,
	value,
	selected,
	disabled = false,
	label,
	unit,
	onSelect,
}: {
	id: string;
	value: string;
	selected: boolean;
	disabled?: boolean;
	label: string;
	unit?: string;
	onSelect(id: string): void;
}) {
	return (
		<button
			type="button"
			className="amount-cell"
			data-selected={selected || undefined}
			disabled={disabled}
			aria-label={label}
			onClick={() => {
				weighSounds.play("tap");
				onSelect(id);
			}}
		>
			{unit && <small>{unit}</small>}
			<strong>{value === "" ? "?" : value}</strong>
		</button>
	);
}

/** Types a digit into a cell's text (at most `width` digits, no leading zeros). */
export const typeDigit = (text: string, digit: number, width: number) =>
	text.length >= width
		? text
		: text === "0"
			? String(digit)
			: `${text}${digit}`;
