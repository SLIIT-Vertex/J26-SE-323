import { useEffect, useMemo, useRef } from "react";
import { GameStoryCard } from "../../../mobile-learning-flow/landscape/GameStoryCard";
import { LandscapeGameStage } from "../../../mobile-learning-flow/landscape/LandscapeGameStage";
import {
	type TrainingBoardProps,
	TrainingRoom,
} from "../../../mobile-learning-flow/landscape/TrainingRoom";
import { useHardFirstEpisode } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import type { AreaGameProps } from "../../registry";
import { BowlingBuddies } from "./BowlingBuddies";
import { carnivalArtReady, carnivalArtUrl } from "./carnivalArt";
import {
	BY_2_3_SKILL_ID,
	CARNIVAL_AREA_ID,
	type CarnivalPlace,
	carnivalTrainingPlace,
	missionOrder,
	readTask,
} from "./carnivalRules";
import { carnivalSounds } from "./carnivalSounds";
import { DancingStadium } from "./DancingStadium";
import { TurboRace } from "./TurboRace";
import "./sports-carnival.css";

/** The interaction-summary fields the Multiplication flow accepts that the shared evidence counts. */
const MULTIPLICATION_SUMMARY_FIELDS = [
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

/** Both help games play in front of the carnival track. */
const TRACK = carnivalArtReady("bgCarnival")
	? carnivalArtUrl("bgCarnival")
	: undefined;

const PLACES: Record<
	CarnivalPlace,
	{ title: string; backdrop: string | undefined }
> = {
	"dancing-stadium": { title: "නටන ප්‍රේක්ෂකාගාරය!", backdrop: TRACK },
	"bowling-buddies": { title: "බෝල ගහලා කූරු පෙරළමු!", backdrop: TRACK },
};

/**
 * Nimo's Wacky Sports Carnival (Multiplication). Nimo races at the Giggle Games to win the Golden
 * Giggle Trophy: every lap earns the same points, and the finish booth asks for the total. A
 * muddled score sends Nimo to the dancing stadium or to bowling, where the server picks each help
 * round; then a fresh race of the same kind. Each new race picks its kind at random.
 */
export function NimoSportsCarnival({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: AreaGameProps) {
	const episode = useHardFirstEpisode({
		api,
		learnerId,
		condition,
		onFailure,
		areaId: CARNIVAL_AREA_ID,
		skillId: BY_2_3_SKILL_ID,
		summaryFields: MULTIPLICATION_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				carnivalSounds.play("jingle-race", { steady: true });
				carnivalSounds.play("sparkle", { delay: 0.8, volume: 0.6 });
			} else {
				carnivalSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			carnivalSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastRace = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => carnivalSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			carnivalSounds.play("jingle-train", { steady: true });
		if (phase === "training") carnivalSounds.play("zoom");
		if (phase === "return")
			carnivalSounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") carnivalSounds.play("zoom");
		if (phase === "victory")
			carnivalSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") carnivalSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => carnivalSounds.play("tap");
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
	const place = carnivalTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝගේ පුදුම ක්‍රීඩා සැණකෙළිය" onBack={onBack}>
			<section
				className="sports-carnival"
				data-carnival-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<TurboRace
						key={manifest.revision_id}
						task={task}
						prompt={manifest.prompt_si}
						returning={manifest.measurement_role === "unsupported_after"}
						outcome={episode.outcome}
						busy={busy}
						reducedMotion={reducedMotion}
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
							<CarnivalTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ පුදුම ක්‍රීඩා සැණකෙළිය"
						image={carnivalArtUrl("nimoCheer")}
						lines={[
							"ලෝකයේ විහිළුම ක්‍රීඩා උළෙලට නිමෝට ආරාධනාවක් ආවා!",
							"හැම වටයකටම එක වගේ ලකුණු. මුළු ලකුණු හොයලා රත්තරන් කුසලානය දිනමු!",
						]}
						action="රේස් එකට යමු!"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="සැණකෙළියේ විශේෂ සෙල්ලම්"
						image={carnivalArtUrl("nimoThink")}
						lines={["ලකුණු ටිකක් පැටලුණා.", "සැණකෙළියේ විශේෂ සෙල්ලම් කරලා බලවත් වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={carnivalArtUrl("nimoCheer")}
						lines={["අලුත් රේස් එකක් පටන් ගන්නවා."]}
						action="රේස් එකට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="ආරම්භක රේඛාවට…"
						image={carnivalArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="ජයග්‍රහණය!"
						image={carnivalArtUrl("nimoCheer")}
						lines={["ලකුණු පුවරුව දැල්වුණා, ප්‍රේක්ෂකයෝ සතුටින් නටනවා!"]}
						action="ඊළඟ රේස් එක"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={carnivalArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් රේස් එකක් යමු!"]}
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

/** Written products in the dancing stadium; facts and stories at the bowling alley. */
export function CarnivalTrainingBoard({
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
		carnivalTrainingPlace(task) === "dancing-stadium"
			? DancingStadium
			: BowlingBuddies;
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
