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
import { AlienBedtime } from "./AlienBedtime";
import { StarSplitter } from "./StarSplitter";
import { spaceArtReady, spaceArtUrl } from "./spaceArt";
import {
	missionOrder,
	readTask,
	SPACE_AREA_ID,
	type SpacePlace,
	spaceTrainingPlace,
	WRITTEN_SKILL_ID,
} from "./spaceRules";
import { spaceSounds } from "./spaceSounds";
import { UfoBoarding } from "./UfoBoarding";
import "./space-sleepover.css";

/** The interaction-summary fields the Division flow accepts. */
const DIVISION_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

const STATION = spaceArtReady("bgSpace") ? spaceArtUrl("bgSpace") : undefined;

const PLACES: Record<
	SpacePlace,
	{ title: string; backdrop: string | undefined }
> = {
	"star-splitter": { title: "තරු බෙදන මැජික් සෙල්ලම!", backdrop: STATION },
	"alien-bedtime": { title: "පිටසක්වල පැටවු නිදි කරමු!", backdrop: STATION },
};

/**
 * Nimo's Galactic Sleepover (Division). Nimo organises the biggest sleepover in the galaxy: the
 * guests must board the UFOs equally, and any left over ride with Nimo. A muddled boarding sends
 * Nimo to the star splitter or the alien bedroom, where the server picks each help round; then a
 * fresh boarding of the same kind. Each new boarding picks its kind at random.
 */
export function NimoSpaceSleepover({
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
		areaId: SPACE_AREA_ID,
		skillId: WRITTEN_SKILL_ID,
		summaryFields: DIVISION_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				spaceSounds.play("jingle-launch", { steady: true });
				spaceSounds.play("sparkle", { delay: 0.9, volume: 0.6 });
			} else {
				spaceSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			spaceSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastBoarding = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => spaceSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			spaceSounds.play("jingle-train", { steady: true });
		if (phase === "training") spaceSounds.play("beam");
		if (phase === "return") spaceSounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") spaceSounds.play("beam");
		if (phase === "victory")
			spaceSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") spaceSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => spaceSounds.play("tap");
	const newBoarding = () => {
		const skills = missionOrder(lastBoarding.current);
		lastBoarding.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = spaceTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝගේ පුංචි පිටසක්වල සාදය" onBack={onBack}>
			<section
				className="space-sleepover"
				data-space-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<UfoBoarding
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
							<SpaceTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ පුංචි පිටසක්වල සාදය"
						image={spaceArtUrl("nimoIdle")}
						lines={[
							"මන්දාකිනියේ ලොකුම නිදි සාදයට නිමෝට ආරාධනාවක් ආවා!",
							"හැම යානයකටම අමුත්තන් සමාන ගාණක් නංවමු. ඉතිරි අය නිමෝ එක්ක යනවා!",
						]}
						action="යානා පුරවමු!"
						busy={busy}
						onPress={tap}
						onAction={newBoarding}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="යානා ස්ථානයේ පුහුණුව"
						image={spaceArtUrl("nimoThink")}
						lines={["අමුත්තන් ගාණ ටිකක් පැටලුණා.", "පොඩ්ඩක් පුහුණු වෙලා බලවත් වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={spaceArtUrl("nimoCheer")}
						lines={["අලුත් අමුත්තන් කණ්ඩායමක් යානා ළඟ බලාගෙන ඉන්නවා."]}
						action="යානා ළඟට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="යානා ළඟට යනවා…"
						image={spaceArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="යානා ඉගිලුණා!"
						image={spaceArtUrl("nimoCheer")}
						lines={["හැම යානයකටම එක ගාණක්. සාදය පටන් ගන්නවා!"]}
						action="ඊළඟ ගමන"
						busy={busy}
						onPress={tap}
						onAction={newBoarding}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={spaceArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් යානා පුරවමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newBoarding}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Long division at the star splitter; sharing into 2 at alien bedtime. */
export function SpaceTrainingBoard({
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
		spaceTrainingPlace(task) === "alien-bedtime" ? AlienBedtime : StarSplitter;
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
