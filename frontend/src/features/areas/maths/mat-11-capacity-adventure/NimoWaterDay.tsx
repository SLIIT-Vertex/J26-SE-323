import { type CSSProperties, useEffect, useMemo, useRef } from "react";
import { GameStoryCard } from "../../../mobile-learning-flow/landscape/GameStoryCard";
import { LandscapeGameStage } from "../../../mobile-learning-flow/landscape/LandscapeGameStage";
import {
	type TrainingBoardProps,
	TrainingRoom,
} from "../../../mobile-learning-flow/landscape/TrainingRoom";
import { useHardFirstEpisode } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import type { AreaGameProps } from "../../registry";
import { BoatRace } from "./BoatRace";
import { DancingFountain } from "./DancingFountain";
import { WaterBalloons } from "./WaterBalloons";
import { waterArtReady, waterArtUrl } from "./waterArt";
import {
	ARITHMETIC_SKILL_ID,
	missionOrder,
	readTask,
	WATER_AREA_ID,
	type WaterPlace,
	waterTrainingPlace,
} from "./waterRules";
import { waterSounds } from "./waterSounds";
import "./water-day.css";

/** The interaction-summary fields the Capacity flow accepts. */
const CAPACITY_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

const GARDEN = waterArtReady("bgGarden") ? waterArtUrl("bgGarden") : undefined;

const PLACES: Record<
	WaterPlace,
	{ title: string; backdrop: string | undefined }
> = {
	"dancing-fountain": { title: "නටන වතුර මල!", backdrop: GARDEN },
	"water-balloons": { title: "බැලුම්වලට වතුර පුරවමු!", backdrop: GARDEN },
};

/**
 * Nimo's Water-Play Day (Capacity). Nimo's garden is ready for water games: the boat race needs its
 * channel filled with just the right water. A muddled race sends him to the dancing fountain or the
 * water balloons, where the server picks each help round; then a fresh race of the same kind. Each
 * new race picks its kind at random.
 */
export function NimoWaterDay({
	api,
	learnerId,
	condition,
	onBack,
	onFailure,
}: AreaGameProps) {
	const episode = useHardFirstEpisode({
		api,
		learnerId,
		condition,
		onFailure,
		areaId: WATER_AREA_ID,
		skillId: ARITHMETIC_SKILL_ID,
		summaryFields: CAPACITY_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				waterSounds.play("whoosh");
				waterSounds.play("jingle-race", { steady: true, delay: 0.8 });
			} else {
				waterSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			waterSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastRace = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => waterSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			waterSounds.play("jingle-train", { steady: true });
		if (phase === "return") waterSounds.play("jingle-return", { steady: true });
		if (phase === "victory")
			waterSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") waterSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => waterSounds.play("tap");
	const newRace = () => {
		const skills = missionOrder(lastRace.current);
		lastRace.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = waterTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝගේ වතුර සෙල්ලම් දවස" onBack={onBack}>
			<section
				className="water-day"
				data-water-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
				style={
					GARDEN
						? ({ "--water-bg": `url("${GARDEN}")` } as CSSProperties)
						: undefined
				}
			>
				{phase === "mission" && manifest && (
					<BoatRace
						key={manifest.revision_id}
						task={task}
						prompt={manifest.prompt_si}
						returning={manifest.measurement_role === "unsupported_after"}
						outcome={episode.outcome}
						busy={busy}
						evidence={evidence}
						onSubmit={(response) => void episode.submitMission(response)}
					/>
				)}
				{phase === "training" && support && (
					<TrainingRoom
						key={support.revision_id}
						support={support}
						busy={busy}
						place={place}
						title={PLACES[place].title}
						backdrop={PLACES[place].backdrop}
						checkLabel="බලමු!"
						onCheckPress={tap}
						renderBoard={(props) => (
							<WaterTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ වතුර සෙල්ලම් දවස"
						image={waterArtUrl("nimoIdle")}
						lines={[
							"අද නිමෝගේ වත්තේ වතුර සෙල්ලම් දවස! බෝට්ටු තරගයක්, වතුර මලක්, වතුර බැලුම්!",
							"අද අපි වතුරෙන් සෙල්ලම් කරමු! මුලින්ම බෝට්ටු තරගෙට යමු!",
						]}
						action="තරගෙට යමු!"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="පොඩි නැවතීමක්"
						image={waterArtUrl("nimoThink")}
						lines={["වතුර ගාණ පොඩ්ඩක් පැටලුණා.", "වතුර එක්ක පොඩ්ඩක් සෙල්ලම් කරමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් ලෑස්තියි!"
						image={waterArtUrl("nimoCheer")}
						lines={["අලුත් බෝට්ටු තරගයක් ලෑස්තියි."]}
						action="තරගෙට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="තරගෙට යනවා…"
						image={waterArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="බෝට්ටුව දිනුවා!"
						image={waterArtUrl("nimoCheer")}
						lines={["වතුර හරියටම! නිමෝගේ බෝට්ටුව දිනුවා! 🚤"]}
						action="ඊළඟ තරගය"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={waterArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් තරගෙට යමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Litres and millilitres at the fountain; small jugs at the balloons. */
export function WaterTrainingBoard({
	activity,
	demo,
	hint,
	onResponse,
	evidence,
}: TrainingBoardProps & { evidence: ReturnType<typeof useMoveEvidence> }) {
	const task = useMemo(
		() => readTask(activity.game as Record<string, unknown>),
		[activity.game],
	);
	const Board =
		waterTrainingPlace(task) === "water-balloons"
			? WaterBalloons
			: DancingFountain;
	return (
		<Board
			task={task}
			demo={demo}
			hint={hint}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}
