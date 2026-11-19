/** A story moment between scenes: Nimo, a title, a line or two and one big button. */
export function GameStoryCard({
	title,
	image,
	lines,
	action,
	busy = false,
	onAction,
	onPress,
}: {
	title: string;
	/** Picture beside the card, usually a Nimo pose. */
	image: string;
	lines: string[];
	action?: string;
	busy?: boolean;
	onAction?(): void;
	/** Runs on the button press before `onAction` (e.g. a click sound). */
	onPress?(): void;
}) {
	return (
		<div className="game-story">
			<img className="game-story-image" src={image} alt="" />
			<div className="game-story-card" role="dialog" aria-label={title}>
				<h2>{title}</h2>
				{lines.map((line) => (
					<p key={line}>{line}</p>
				))}
				{action && onAction && (
					<button
						type="button"
						className="game-action"
						disabled={busy}
						onClick={() => {
							onPress?.();
							onAction();
						}}
					>
						{action}
					</button>
				)}
				{!action && busy && <p role="status">…</p>}
			</div>
		</div>
	);
}
