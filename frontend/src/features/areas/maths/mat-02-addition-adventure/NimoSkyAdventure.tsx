import { useEffect, useMemo } from "react";
import { GameStoryCard } from "../../../mobile-learning-flow/landscape/GameStoryCard";
import { LandscapeGameStage } from "../../../mobile-learning-flow/landscape/LandscapeGameStage";
import { TrainingRoom } from "../../../mobile-learning-flow/landscape/TrainingRoom";
import { useHardFirstEpisode } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { AreaGameProps } from "../../registry";
import { SkyCityMission } from "./SkyCityMission";
import { artUrl } from "./skyArt";
import { CITY_SKILL_ID, readAddends, SKY_AREA_ID } from "./skyRules";
import { skySounds } from "./skySounds";
import {
	SkyTrainingBoard,
	TRAINING_PLACES,
	trainingPlace,
} from "./TrainingGround";
import "./sky-adventure.css";

/**
 * Nimo's Sky Adventure (Addition). The child starts on the city mission; a closed warehouse door
 * sends Nimo to training, where the server chooses each help round; then Nimo returns to the city
 * for a fresh mission with no help.
 */
export function NimoSkyAdventure({
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
		areaId: SKY_AREA_ID,
		skillId: CITY_SKILL_ID,
		onMissionResult: (correct) => {
			if (correct) {
				skySounds.play("gate-open");
				skySounds.play("jingle-open", { delay: 0.35, steady: true });
				skySounds.play("sparkle", { delay: 0.8, volume: 0.6 });
			} else {
				skySounds.play("gate-locked");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			skySounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const addends = useMemo(
		() => readAddends(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => skySounds.preload(), []);

	// Each story moment has its own little tune.
	useEffect(() => {
		if (phase === "to-training")
			skySounds.play("jingle-train", { steady: true });
		if (phase === "training") skySounds.play("whoosh");
		if (phase === "return") skySounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") skySounds.play("fly");
		if (phase === "victory") skySounds.play("jingle-victory", { steady: true });
		if (phase === "rest") skySounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => skySounds.play("tap");
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const place = trainingPlace(
		(round?.activity ?? round?.worked_example)?.skill_id ??
			round?.skill_id ??
			"",
	);

	return (
		<LandscapeGameStage label="නිමෝගේ අහස් සවාරිය" onBack={onBack}>
			<section
				className="sky-adventure"
				data-sky-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<SkyCityMission
						key={manifest.revision_id}
						addends={addends}
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
						title={TRAINING_PLACES[place].title}
						backdrop={TRAINING_PLACES[place].backdrop}
						checkLabel="බලමු!"
						onCheckPress={tap}
						renderBoard={(props) => (
							<SkyTrainingBoard
								{...props}
								reducedMotion={reducedMotion}
								evidence={evidence}
							/>
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="අහස් නගරය බේරාගමු"
						image={artUrl("nimoIdle")}
						lines={[
							"අහස් නගරයේ උත්සවයට ශක්තිය මදි!",
							"ගුවන් නැව් බඩු පෙට්ටි ගෙනෙනවා. නිමෝට උදව් කරමු!",
						]}
						action="යමු!"
						busy={busy}
						onPress={tap}
						onAction={() => void episode.startMission()}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="නිමෝගේ පුහුණුව"
						image={artUrl("nimoThink")}
						lines={["දොර අරින්න නිමෝට තව ශක්තිය ඕනෑ.", "පුහුණුවට ගිහින් ශක්තිය පුරවගමු!"]}
						action="පුහුණුවට යමු"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="ශක්තිය පිරිලා!"
						image={artUrl("nimoPlane")}
						lines={["නිමෝ දැන් ශක්තියෙන් පිරිලා.", "නගරයට ආපසු ගිහින් ගබඩාව අරිමු!"]}
						action="නගරයට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="නගරයට පියාසර කරනවා…"
						image={artUrl("nimoPlane")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="නගරය බේරුණා!"
						image={artUrl("nimoCheer")}
						lines={["ගබඩාව ඇරුණා. උත්සවයට ශක්තිය ලැබුණා!"]}
						action="ඊළඟ ගුවන් නැව් ටික"
						busy={busy}
						onPress={tap}
						onAction={() => void episode.startMission()}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={artUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් නගරයට උදව් කරමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={() => void episode.startMission()}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}
