import type { ReactNode } from "react";
import { litresOf, restOf } from "./waterRules";
import { waterSounds } from "./waterSounds";

/**
 * A tank sum in two columns, l and ml, worked millilitres first. Adding: when the millilitres reach
 * 1000, "1000 ml → 1 l" carries one litre over. Taking away: when the millilitres are too few,
 * "1 l → 1000 ml" opens one litre first. Nothing is checked here.
 */
export function CapacityBoard({
	operation,
	left,
	right,
	exchanged,
	millilitres,
	disabled,
	title,
	litresCell,
	millilitresCell,
	onExchange,
}: {
	operation: "add" | "subtract";
	left: number;
	right: number;
	exchanged: boolean;
	/** The millilitres the child has typed so far. */
	millilitres: number;
	disabled: boolean;
	title: string;
	litresCell: ReactNode;
	millilitresCell: ReactNode;
	onExchange(exchanged: boolean): void;
}) {
	const adding = operation === "add";
	const carried = adding && exchanged;
	const borrowed = !adding && exchanged;
	const canExchange = adding ? millilitres >= 1000 : litresOf(left) > 0;
	return (
		<div className="capacity-board" data-operation={operation}>
			<strong className="capacity-board-title">{title}</strong>
			<div className="capacity-sum">
				<span className="sum-sign" />
				<span className="sum-head">l</span>
				<span className="sum-head">ml</span>
				<span className="sum-sign" />
				<span className="sum-carry">
					{carried && (
						<button
							type="button"
							className="sum-carry-chip"
							disabled={disabled}
							aria-label="1 l ආපහු මිලිලීටර්වලට"
							onClick={() => {
								waterSounds.play("back");
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
							<s>{litresOf(left)}</s> {litresOf(left) - 1}
						</>
					) : (
						litresOf(left)
					)}
				</span>
				<span className="sum-cell">
					{borrowed ? (
						<>
							<s>{restOf(left)}</s> {restOf(left) + 1000}
						</>
					) : (
						restOf(left)
					)}
				</span>
				<span className="sum-sign">{adding ? "+" : "−"}</span>
				<span className="sum-cell">{litresOf(right)}</span>
				<span className="sum-cell">{restOf(right)}</span>
				<span className="sum-line" />
				<span className="sum-sign">=</span>
				<span className="sum-answer">{litresCell}</span>
				<span className="sum-answer">
					{carried ? (
						<strong className="sum-ml-left">
							{Math.max(0, millilitres - 1000)}
						</strong>
					) : (
						millilitresCell
					)}
				</span>
			</div>
			<button
				type="button"
				className="capacity-exchange"
				disabled={disabled || exchanged || !canExchange}
				onClick={() => {
					waterSounds.play("exchange");
					onExchange(true);
				}}
			>
				{adding ? "🔁 1000 ml → 1 l" : "🔁 1 l → 1000 ml"}
			</button>
			{borrowed && !disabled && (
				<button
					type="button"
					className="capacity-undo"
					aria-label="1 l ආපහු"
					onClick={() => {
						waterSounds.play("back");
						onExchange(false);
					}}
				>
					↩
				</button>
			)}
		</div>
	);
}
