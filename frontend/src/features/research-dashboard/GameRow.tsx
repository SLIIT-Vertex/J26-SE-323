import type { ReactNode } from "react";
import { shortDate } from "./charts";

export function answerLabel(
	value: boolean | null | undefined,
	missing = "Not answered",
) {
	return value === true ? "Correct" : value === false ? "Incorrect" : missing;
}
export function GameRow({
	title,
	date,
	selected,
	onClick,
	children,
	status,
}: {
	title: string;
	date?: string | null;
	selected?: boolean;
	onClick(): void;
	children: ReactNode;
	status?: ReactNode;
}) {
	return (
		<button
			type="button"
			className="rd-game-row"
			aria-pressed={selected}
			onClick={onClick}
		>
			<span className="rd-game-row__head">
				<strong>{title}</strong>
				{date && (
					<time dateTime={date}>
						{shortDate(date)} ·{" "}
						{new Date(date).toLocaleTimeString("en-GB", {
							hour: "2-digit",
							minute: "2-digit",
							timeZone: "Asia/Colombo",
						})}
					</time>
				)}
			</span>
			<span className="rd-game-row__facts">{children}</span>
			{status && <span className="rd-game-row__status">{status}</span>}
			<span className="rd-game-row__open">View game details →</span>
		</button>
	);
}
export function PlayStatus({ status }: { status?: string }) {
	if (status === "abandoned") return <span>Stopped partway · not counted</span>;
	if (status === "invalid") return <span>Not valid · not counted</span>;
	if (status === "live") return <span>In progress · awaiting a result</span>;
	return null;
}
