import { Art, DigitDial, digitsOf, numberOf } from "./villageParts";
import { PARCHMENT_URL } from "./villageArt";
import type { Distance, Operation, Working } from "./villageRules";
import { villageSounds } from "./villageSounds";

const KM_DIGITS = 2;

/** The dial digits of a board: kilometres (2 dials) and metres (4 when adding, else 3). */
export type BoardDigits = { km: number[]; m: number[] };

export const emptyDigits = (operation: Operation): BoardDigits => ({
	km: Array(KM_DIGITS).fill(0),
	m: Array(operation === "add" ? 4 : 3).fill(0),
});

export const digitsOfWorking = (working: Working): BoardDigits => ({
	km: digitsOf(working.km, KM_DIGITS),
	m: digitsOf(working.metres, working.operation === "add" ? 4 : 3),
});

export const workingOf = (
	operation: Operation,
	digits: BoardDigits,
	exchanged: boolean,
): Working => ({
	operation,
	metres: numberOf(digits.m),
	exchanged,
	km: numberOf(digits.km),
});

/**
 * The wooden distance board: the two distances in km and m columns, then the answer dialled
 * metres first. Adding: when the metres reach 1000, "1000 m → 1 km" carries one kilometre over.
 * Subtracting: when the metres are too few, "1 km → 1000 m" opens one kilometre first. Nothing is
 * checked here.
 */
export function DistanceBoard({
	operation,
	left,
	right,
	digits,
	exchanged,
	disabled,
	title,
	onDigits,
	onExchange,
}: {
	operation: Operation;
	left: Distance;
	right: Distance;
	digits: BoardDigits;
	exchanged: boolean;
	disabled: boolean;
	title: string;
	onDigits(digits: BoardDigits, column: number): void;
	onExchange(exchanged: boolean): void;
}) {
	const metres = numberOf(digits.m);
	const adding = operation === "add";
	const canExchange = adding ? metres >= 1000 : left.km > 0;
	const borrowed = !adding && exchanged;
	const setDigit = (part: "km" | "m", at: number, value: number) =>
		onDigits(
			{
				...digits,
				[part]: digits[part].map((digit, place) =>
					place === at ? value : digit,
				),
			},
			part === "km" ? at : KM_DIGITS + at,
		);

	return (
		<div
			className="distance-board"
			data-operation={operation}
			data-locked={disabled || undefined}
			style={{ backgroundImage: `url("${PARCHMENT_URL}")` }}
		>
			<div className="board-head">
				<Art art="compass" className="board-compass" />
				<strong>{title}</strong>
			</div>
			<div className="board-sum">
				<span className="board-sign" />
				<span className="board-col-head">km</span>
				<span className="board-col-head">m</span>
				<span className="board-sign" />
				{adding && exchanged ? (
					<span className="board-carry">
						<button
							type="button"
							className="board-carry-chip"
							disabled={disabled}
							aria-label="1 km ආපහු මීටර්වලට"
							onClick={() => {
								villageSounds.play("back");
								onExchange(false);
							}}
						>
							+1
						</button>
					</span>
				) : (
					<span className="board-carry" />
				)}
				<span className="board-carry" />
				<span className="board-sign" />
				<span className="board-cell">
					{borrowed ? (
						<>
							<s>{left.km}</s> {left.km - 1}
						</>
					) : (
						left.km
					)}
				</span>
				<span className="board-cell">
					{borrowed ? (
						<>
							<s>{left.m}</s> {left.m + 1000}
						</>
					) : (
						left.m
					)}
				</span>
				<span className="board-sign">{adding ? "+" : "−"}</span>
				<span className="board-cell">{right.km}</span>
				<span className="board-cell">{right.m}</span>
				<span className="board-line" />
				<span className="board-sign">=</span>
				<span className="board-dials">
					{digits.km.map((value, at) => (
						<DigitDial
							// biome-ignore lint/suspicious/noArrayIndexKey: the place is the identity.
							key={at}
							label={`km ${at + 1}`}
							value={value}
							disabled={disabled}
							onChange={(next) => setDigit("km", at, next)}
						/>
					))}
				</span>
				<span className="board-dials">
					{adding && exchanged ? (
						<strong className="board-metres-left">{metres - 1000}</strong>
					) : (
						digits.m.map((value, at) => (
							<DigitDial
								// biome-ignore lint/suspicious/noArrayIndexKey: the place is the identity.
								key={at}
								label={`m ${at + 1}`}
								value={value}
								disabled={disabled}
								onChange={(next) => setDigit("m", at, next)}
							/>
						))
					)}
				</span>
			</div>
			<button
				type="button"
				className="board-exchange"
				disabled={disabled || exchanged || !canExchange}
				onClick={() => {
					villageSounds.play("exchange");
					onExchange(true);
				}}
			>
				{adding ? "🔁 1000 m → 1 km" : "🔁 1 km → 1000 m"}
			</button>
			{borrowed && !disabled && (
				<button
					type="button"
					className="board-undo"
					aria-label="1 km ආපහු"
					onClick={() => {
						villageSounds.play("back");
						onExchange(false);
					}}
				>
					↩
				</button>
			)}
		</div>
	);
}
