// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import type { ReactNode } from "react";

export type AvatarTone = "violet" | "sky" | "teal" | "orange";

export function Back({ onClick }: { onClick(): void }) {
	return (
		<button className="back-button" aria-label="ආපසු" onClick={onClick}>
			<AppIcon name="back" size={19} /> ආපසු
		</button>
	);
}
export function BrandMark({
	className = "",
	variant = "submark",
}: {
	className?: string;
	variant?: "primary" | "submark";
}) {
	const src = variant === "primary" ? "/primary-logo.svg" : "/logo-submark.svg";
	return (
		<img
			className={`brand-mark brand-mark--${variant} ${className}`.trim()}
			src={src}
			alt="MindBridge"
		/>
	);
}

export function LearnerAvatar({ tone = "violet" }: { tone?: AvatarTone }) {
	const palette: Record<
		AvatarTone,
		{ background: string; shirt: string; backpack: string }
	> = {
		violet: { background: "#efecfd", shirt: "#6c5ce7", backpack: "#4ebbc4" },
		sky: { background: "#e8f5fe", shirt: "#3fa9f5", backpack: "#6c5ce7" },
		teal: { background: "#e4faf5", shirt: "#16bfa6", backpack: "#ff9f5a" },
		orange: { background: "#fff0e3", shirt: "#ff8b45", backpack: "#6c5ce7" },
	};
	const colors = palette[tone];
	return (
		<svg
			className="learner-avatar"
			viewBox="0 0 100 100"
			role="img"
			aria-label="තෝරාගත් අවතාරය"
		>
			<circle cx="50" cy="50" r="48" fill={colors.background} />
			<path
				d="M24 69q2-15 13-19l13 19-9 20H28q-5-9-4-20Z"
				fill={colors.backpack}
				opacity=".82"
			/>
			<ellipse cx="50" cy="71" rx="27" ry="20" fill={colors.shirt} />
			<circle cx="50" cy="43" r="23" fill="#f2bf91" />
			<path d="M27 38Q50 12 73 38Q72 20 50 19Q28 21 27 38Z" fill="#342a38" />
			<circle cx="42" cy="43" r="2.7" fill="#2e2a45" />
			<circle cx="58" cy="43" r="2.7" fill="#2e2a45" />
			<path
				d="M43 52q7 7 14 0"
				fill="none"
				stroke="#2e2a45"
				strokeLinecap="round"
				strokeWidth="2.4"
			/>
			<circle cx="34" cy="49" r="3" fill="#ff9f5a" opacity=".45" />
			<circle cx="66" cy="49" r="3" fill="#ff9f5a" opacity=".45" />
		</svg>
	);
}

export type IconName =
	| "home"
	| "game"
	| "trophy"
	| "chart"
	| "user"
	| "book"
	| "sparkle"
	| "globe"
	| "shield"
	| "play"
	| "target"
	| "settings"
	| "back"
	| "bell"
	| "fire"
	| "arrow"
	| "support"
	| "document";
export function AppIcon({
	name,
	size = 24,
}: {
	name: IconName;
	size?: number;
}) {
	const paths: Record<IconName, ReactNode> = {
		home: (
			<>
				<path d="m3 10 9-7 9 7" />
				<path d="M5 9v11h14V9M9 20v-6h6v6" />
			</>
		),
		game: (
			<>
				<path d="M8 8h8a5 5 0 0 1 4.7 6.7l-1.1 3.1a2.5 2.5 0 0 1-4.1 1l-1.3-1.2H9.8l-1.3 1.2a2.5 2.5 0 0 1-4.1-1l-1.1-3.1A5 5 0 0 1 8 8Z" />
				<path d="M7 12v4M5 14h4M16.5 12.5h.01M18.5 15h.01" />
			</>
		),
		trophy: (
			<>
				<path d="M8 4h8v5a4 4 0 0 1-8 0V4Z" />
				<path d="M8 6H5v2a3 3 0 0 0 3 3M16 6h3v2a3 3 0 0 1-3 3M12 13v4M8 21h8M9 17h6v4H9z" />
			</>
		),
		chart: (
			<>
				<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
			</>
		),
		user: (
			<>
				<circle cx="12" cy="8" r="4" />
				<path d="M4 21a8 8 0 0 1 16 0" />
			</>
		),
		book: (
			<>
				<path d="M4 5a3 3 0 0 1 3-2h5v17H7a3 3 0 0 0-3 2V5ZM20 5a3 3 0 0 0-3-2h-5v17h5a3 3 0 0 1 3 2V5Z" />
			</>
		),
		sparkle: (
			<>
				<path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z" />
				<path d="m19 14 .8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14Z" />
			</>
		),
		globe: (
			<>
				<circle cx="12" cy="12" r="9" />
				<path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
			</>
		),
		shield: (
			<>
				<path d="M12 3 4.5 6v5.5c0 4.7 3.2 8.1 7.5 9.5 4.3-1.4 7.5-4.8 7.5-9.5V6L12 3Z" />
				<path d="m9 12 2 2 4-5" />
			</>
		),
		play: <path d="m9 7 8 5-8 5V7Z" />,
		target: (
			<>
				<circle cx="12" cy="12" r="9" />
				<circle cx="12" cy="12" r="5" />
				<circle cx="12" cy="12" r="1" />
			</>
		),
		settings: (
			<>
				<circle cx="12" cy="12" r="3" />
				<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
			</>
		),
		back: (
			<>
				<path d="m15 18-6-6 6-6" />
				<path d="M9 12h10" />
			</>
		),
		bell: (
			<>
				<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
				<path d="M10 21h4" />
			</>
		),
		fire: (
			<path d="M12 22c4 0 7-3 7-7 0-3-1.5-5.5-4-8 .2 3-1.3 4-2 4-1-4-3-6-3-6-1 4-5 6-5 11 0 3.4 3 6 7 6Z" />
		),
		arrow: (
			<>
				<path d="M5 12h14M14 7l5 5-5 5" />
			</>
		),
		support: (
			<>
				<path d="M8.5 5.5A4.5 4.5 0 0 0 4 10c0 4.5 8 9 8 9s8-4.5 8-9a4.5 4.5 0 0 0-8-2.8 4.5 4.5 0 0 0-3.5-1.7Z" />
				<path d="m9 12 2 2 4-4" />
			</>
		),
		document: (
			<>
				<path d="M6 2h8l4 4v16H6z" />
				<path d="M14 2v5h5M9 12h6M9 16h6" />
			</>
		),
	};
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 24 24"
			aria-hidden="true"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.9"
			strokeLinecap="round"
			strokeLinejoin="round"
		>
			{paths[name]}
		</svg>
	);
}
