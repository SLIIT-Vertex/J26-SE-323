import type { CSSProperties } from "react";
import {
	type CafeArtKey,
	cafeArtReady,
	cafeArtUrl,
	cafeEmoji,
	isCafeFile,
	MONSTERS,
	PACK_ART,
} from "./cafeArt";
import {
	type CafeOrder,
	digitsOf,
	PLACE_NAMES,
	type Place,
	type Source,
	workingDigits,
} from "./cafeRules";

/**
 * A picture from the art manifest: an emoji for the small snacks, a file once its art is ready,
 * and a placeholder shape until then.
 */
export function Art({
	art,
	className,
}: {
	art: CafeArtKey;
	className?: string;
}) {
	const emoji = cafeEmoji(art);
	if (emoji)
		return (
			<span className={`${className ?? ""} cafe-emoji`} aria-hidden="true">
				{emoji}
			</span>
		);
	return isCafeFile(art) && cafeArtReady(art) ? (
		<img className={className} src={cafeArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} cafe-shape`} data-art={art} />
	);
}

export type MonsterMood = "idle" | "happy" | "puzzled" | "eating";

/** The three café customers behind the counter. */
export function Monsters({
	mood,
	onTap,
}: {
	mood: MonsterMood;
	onTap?(seat: number): void;
}) {
	return (
		<div className="cafe-monsters" data-mood={mood}>
			{MONSTERS.map((monster, seat) =>
				onTap ? (
					<button
						type="button"
						key={monster.key}
						className="cafe-monster"
						style={
							{ "--seat": seat, "--tone": monster.colour } as CSSProperties
						}
						aria-label={`${monster.name}ට කෑම දෙන්න`}
						onClick={() => onTap(seat)}
					>
						<Art art={monster.key} className="cafe-monster-art" />
					</button>
				) : (
					<span
						key={monster.key}
						className="cafe-monster"
						style={
							{ "--seat": seat, "--tone": monster.colour } as CSSProperties
						}
					>
						<Art art={monster.key} className="cafe-monster-art" />
					</span>
				),
			)}
		</div>
	);
}

/**
 * Two monsters' orders: the child taps the bigger one to put it on top of the order board. The
 * cards never say which is bigger.
 */
export function StoryPick({
	order,
	top,
	disabled = false,
	onPick,
}: {
	order: CafeOrder;
	top: Source | null;
	disabled?: boolean;
	onPick(source: Source): void;
}) {
	if (!order.story) return null;
	return (
		<div className="cafe-story-pick">
			{order.story.quantities.map((quantity) => (
				<button
					type="button"
					key={quantity.source}
					className="cafe-order-card"
					aria-pressed={top === quantity.source}
					disabled={disabled}
					onClick={() => onPick(quantity.source)}
				>
					<span>{quantity.label}</span>
					<strong>{quantity.value}</strong>
				</button>
			))}
		</div>
	);
}

/**
 * The café order board: place headings, the top row (with opened packs crossed out), the bottom
 * row and the answer row. Opening a pack above a column takes one from it and gives ten to the
 * column on its right. Everything is shown as the child set it; nothing here is checked.
 */
export function OrderBoard({
	places,
	top,
	bottom,
	topLabel,
	bottomLabel,
	opens,
	digits,
	selected,
	ghostOpens = [],
	ghostDigits,
	disabled = false,
	onOpen,
	onSelect,
}: {
	places: readonly Place[];
	top: number | null;
	bottom: number | null;
	topLabel: string;
	bottomLabel: string;
	opens: readonly number[];
	digits: ReadonlyArray<number | null>;
	selected?: number | null;
	ghostOpens?: readonly number[];
	ghostDigits?: readonly number[];
	disabled?: boolean;
	onOpen?(column: number): void;
	onSelect?(column: number): void;
}) {
	const width = places.length;
	const upper = top === null ? null : digitsOf(top, width);
	const lower = bottom === null ? null : digitsOf(bottom, width);
	const working = upper ? workingDigits(upper, opens) : null;
	return (
		<div className="cafe-board" style={{ "--columns": width } as CSSProperties}>
			<span className="cafe-board-label" />
			{places.map((place) => (
				<span key={place} className="cafe-board-place">
					{PLACE_NAMES[place]}
				</span>
			))}
			<span className="cafe-board-label" />
			{places.map((place, column) =>
				column < width - 1 && onOpen ? (
					<button
						type="button"
						key={place}
						className="cafe-open"
						aria-pressed={opens.includes(column)}
						data-ghost={ghostOpens.includes(column) || undefined}
						disabled={disabled || !upper}
						aria-label={`${PLACE_NAMES[place]} තීරුවෙන් පැකට්ටුවක් විවෘත කරන්න`}
						onClick={() => onOpen(column)}
					>
						<Art art={PACK_ART[place]} className="cafe-open-art" />
					</button>
				) : (
					<span key={place} />
				),
			)}
			<span className="cafe-board-label">{topLabel}</span>
			{places.map((place, column) => {
				const changed = working && upper && working[column] !== upper[column];
				return (
					<span
						key={place}
						className="cafe-board-digit"
						data-changed={changed || undefined}
					>
						{changed && <small>{working?.[column]}</small>}
						<span>{upper ? upper[column] : "?"}</span>
					</span>
				);
			})}
			<span className="cafe-board-label">− {bottomLabel}</span>
			{places.map((place, column) => (
				<span key={place} className="cafe-board-digit">
					{lower ? lower[column] : "?"}
				</span>
			))}
			<span className="cafe-board-label">ඉතිරි</span>
			{places.map((place, column) => {
				const digit = digits[column] ?? null;
				const ghost = digit === null ? ghostDigits?.[column] : undefined;
				return (
					<button
						type="button"
						key={place}
						className="cafe-answer"
						aria-pressed={selected === column}
						data-ghost={ghost !== undefined || undefined}
						disabled={disabled || !onSelect}
						aria-label={`${PLACE_NAMES[place]} තීරුවේ ඉතිරිය (${digit ?? "හිස්"})`}
						onClick={() => onSelect?.(column)}
					>
						{digit ?? ghost ?? ""}
					</button>
				);
			})}
		</div>
	);
}

/** Ten big digit buttons for the answer row. */
export function DigitPad({
	disabled,
	onDigit,
}: {
	disabled: boolean;
	onDigit(digit: number): void;
}) {
	return (
		<div className="cafe-pad">
			{Array.from({ length: 10 }, (_, digit) => (
				<button
					type="button"
					// biome-ignore lint/suspicious/noArrayIndexKey: the digit is the identity.
					key={digit}
					disabled={disabled}
					onClick={() => onDigit(digit)}
				>
					{digit}
				</button>
			))}
		</div>
	);
}

/** A pile of up to `max` snacks of one kind (the number beside it shows the full count). */
export function Pile({
	art,
	count,
	max = 19,
}: {
	art: CafeArtKey;
	count: number;
	max?: number;
}) {
	const pieces = Array.from(
		{ length: Math.min(max, Math.max(0, count)) },
		(_, at) => `piece-${at}`,
	);
	return (
		<>
			{pieces.map((id) => (
				<Art key={id} art={art} className="snack-piece" />
			))}
		</>
	);
}
