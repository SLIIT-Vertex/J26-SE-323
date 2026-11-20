import type { ReactNode } from "react";
import { kilogramsOf, gramsOf } from "./weighRules";
import { weighSounds } from "./weighSounds";

/**
 * A cart sum in two columns, kg and g, worked grams first. Adding: when the grams reach 1000,
 * "1000 g → 1 kg" carries one kilogram over. Unloading: when the grams are too few, "1 kg → 1000 g"
 * opens one kilogram first. Nothing is checked here.
 */
export function MassBoard({
	operation,
	left,
	right,
	exchanged,
	grams,
	disabled,
	title,
	kilogramsCell,
	gramsCell,
	onExchange,
}: {
	operation: "add" | "subtract";
	left: number;
	right: number;
	exchanged: boolean;
	/** The grams the child has typed so far. */
	grams: number;
	disabled: boolean;
	title: string;
	kilogramsCell: ReactNode;
	gramsCell: ReactNode;
	onExchange(exchanged: boolean): void;
}) {
	const adding = operation === "add";
	const carried = adding && exchanged;
	const borrowed = !adding && exchanged;
	const canExchange = adding ? grams >= 1000 : kilogramsOf(left) > 0;
	return (
		<div className="mass-board" data-operation={operation}>
			<strong className="mass-board-title">{title}</strong>
			<div className="mass-sum">
				<span className="sum-sign" />
				<span className="sum-head">kg</span>
				<span className="sum-head">g</span>
				<span className="sum-sign" />
				<span className="sum-carry">
					{carried && (
						<button
							type="button"
							className="sum-carry-chip"
							disabled={disabled}
							aria-label="1 kg ආපහු ග්‍රෑම්වලට"
							onClick={() => {
								weighSounds.play("back");
								onExchange(false);
							}}
						>
							+1
						</button>
					)}
				</span>
				<span className="sum-carry" />
				<span className="sum-sign" />
				<span className="sum-cell">
					{borrowed ? (
						<>
							<s>{kilogramsOf(left)}</s> {kilogramsOf(left) - 1}
						</>
					) : (
						kilogramsOf(left)
					)}
				</span>
				<span className="sum-cell">
					{borrowed ? (
						<>
							<s>{gramsOf(left)}</s> {gramsOf(left) + 1000}
						</>
					) : (
						gramsOf(left)
					)}
				</span>
				<span className="sum-sign">{adding ? "+" : "−"}</span>
				<span className="sum-cell">{kilogramsOf(right)}</span>
				<span className="sum-cell">{gramsOf(right)}</span>
				<span className="sum-line" />
				<span className="sum-sign">=</span>
				<span className="sum-answer">{kilogramsCell}</span>
				<span className="sum-answer">
					{carried ? (
						<strong className="sum-g-left">{Math.max(0, grams - 1000)}</strong>
					) : (
						gramsCell
					)}
				</span>
			</div>
			<button
				type="button"
				className="mass-exchange"
				disabled={disabled || exchanged || !canExchange}
				onClick={() => {
					weighSounds.play("exchange");
					onExchange(true);
				}}
			>
				{adding ? "🔁 1000 g → 1 kg" : "🔁 1 kg → 1000 g"}
			</button>
			{borrowed && !disabled && (
				<button
					type="button"
					className="mass-undo"
					aria-label="1 kg ආපහු"
					onClick={() => {
						weighSounds.play("back");
						onExchange(false);
					}}
				>
					↩
				</button>
			)}
		</div>
	);
}
