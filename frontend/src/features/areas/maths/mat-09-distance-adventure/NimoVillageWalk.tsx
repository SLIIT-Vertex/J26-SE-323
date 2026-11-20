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
import { MarketRoad } from "./MarketRoad";
import { TikkiGarden } from "./TikkiGarden";
import { ToyRoad } from "./ToyRoad";
import { villageArtReady, villageArtUrl } from "./villageArt";
import {
	ADD_SKILL_ID,
	missionOrder,
	readTask,
	VILLAGE_AREA_ID,
	type VillagePlace,
	villageTrainingPlace,
} from "./villageRules";
import { villageSounds } from "./villageSounds";
import "./village-walk.css";

/** The interaction-summary fields the Length flow accepts. */
const DISTANCE_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

const backdrop = (key: "bgVillage" | "bgToyroom" | "bgGarden") =>
	villageArtReady(key) ? villageArtUrl(key) : undefined;
const VILLAGE = backdrop("bgVillage");

const PLACES: Record<
	VillagePlace,
	{ title: string; backdrop: string | undefined }
> = {
	"toy-road": { title: "සෙල්ලම් ගෙදර පාර හදමු!", backdrop: backdrop("bgToyroom") },
	"tikki-garden": { title: "ටික්කි එක්ක දුර මනිමු!", backdrop: backdrop("bgGarden") },
};

/**
 * Nimo's Village Walk (Length and distance). It is market day: Nimo builds the road to the market
 * piece by piece and works out how far it is. A muddled road sends him to the playhouse's toy road
 * or to Tikki's garden, where the server picks each help round; then a fresh road of the same
 * kind. Each new road picks its kind at random.
 */
export function NimoVillageWalk({
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
		areaId: VILLAGE_AREA_ID,
		skillId: ADD_SKILL_ID,
		summaryFields: DISTANCE_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				for (let step = 0; step < 4; step++)
					villageSounds.play("step", { delay: step * 0.35, volume: 0.7 });
				villageSounds.play("jingle-arrive", { steady: true, delay: 1.5 });
			} else {
				villageSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			villageSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastRoad = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => villageSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			villageSounds.play("jingle-train", { steady: true });
		if (phase === "return")
			villageSounds.play("jingle-return", { steady: true });
		if (phase === "victory")
			villageSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") villageSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => villageSounds.play("tap");
	const newRoad = () => {
		const skills = missionOrder(lastRoad.current);
		lastRoad.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = villageTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝ එක්ක ගම වටේ යමු!" onBack={onBack}>
			<section
				className="village-walk"
				data-village-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
				style={
					VILLAGE
						? ({ "--village-bg": `url("${VILLAGE}")` } as CSSProperties)
						: undefined
				}
			>
				{phase === "mission" && manifest && (
					<MarketRoad
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
							<VillageTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ ගමේ දවස"
						image={villageArtUrl("nimoIdle")}
						lines={[
							"අද ගමේ පොළ දවස! නිමෝට පොළට ගිහින් පලතුරු ටිකක් ගන්න ඕනේ.",
							"අද අපි පොළට යමුද? එන්න, පාර හොයාගෙන යමු!",
						]}
						action="පොළට යමු!"
						busy={busy}
						onPress={tap}
						onAction={newRoad}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="පොඩි නැවතීමක්"
						image={villageArtUrl("nimoThink")}
						lines={["පාරේ දුර පොඩ්ඩක් පැටලුණා.", "යාළුවෝ ළඟට ගිහින් දුර මනින්න පුහුණු වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={villageArtUrl("nimoCheer")}
						lines={["පොළට යන අලුත් පාරක් බලාගෙන ඉන්නවා."]}
						action="පොළ පාරට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="පොළ පාරට යනවා…"
						image={villageArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="පොළට ආවා!"
						image={villageArtUrl("nimoCheer")}
						lines={["නිමෝ පොළෙන් රසම රස පලතුරු ගත්තා! 🍌 🥭 🍍"]}
						action="ඊළඟ ගමන"
						busy={busy}
						onPress={tap}
						onAction={newRoad}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={villageArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් පොළට යමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newRoad}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Road sums on the toy road; units and building distances in Tikki's garden. */
export function VillageTrainingBoard({
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
		villageTrainingPlace(task) === "tikki-garden" ? TikkiGarden : ToyRoad;
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
