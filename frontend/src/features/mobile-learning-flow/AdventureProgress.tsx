import type { PresentationManifest } from "./api/generated";

export type AdventureProgressStage = 1 | 2 | 3 | 4;

export function adaptiveGameProgressStage(
	step: string,
	measurementRole?: PresentationManifest["measurement_role"],
): AdventureProgressStage {
	if (step === "result") return 4;
	if (measurementRole === "unsupported_after") return 3;
	if (step === "support" || step === "withdrawing") return 2;
	return 1;
}

export function AdventureProgress({
	stage,
	activityCount = 3,
	currentActivity,
	completedActivities = 0,
}: {
	stage: AdventureProgressStage;
	activityCount?: number;
	currentActivity?: number;
	completedActivities?: number;
}) {
	if (currentActivity !== undefined) {
		const labels = Array.from({ length: activityCount }, (_, index) =>
			String(index + 1),
		);
		return (
			<fieldset
				className="adventure-progress adventure-progress--activities"
				data-progress-mode="activities"
				data-activity-count={activityCount}
			>
				<legend className="sr-only">සම්පූර්ණ ක්‍රියාකාරකම් ප්‍රගතිය</legend>
				{labels.map((label, index) => {
					const activity = index + 1;
					const done = activity <= completedActivities;
					const current = activity === currentActivity && !done;
					return (
						<span
							key={label}
							className={done ? "is-done" : current ? "is-current" : undefined}
							aria-current={current ? "step" : undefined}
						>
							{done ? "✓" : label}
							<small className="sr-only">
								ක්‍රියාකාරකම {activity}
								{done ? " සම්පූර්ණයි" : ""}
							</small>
						</span>
					);
				})}
			</fieldset>
		);
	}
	if (activityCount < 3) {
		return (
			<div
				className="adventure-progress adventure-progress--stars"
				data-progress-mode="stars"
				data-progress-stage={stage}
				role="img"
				aria-label="තරු තුනක්"
			>
				{["star-1", "star-2", "star-3"].map((id) => (
					<span key={id} aria-hidden="true">
						★
					</span>
				))}
			</div>
		);
	}
	const labels = ["1", "2", "3", "★"];
	return (
		<fieldset className="adventure-progress" data-progress-stage={stage}>
			<legend className="sr-only">ක්‍රීඩා පියවර</legend>
			{labels.map((label, index) => {
				const itemStage = (index + 1) as AdventureProgressStage;
				const state =
					itemStage < stage
						? "is-done"
						: itemStage === stage
							? "is-current"
							: "";
				return (
					<span
						key={label}
						className={state || undefined}
						aria-current={itemStage === stage ? "step" : undefined}
					>
						{label}
					</span>
				);
			})}
		</fieldset>
	);
}
