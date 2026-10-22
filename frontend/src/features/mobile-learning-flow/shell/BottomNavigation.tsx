// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import type { CSSProperties, ReactNode } from "react";

export type TabDestination =
	| "home"
	| "learn"
	| "practice"
	| "mindy"
	| "progress";
export function BottomNavigation({
	active,
	onNavigate,
}: {
	active: string;
	onNavigate(destination: TabDestination): void;
}) {
	const tabs: Array<{
		id: TabDestination;
		label: string;
		icon: NavigationIconName;
	}> = [
		{ id: "home", label: "මුල් පිටුව", icon: "home" },
		{ id: "learn", label: "ක්‍රීඩා", icon: "game" },
		{ id: "practice", label: "පුහුණුව", icon: "document" },
		{ id: "mindy", label: "Mindy", icon: "sparkle" },
		{ id: "progress", label: "ප්‍රගතිය", icon: "chart" },
	];
	return (
		<nav
			className="bottom-navigation"
			aria-label="ප්‍රධාන මෙනුව"
			style={
				{
					"--active-tab": Math.max(
						0,
						tabs.findIndex((tab) => tab.id === active),
					),
				} as CSSProperties
			}
		>
			<span className="nav-selection" aria-hidden="true" />
			{tabs.map((tab) => {
				const selected = active === tab.id;
				return (
					<button
						key={tab.id}
						className={selected ? "nav-item nav-item--active" : "nav-item"}
						type="button"
						aria-current={selected ? "page" : undefined}
						onClick={() => onNavigate(tab.id)}
					>
						<span>
							<NavigationIcon name={tab.icon} />
						</span>
						<small>{tab.label}</small>
					</button>
				);
			})}
		</nav>
	);
}

export type NavigationIconName =
	| "home"
	| "game"
	| "document"
	| "sparkle"
	| "chart";

export function NavigationIcon({ name }: { name: NavigationIconName }) {
	const icons: Record<NavigationIconName, ReactNode> = {
		home: (
			<>
				<path d="m4 10 6.1-5.3a3 3 0 0 1 3.8 0L20 10v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
				<path d="M9 20v-5a3 3 0 0 1 6 0v5" />
			</>
		),
		game: (
			<>
				<path d="M8 7h8a4 4 0 0 1 3.9 3.2l1 6a2.5 2.5 0 0 1-4.1 2.3L14.5 17h-5l-2.3 1.5a2.5 2.5 0 0 1-4.1-2.3l1-6A4 4 0 0 1 8 7Z" />
				<path d="M8 10v4m-2-2h4" />
				<circle cx="16" cy="11" r=".7" fill="currentColor" stroke="none" />
				<circle cx="18" cy="14" r=".7" fill="currentColor" stroke="none" />
			</>
		),
		document: (
			<>
				<rect x="5" y="3" width="14" height="18" rx="4" />
				<path d="M9 8h6m-6 4h6m-6 4h3" />
			</>
		),
		sparkle: (
			<>
				<path d="M12 3c.9 5.4 3.6 8.1 9 9-5.4.9-8.1 3.6-9 9-.9-5.4-3.6-8.1-9-9 5.4-.9 8.1-3.6 9-9Z" />
				<path d="M20 2v4m-2-2h4" />
			</>
		),
		chart: (
			<>
				<rect x="3" y="12" width="4" height="8" rx="2" />
				<rect x="10" y="4" width="4" height="16" rx="2" />
				<rect x="17" y="8" width="4" height="12" rx="2" />
			</>
		),
	};
	return (
		<svg
			className="nav-icon"
			width="24"
			height="24"
			viewBox="0 0 24 24"
			aria-hidden="true"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.8"
			strokeLinecap="round"
			strokeLinejoin="round"
		>
			{icons[name]}
		</svg>
	);
}
