const CELEBRATION_ASSET =
	"/curriculum/game/shared/child-celebrating-stars.png";

export function AdventureBackButton({ onClick }: { onClick(): void }) {
	return (
		<button
			type="button"
			className="text-action adventure-back-action"
			aria-label="ආපසු"
			onClick={onClick}
		>
			<svg aria-hidden="true" viewBox="0 0 24 24">
				<path d="m15 18-6-6 6-6" />
			</svg>
		</button>
	);
}

export function SuccessCelebration() {
	return (
		<img
			className="success-celebration-image"
			src={CELEBRATION_ASSET}
			alt=""
		/>
	);
}
