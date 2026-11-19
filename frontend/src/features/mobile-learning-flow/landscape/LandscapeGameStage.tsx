import { type ReactNode, useEffect } from "react";
import { setGameSoundMuted, useGameSoundMuted } from "./gameAudio";
import { lockOrientation } from "./orientation";
import "./landscape-game-stage.css";

/**
 * A full-screen 16:9 game stage. While it is mounted the phone is turned to landscape and the app
 * menus are covered; leaving it turns the phone back to portrait. Children are laid out in a
 * 1920×1080 design space: CSS inside the stage can use `calc(var(--px) * N)` for N design pixels.
 * The sound button beside the back button mutes every game's sounds and remembers the choice.
 */
export function LandscapeGameStage({
	label,
	onBack,
	children,
}: {
	label: string;
	onBack(): void;
	children: ReactNode;
}) {
	const muted = useGameSoundMuted();
	useEffect(() => {
		void lockOrientation("landscape");
		return () => {
			void lockOrientation("portrait");
		};
	}, []);
	return (
		<div className="landscape-game-layer" role="application" aria-label={label}>
			<div className="landscape-game-stage">
				{children}
				<button
					type="button"
					className="landscape-back-button"
					aria-label="ආපසු"
					onClick={onBack}
				>
					<svg aria-hidden="true" viewBox="0 0 24 24">
						<path d="m15 18-6-6 6-6" />
					</svg>
				</button>
				<button
					type="button"
					className="landscape-back-button landscape-sound-button"
					aria-label={muted ? "ශබ්දය දාන්න" : "ශබ්දය නවත්වන්න"}
					aria-pressed={muted}
					onClick={() => setGameSoundMuted(!muted)}
				>
					<svg aria-hidden="true" viewBox="0 0 24 24">
						<path d="M4 9h4l5-4v14l-5-4H4z" />
						{muted ? (
							<path d="m17 9 5 6m0-6-5 6" />
						) : (
							<path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" />
						)}
					</svg>
				</button>
			</div>
			<div className="landscape-rotate-prompt" role="status">
				<svg aria-hidden="true" viewBox="0 0 48 48">
					<rect x="14" y="6" width="20" height="36" rx="4" />
					<path d="M8 30a16 16 0 0 0 16 12M40 18A16 16 0 0 0 24 6" />
					<path d="m22 38 2 4-4 1M26 10l-2-4 4-1" />
				</svg>
				<p>දුරකථනය හරවන්න</p>
				<button
					type="button"
					className="landscape-back-button is-inline"
					aria-label="ආපසු"
					onClick={onBack}
				>
					<svg aria-hidden="true" viewBox="0 0 24 24">
						<path d="m15 18-6-6 6-6" />
					</svg>
				</button>
			</div>
		</div>
	);
}
