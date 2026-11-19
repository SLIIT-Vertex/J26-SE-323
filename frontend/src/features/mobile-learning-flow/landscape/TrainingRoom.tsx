import { type ReactNode, useState } from "react";
import { createPortal } from "react-dom";
import type {
	ConstructedResponse,
	SupportRoundActivity,
	SupportView,
} from "../api/generated";
import { SupportRoundFrame } from "../SupportRoundFrame";

export type TrainingBoardProps = {
	activity: SupportRoundActivity;
	/** A worked example: show the finished board; nothing can be touched. */
	demo: boolean;
	/** A help stage that carries the answer: show it faintly. */
	hint: boolean;
	onResponse(response: ConstructedResponse | null): void;
};

/**
 * Training after a failed mission. The server picks every help round; its words sit on the left
 * and its item is played on the right, in whichever training game `renderBoard` chooses.
 */
export function TrainingRoom({
	support,
	busy,
	place,
	title,
	backdrop,
	checkLabel,
	renderBoard,
	onAnswer,
	onViewComplete,
	onCheckPress,
}: {
	support: SupportView;
	busy: boolean;
	/** Stable id of the training place (data attribute for styling and tests). */
	place: string;
	title: string;
	/** Background image URL of the training place. */
	backdrop?: string;
	checkLabel: string;
	renderBoard(props: TrainingBoardProps): ReactNode;
	onAnswer(response: ConstructedResponse, activity: SupportRoundActivity): void;
	onViewComplete(): void;
	onCheckPress?(): void;
}) {
	const manifest = support.game_manifest;
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [stage, setStage] = useState<HTMLDivElement | null>(null);
	if (manifest.schema_version !== "support-round-v1") return null;
	const activity = manifest.activity;
	const demo = manifest.stage_kind === "view";
	return (
		<div
			className="game-training"
			data-training-place={place}
			data-stage-kind={manifest.stage_kind}
		>
			<div
				className="game-training-backdrop"
				aria-hidden="true"
				style={backdrop ? { backgroundImage: `url("${backdrop}")` } : undefined}
			/>
			<h2 className="game-training-title">{title}</h2>
			<div className="game-training-help">
				<SupportRoundFrame
					support={support}
					busy={busy}
					onViewComplete={onViewComplete}
					renderActivity={(item) =>
						stage &&
						createPortal(
							<TrainingBoardSlot key={item.revision_id}>
								{renderBoard({
									activity: item,
									demo,
									hint: Boolean(activity?.answer),
									onResponse: setResponse,
								})}
							</TrainingBoardSlot>,
							stage,
						)
					}
				/>
			</div>
			<div className="game-training-stage">
				<div ref={setStage} className="game-training-board" />
				{activity && !demo && (
					<button
						type="button"
						className="game-action"
						disabled={busy || response === null}
						onClick={() => {
							if (!response) return;
							onCheckPress?.();
							onAnswer(response, activity);
						}}
					>
						{checkLabel}
					</button>
				)}
			</div>
		</div>
	);
}

/** Keyed wrapper so each help item mounts a fresh board. */
function TrainingBoardSlot({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
