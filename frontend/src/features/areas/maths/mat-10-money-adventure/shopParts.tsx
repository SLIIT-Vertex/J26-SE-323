import type { CSSProperties, ReactNode } from "react";
import {
	kitUrl,
	NOTES,
	type ShopArtKey,
	shopArtReady,
	shopArtUrl,
} from "./shopArt";
import { DENOMINATION_BY_ID } from "./shopRules";
import { shopSounds } from "./shopSounds";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: ShopArtKey;
	className?: string;
}) {
	return shopArtReady(art) ? (
		<img className={className} src={shopArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} shop-shape`} data-art={art} />
	);
}

const COIN_FACE: Record<string, string> = {
	"coin-1": "coin-silver",
	"coin-2": "coin-copper",
	"coin-5": "coin-twotone",
	"coin-10": "coin-gold",
};
const NOTE_COLOUR: Record<string, string> = {
	"note-20": "#e85d9a",
	"note-50": "#3d8be0",
	"note-100": "#f08a24",
	"note-500": "#9b59b6",
	"note-1000": "#2fa35a",
	"note-5000": "#d9a514",
};

/** A Sri Lankan coin or note (play money that looks like the real one), its value written on it. */
export function Money({ id, className }: { id: string; className?: string }) {
	const row = DENOMINATION_BY_ID[id];
	if (!row) return null;
	const rupees = row.value / 100;
	if (row.type === "coin")
		return (
			<span className={`money money-coin ${className ?? ""}`} data-id={id}>
				<img src={kitUrl(COIN_FACE[id] ?? "coin-silver")} alt="" />
				<b>{rupees}</b>
			</span>
		);
	return (
		<span
			className={`money money-note ${className ?? ""}`}
			data-id={id}
			style={{ "--note": NOTE_COLOUR[id] ?? "#888" } as CSSProperties}
		>
			{NOTES[id] && shopArtReady(NOTES[id]) && (
				<img className="money-note-art" src={shopArtUrl(NOTES[id])} alt="" />
			)}
			<b>රු. {rupees}</b>
		</span>
	);
}

/** A little coin of cents (සත), used in the cash box's cents drawer. */
export function CentCoin({ value }: { value: 10 | 1 }) {
	return (
		<span className="money money-coin money-cent" data-cent={value}>
			<img src={kitUrl(value === 10 ? "coin-blue" : "coin-copper")} alt="" />
			<b>
				{value}
				<small>සත</small>
			</b>
		</span>
	);
}

/** Pieces of one kind, drawn up to `max` (the count beside them is always exact). */
export function Pile({
	count,
	max = 4,
	kind = "coin",
	children,
}: {
	count: number;
	max?: number;
	/** Notes overlap more, so only the top one's value shows in full. */
	kind?: "coin" | "note";
	children: ReactNode;
}) {
	const shown = Math.min(max, Math.max(0, count));
	return (
		<span className="money-pile" data-kind={kind}>
			{Array.from({ length: shown }, (_, at) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: pieces of one kind are interchangeable.
				<span key={at} className="money-pile-piece">
					{children}
				</span>
			))}
			<small className="money-pile-count">× {count}</small>
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
						shopSounds.play("key");
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
					shopSounds.play("back");
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
				shopSounds.play("tap");
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
