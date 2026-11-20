import type { ReactNode } from "react";
import { centsOf, rupeesOf } from "./shopRules";
import { shopSounds } from "./shopSounds";

const two = (cents: number) => String(cents).padStart(2, "0");

/**
 * The cash register's sum in two columns, රු. and සත, worked cents first. Adding: when the cents
 * reach 100, "සත 100 → රු. 1" carries one rupee over. Subtracting: when the cents are too few,
 * "රු. 1 → සත 100" opens one rupee first. Nothing is checked here.
 */
export function MoneyBoard({
	operation,
	left,
	right,
	exchanged,
	cents,
	disabled,
	title,
	rupeesCell,
	centsCell,
	onExchange,
}: {
	operation: "add" | "subtract";
	left: number;
	right: number;
	exchanged: boolean;
	/** The cents the child has typed so far. */
	cents: number;
	disabled: boolean;
	title: string;
	rupeesCell: ReactNode;
	centsCell: ReactNode;
	onExchange(exchanged: boolean): void;
}) {
	const adding = operation === "add";
	const carried = adding && exchanged;
	const borrowed = !adding && exchanged;
	const canExchange = adding ? cents >= 100 : rupeesOf(left) > 0;
	return (
		<div className="money-board" data-operation={operation}>
			<strong className="money-board-title">{title}</strong>
			<div className="money-sum">
				<span className="sum-sign" />
				<span className="sum-head">රු.</span>
				<span className="sum-head">සත</span>
				<span className="sum-sign" />
				<span className="sum-carry">
					{carried && (
						<button
							type="button"
							className="sum-carry-chip"
							disabled={disabled}
							aria-label="රු. 1 ආපහු සතවලට"
							onClick={() => {
								shopSounds.play("back");
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
							<s>{rupeesOf(left)}</s> {rupeesOf(left) - 1}
						</>
					) : (
						rupeesOf(left)
					)}
				</span>
				<span className="sum-cell">
					{borrowed ? (
						<>
							<s>{two(centsOf(left))}</s> {centsOf(left) + 100}
						</>
					) : (
						two(centsOf(left))
					)}
				</span>
				<span className="sum-sign">{adding ? "+" : "−"}</span>
				<span className="sum-cell">{rupeesOf(right)}</span>
				<span className="sum-cell">{two(centsOf(right))}</span>
				<span className="sum-line" />
				<span className="sum-sign">=</span>
				<span className="sum-answer">{rupeesCell}</span>
				<span className="sum-answer">
					{carried ? (
						<strong className="sum-cents-left">
							{two(Math.max(0, cents - 100))}
						</strong>
					) : (
						centsCell
					)}
				</span>
			</div>
			<button
				type="button"
				className="money-exchange"
				disabled={disabled || exchanged || !canExchange}
				onClick={() => {
					shopSounds.play("exchange");
					onExchange(true);
				}}
			>
				{adding ? "🔁 සත 100 → රු. 1" : "🔁 රු. 1 → සත 100"}
			</button>
			{borrowed && !disabled && (
				<button
					type="button"
					className="money-undo"
					aria-label="රු. 1 ආපහු"
					onClick={() => {
						shopSounds.play("back");
						onExchange(false);
					}}
				>
					↩
				</button>
			)}
		</div>
	);
}
