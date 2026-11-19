import { useState } from "react";
import { createPortal } from "react-dom";
import type {
	ConstructedResponse,
	SupportRoundActivity,
	SupportView,
} from "../../../mobile-learning-flow/api/generated";
import { SupportRoundFrame } from "../../../mobile-learning-flow/SupportRoundFrame";
import { CrystalFlight } from "./CrystalFlight";
import { NumberFactory } from "./NumberFactory";
import { readAddends } from "./skyRules";
import type { useMoveEvidence } from "./useMoveEvidence";

const MENTAL_SKILL_ID = "G5-MAT-ADD-MENTAL-01";

/** Which training place a help round's item belongs to. */
export function trainingPlace(
	skillId: string,
): "crystal-sky" | "number-factory" {
	return skillId === MENTAL_SKILL_ID ? "crystal-sky" : "number-factory";
}

/**
 * Nimo's training after a closed warehouse door. The server picks every help round; its words
 * sit on the left, and its item is played on the right in the training place that fits it: the
 * crystal flight for quick facts, the Number Factory for carrying.
 */
export function TrainingGround({
	support,
	busy,
	reducedMotion,
	evidence,
	onAnswer,
	onViewComplete,
}: {
	support: SupportView;
	busy: boolean;
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onAnswer(response: ConstructedResponse, activity: SupportRoundActivity): void;
	onViewComplete(): void;
}) {
	const manifest = support.game_manifest;
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [stage, setStage] = useState<HTMLDivElement | null>(null);
	if (manifest.schema_version !== "support-round-v1") return null;
	const activity = manifest.activity;
	const demo = manifest.stage_kind === "view";
	const shown = activity ?? manifest.worked_example;
	const place = trainingPlace(shown?.skill_id ?? manifest.skill_id);
	return (
		<div
			className="sky-training"
			data-training-place={place}
			data-stage-kind={manifest.stage_kind}
		>
			<div className="sky-training-backdrop" aria-hidden="true" />
			<h2 className="sky-training-title">
				{place === "crystal-sky" ? "ස්ඵටික අහස" : "අංක කර්මාන්ත ශාලාව"}
			</h2>
			<div className="sky-training-help">
				<SupportRoundFrame
					support={support}
					busy={busy}
					onViewComplete={onViewComplete}
					renderActivity={(item) =>
						stage &&
						createPortal(
							<TrainingBoard
								key={item.revision_id}
								activity={item}
								demo={demo}
								hint={Boolean(activity?.answer)}
								reducedMotion={reducedMotion}
								evidence={evidence}
								onResponse={setResponse}
							/>,
							stage,
						)
					}
				/>
			</div>
			<div className="sky-training-stage">
				<div ref={setStage} className="sky-training-board" />
				{activity && !demo && (
					<button
						type="button"
						className="sky-action"
						disabled={busy || response === null}
						onClick={() => response && onAnswer(response, activity)}
					>
						බලමු!
					</button>
				)}
			</div>
		</div>
	);
}

function TrainingBoard({
	activity,
	demo,
	hint,
	reducedMotion,
	evidence,
	onResponse,
}: {
	activity: SupportRoundActivity;
	demo: boolean;
	hint: boolean;
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const addends = readAddends(activity.game as Record<string, unknown>);
	if (trainingPlace(activity.skill_id) === "crystal-sky") {
		return (
			<CrystalFlight
				values={addends}
				demo={demo}
				hint={hint}
				reducedMotion={reducedMotion}
				evidence={evidence}
				onResponse={onResponse}
			/>
		);
	}
	return (
		<NumberFactory
			addends={addends}
			demo={demo}
			hint={hint}
			reducedMotion={reducedMotion}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}
