import { useEffect, useMemo } from "react";
import { GameStoryCard } from "../../../mobile-learning-flow/landscape/GameStoryCard";
import { LandscapeGameStage } from "../../../mobile-learning-flow/landscape/LandscapeGameStage";
import {
	TrainingRoom,
	type TrainingBoardProps,
} from "../../../mobile-learning-flow/landscape/TrainingRoom";
import { useHardFirstEpisode } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import type { AreaGameProps } from "../../registry";
import { BeadBuilder, BeadCompare } from "./BeadBounce";
import { CostumeShop } from "./CostumeShop";
import { ToyParadeMission } from "./ToyParadeMission";
import { toyArtReady, toyArtUrl } from "./toyArt";
import {
	ABACUS_SKILL_ID,
	costumeQuestion,
	PARADE_SKILL_ID,
	POSITION_SKILL_ID,
	REPRESENTED_SKILL_ID,
	readDigit,
	readNumber,
	readParade,
	TOY_AREA_ID,
} from "./toyRules";
import { toySounds } from "./toySounds";
import "./toybox.css";

type Place = "bead-bounce" | "costume-shop";

/** The interaction-summary fields the Numbers flow accepts. */
const NUMBERS_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

export function toyTrainingPlace(skillId: string): Place {
	return skillId === POSITION_SKILL_ID || skillId === REPRESENTED_SKILL_ID
		? "costume-shop"
		: "bead-bounce";
}

const backdrop = (key: "bgBeadWorkshop" | "bgCostumeShop") =>
	toyArtReady(key) ? toyArtUrl(key) : undefined;

const PLACES: Record<Place, { title: string; backdrop: string | undefined }> = {
	"bead-bounce": {
		title: "මැණික් බෝල සෙල්ලම",
		backdrop: backdrop("bgBeadWorkshop"),
	},
	"costume-shop": {
		title: "අංක ඇඳුම් සාප්පුව",
		backdrop: backdrop("bgCostumeShop"),
	},
};

/**
 * Nimo's Wacky Toybox (Numbers). Nimo shrinks inside a giant toybox and directs the Great Toy
 * Show: the child orders the parade toys; a muddled parade sends Nimo backstage to the bead toy
 * and the costume shop, where the server picks each help round; then a fresh parade.
 */
export function NimoToybox({
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
		areaId: TOY_AREA_ID,
		skillId: PARADE_SKILL_ID,
		summaryFields: NUMBERS_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				toySounds.play("jingle-parade", { steady: true });
				toySounds.play("sparkle", { delay: 0.9, volume: 0.6 });
			} else {
				toySounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			toySounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const parade = useMemo(
		() => readParade(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => toySounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			toySounds.play("jingle-train", { steady: true });
		if (phase === "training") toySounds.play("whoosh");
		if (phase === "return") toySounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") toySounds.play("whoosh");
		if (phase === "victory") toySounds.play("jingle-victory", { steady: true });
		if (phase === "rest") toySounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => toySounds.play("tap");
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const place = toyTrainingPlace(
		(round?.activity ?? round?.worked_example)?.skill_id ??
			round?.skill_id ??
			"",
	);

	return (
		<LandscapeGameStage label="නිමෝගේ අරුම පුදුම සෙල්ලම් ලෝකය" onBack={onBack}>
			<section
				className="toybox"
				data-toy-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<ToyParadeMission
						key={manifest.revision_id}
						values={parade.values}
						ascending={parade.ascending}
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
							<ToyTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ අරුම පුදුම සෙල්ලම් ලෝකය"
						image={toyArtUrl("nimoIdle")}
						lines={[
							"නිමෝ ලොකු සෙල්ලම් පෙට්ටියකට ගිහින් සෙල්ලම් බඩුවක් තරම් පුංචි වුණා!",
							"සෙල්ලම් බඩුවල අංක පටලැවිලා. පෙළපාළියට උදව් කරමු!",
						]}
						action="පෙළපාළියට යමු!"
						busy={busy}
						onPress={tap}
						onAction={() => void episode.startMission()}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="පිටුපස වේදිකාව"
						image={toyArtUrl("nimoThink")}
						lines={["අංක ටිකක් පටලැවිලා.", "පිටුපස වේදිකාවේ සෙල්ලම් කරලා බලමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={toyArtUrl("nimoCheer")}
						lines={["අලුත් සෙල්ලම් බඩු ටිකක් පෙළපාළියට එනවා."]}
						action="වේදිකාවට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="වේදිකාවට යනවා…"
						image={toyArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="පෙළපාළිය සාර්ථකයි!"
						image={toyArtUrl("nimoCheer")}
						lines={["සෙල්ලම් බඩු ඔක්කොම සතුටින් නටනවා!"]}
						action="ඊළඟ පෙළපාළිය"
						busy={busy}
						onPress={tap}
						onAction={() => void episode.startMission()}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={toyArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් පෙළපාළියක් කරමු!"]}
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

/** Costumes for place and value, the bead toy for building and for comparing parade numbers. */
export function ToyTrainingBoard({
	activity,
	demo,
	hint,
	onResponse,
	evidence,
}: TrainingBoardProps & { evidence: ReturnType<typeof useMoveEvidence> }) {
	const game = activity.game as Record<string, unknown>;
	if (toyTrainingPlace(activity.skill_id) === "costume-shop") {
		return (
			<CostumeShop
				number={readNumber(game)}
				digit={readDigit(game)}
				question={costumeQuestion(activity.skill_id)}
				demo={demo}
				hint={hint}
				evidence={evidence}
				onResponse={onResponse}
			/>
		);
	}
	if (activity.skill_id === ABACUS_SKILL_ID) {
		return (
			<BeadBuilder
				number={readNumber(game)}
				demo={demo}
				hint={hint}
				evidence={evidence}
				onResponse={onResponse}
			/>
		);
	}
	const { values, ascending } = readParade(game);
	return (
		<BeadCompare
			values={values}
			ascending={ascending}
			demo={demo}
			hint={hint}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}
