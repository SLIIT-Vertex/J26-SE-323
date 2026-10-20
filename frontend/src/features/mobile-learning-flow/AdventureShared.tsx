import { AdventureProgress, type AdventureProgressStage } from "./AdventureProgress";

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

export function AdventureNotice({
	message,
	onDismiss,
}: {
	message: string;
	onDismiss?(): void;
}) {
	if (!message) return null;
	return (
		<div className="adventure-notice" role="alert">
			<span>{message}</span>
			{onDismiss && (
				<button type="button" aria-label="පණිවිඩය වසන්න" onClick={onDismiss}>
					×
				</button>
			)}
		</div>
	);
}

export function GameSuccessScreen({
	gameNumber,
	gameCount = 3,
	onContinue,
}: {
	gameNumber: number;
	gameCount?: number;
	onContinue(): void;
}) {
	const safeGameNumber = Math.min(Math.max(1, gameNumber), gameCount);
	const allGamesComplete = safeGameNumber === gameCount;
	const progressStage = (
		allGamesComplete ? 4 : Math.min(3, safeGameNumber + 1)
	) as AdventureProgressStage;
	return (
		<section
			className="adventure-result is-success game-success-screen"
			data-completed-game={safeGameNumber}
			data-game-count={gameCount}
			role="status"
		>
			{gameCount <= 3 ? (
				<AdventureProgress stage={progressStage} />
			) : (
				<AdventureProgress
					stage={progressStage}
					activityCount={gameCount}
					currentActivity={Math.min(safeGameNumber + 1, gameCount)}
					completedActivities={safeGameNumber}
				/>
			)}
			<SuccessCelebration />
			<h2>
				{allGamesComplete && gameCount === 3
					? "ක්‍රීඩා තුනම සම්පූර්ණයි!"
					: `ක්‍රීඩාව ${safeGameNumber} සම්පූර්ණයි!`}
			</h2>
			<p>
				{allGamesComplete
					? "සියලු අභියෝග අවසන්. තරුව ඔබටයි!"
					: "මෙම ක්‍රීඩාවේ අභියෝග අවසන්. ඊළඟ ක්‍රීඩාවට යමු."}
			</p>
			<button type="button" className="primary-action" onClick={onContinue}>
				{allGamesComplete ? "ක්‍රීඩා තේරීමට" : "ඊළඟ ක්‍රීඩාව"}
			</button>
		</section>
	);
}
