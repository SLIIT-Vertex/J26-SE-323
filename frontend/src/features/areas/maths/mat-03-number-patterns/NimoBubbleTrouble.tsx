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
import { BubbleRushMission } from "./BubbleRushMission";
import { bubbleArtReady, bubbleArtUrl } from "./bubbleArt";
import {
	PATTERN_AREA_ID,
	missionOrder,
	PLUS_TWO_SKILL_ID,
	readPattern,
} from "./bubbleRules";
import { bubbleRun, bubbleSounds } from "./bubbleSounds";
import { JellyfishParty } from "./JellyfishParty";
import { TikiSteps } from "./TikiSteps";
import "./bubble-trouble.css";

export type BubblePlace = "jellyfish-party" | "tiki-steps";

/** The interaction-summary fields the Number Patterns flow accepts. */
const PATTERNS_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

/** Help types that show the pattern most plainly go to Tiki's shells. */
const TIKI_HELP = new Set(["visual_guidance", "simpler_same_game"]);

/**
 * Where a help round is played. Adding and taking-away patterns are always Tiki's hops; a
 * multiplying pattern goes to the jellyfish shells, except for the plainest help, which Tiki shows
 * as group jumps.
 */
export function bubbleTrainingPlace(
	scaffoldType: string,
	operation: string | undefined,
): BubblePlace {
	if (operation !== "multiply") return "tiki-steps";
	return TIKI_HELP.has(scaffoldType) ? "tiki-steps" : "jellyfish-party";
}

/** Both help games play in front of the reef the race runs through. */
const REEF = bubbleArtReady("bgReefRace")
	? bubbleArtUrl("bgReefRace")
	: undefined;

const PLACES: Record<
	BubblePlace,
	{ title: string; backdrop: string | undefined }
> = {
	"jellyfish-party": { title: "ජෙලි මාළු මැජික් සෙල්ලම", backdrop: REEF },
	"tiki-steps": { title: "කකුළු පැටියාගේ බුබුළු පැනීම", backdrop: REEF },
};

/**
 * Nimo's Bubble Trouble (Number Patterns). A seashell blows Nimo into an underwater playground,
 * where a cheeky octopus dares him to a bubble-submarine race through number patterns. A muddled
 * race sends Nimo to Jelly's magic shells or Tiki the crab's stepping shells, where the server picks
 * each help round; then a fresh race on the same pattern. Each new race picks a pattern at random.
 */
export function NimoBubbleTrouble({
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
		areaId: PATTERN_AREA_ID,
		skillId: PLUS_TWO_SKILL_ID,
		summaryFields: PATTERNS_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				bubbleSounds.play("jingle-race", { steady: true });
				bubbleRun(8, 4);
			} else {
				bubbleSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			bubbleSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastPattern = useRef<string | null>(null);
	const board = useMemo(
		() => readPattern(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => bubbleSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			bubbleSounds.play("jingle-train", { steady: true });
		if (phase === "training") bubbleSounds.play("splash");
		if (phase === "return")
			bubbleSounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") bubbleSounds.play("swoosh");
		if (phase === "victory")
			bubbleSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") bubbleSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => bubbleSounds.play("tap");
	const newRace = () => {
		const order = missionOrder(lastPattern.current);
		lastPattern.current = order[0] ?? null;
		void episode.startMission(order);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = bubbleTrainingPlace(
		round?.scaffold_type ?? "",
		typeof helpGame?.operation === "string" ? helpGame.operation : undefined,
	);

	return (
		<LandscapeGameStage label="නිමෝගේ බුබුළු ලෝකයේ වික්‍රමය" onBack={onBack}>
			<section
				className="bubble-trouble"
				data-bubble-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<BubbleRushMission
						key={manifest.revision_id}
						board={board}
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
							<BubbleTrainingBoard
								{...props}
								place={place}
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
						title="නිමෝගේ බුබුළු ලෝකයේ වික්‍රමය"
						image={bubbleArtUrl("nimoIdle")}
						lines={[
							"නිමෝ වෙරළේදී හම්බුණු හක් බෙල්ලකට පිම්බා. ලොකු බුබුළක් ඔහුව මුහුද යටට ගෙනිච්චා!",
							"විහිළුකාර බූවල්ලා නිමෝට බුබුළු රේස් එකකට අභියෝග කරනවා!",
						]}
						action="රේස් එකට යමු!"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="බුබුළු පුහුණුව"
						image={bubbleArtUrl("nimoThink")}
						lines={["රටාව ටිකක් පැටලුණා.", "යාළුවෝ එක්ක පුහුණු වෙලා බලවත් වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={bubbleArtUrl("nimoCheer")}
						lines={["අලුත් බුබුළු රේස් එකක් පටන් ගන්නවා."]}
						action="රේස් එකට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="රේස් එකට යනවා…"
						image={bubbleArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="බුබුළු ශූරයා!"
						image={bubbleArtUrl("nimoCheer")}
						lines={["නිමෝගේ සබ්මැරීනය බුබුළු පාරක් හදාගෙන දිව්වා!"]}
						action="ඊළඟ රේස් එක"
						busy={busy}
						onPress={tap}
						onAction={newRace}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={bubbleArtUrl("nimoIdle")}
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

/** Jelly's magic shells for multiplying help, Tiki's stepping shells for the rest. */
export function BubbleTrainingBoard({
	activity,
	demo,
	hint,
	onResponse,
	place,
	evidence,
}: TrainingBoardProps & {
	place: BubblePlace;
	evidence: ReturnType<typeof useMoveEvidence>;
}) {
	const board = useMemo(
		() => readPattern(activity.game as Record<string, unknown>),
		[activity.game],
	);
	const Board =
		place === "jellyfish-party" && board.operation === "multiply"
			? JellyfishParty
			: TikiSteps;
	return (
		<Board
			board={board}
			demo={demo}
			hint={hint}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}
