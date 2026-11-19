import { type LockAction, type LockState, ONES, PLACES } from "./skyRules";

/**
 * The warehouse lock: one digit wheel per place and a carry spark above every place that can
 * receive a carry. The deliveries are not written in columns here; the child works them out.
 */
export function CarryLock({
	lock,
	disabled = false,
	onAction,
}: {
	lock: LockState;
	disabled?: boolean;
	onAction(action: LockAction): void;
}) {
	return (
		<div className="carry-lock">
			<fieldset className="carry-lock-grid">
				<legend>ගබඩා අගුල</legend>
				{PLACES.map((place, index) => (
					<div className="carry-lock-column" key={place}>
						{index !== ONES ? (
							<button
								type="button"
								className="carry-spark"
								data-carry={lock.carries[index]}
								disabled={disabled}
								aria-label={`${place} තැනට ගෙනයාම: ${lock.carries[index]}`}
								onClick={() => onAction({ type: "carry", place: index })}
							>
								{lock.carries[index] ? `+${lock.carries[index]}` : "+"}
							</button>
						) : (
							<span className="carry-spark is-empty" aria-hidden="true" />
						)}
						<span className="carry-lock-place">{place}</span>
						<button
							type="button"
							className="carry-wheel-step"
							disabled={disabled}
							aria-label={`${place} ඉලක්කම වැඩි කරන්න`}
							onClick={() =>
								onAction({ type: "digit", place: index, delta: 1 })
							}
						>
							▲
						</button>
						<strong className="carry-wheel-digit" aria-live="polite">
							{lock.digits[index] ?? "?"}
						</strong>
						<button
							type="button"
							className="carry-wheel-step"
							disabled={disabled}
							aria-label={`${place} ඉලක්කම අඩු කරන්න`}
							onClick={() =>
								onAction({ type: "digit", place: index, delta: -1 })
							}
						>
							▼
						</button>
					</div>
				))}
			</fieldset>
		</div>
	);
}
