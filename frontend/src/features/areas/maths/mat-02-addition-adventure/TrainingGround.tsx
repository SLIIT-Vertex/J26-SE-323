import type { TrainingBoardProps } from "../../../mobile-learning-flow/landscape/TrainingRoom";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { CrystalFlight } from "./CrystalFlight";
import { NumberFactory } from "./NumberFactory";
import { artUrl } from "./skyArt";
import { readAddends } from "./skyRules";

const MENTAL_SKILL_ID = "G5-MAT-ADD-MENTAL-01";

/** Which training place a help round's item belongs to. */
export function trainingPlace(
	skillId: string,
): "crystal-sky" | "number-factory" {
	return skillId === MENTAL_SKILL_ID ? "crystal-sky" : "number-factory";
}

export const TRAINING_PLACES = {
	"crystal-sky": { title: "ස්ඵටික අහස", backdrop: artUrl("bgCrystalSky") },
	"number-factory": {
		title: "අංක කර්මාන්ත ශාලාව",
		backdrop: artUrl("bgNumberFactory"),
	},
} as const;

/** The crystal flight for quick facts, the Number Factory for carrying. */
export function SkyTrainingBoard({
	activity,
	demo,
	hint,
	onResponse,
	reducedMotion,
	evidence,
}: TrainingBoardProps & {
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
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
