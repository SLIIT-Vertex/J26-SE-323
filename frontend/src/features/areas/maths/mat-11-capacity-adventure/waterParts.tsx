import type { ReactNode } from "react";
import { type WaterArtKey, waterArtReady, waterArtUrl } from "./waterArt";
import { waterText } from "./waterRules";
import { waterSounds } from "./waterSounds";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: WaterArtKey;
	className?: string;
}) {
	return waterArtReady(art) ? (
		<img className={className} src={waterArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} water-shape`} data-art={art} />
	);
}

/** A measuring jug of one size, its size written on it, the water drawn at `level` (0–1). */
export function Jug({
	size,
	level = 1,
	className,
}: {
	size: number;
	level?: number;
	className?: string;
}) {
	return (
		<span className={`jug ${className ?? ""}`} data-size={size}>
			<span
				className="jug-water"
				style={{ height: `${Math.round(level * 72)}%` }}
			/>
			<Art art="jug" className="jug-art" />
			<b className="jug-label">{waterText(size)}</b>
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
						waterSounds.play("key");
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
					waterSounds.play("back");
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
				waterSounds.play("tap");
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
