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
import { cafeArtReady, cafeArtUrl } from "./cafeArt";
import {
	CAFE_AREA_ID,
	type CafePlace,
	cafeTrainingPlace,
	missionOrder,
	ONE_EXCHANGE_SKILL_ID,
	readOrder,
} from "./cafeRules";
import { cafeSounds } from "./cafeSounds";
import { FluffballFeast } from "./FluffballFeast";
import { MonsterOrderMission } from "./MonsterOrderMission";
import { SnackSwap } from "./SnackSwap";
import "./monster-cafe.css";

/** The interaction-summary fields the Subtraction flow accepts that the shared evidence counts. */
const SUBTRACTION_SUMMARY_FIELDS = [
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

/** Both help games play in front of the café counter. */
const CAFE = cafeArtReady("bgCafe") ? cafeArtUrl("bgCafe") : undefined;

const PLACES: Record<
	CafePlace,
	{ title: string; backdrop: string | undefined }
> = {
	"snack-swap": { title: "මැජික් කෑම පැකට් මාරුව", backdrop: CAFE },
	"fluffball-feast": { title: "බඩගිනි රාක්ෂ පැටව්", backdrop: CAFE },
};

/**
 * Nimo's Midnight Monster Café (Subtraction). Nimo is the chef for one night at a café whose
 * customers are little monsters: every order asks what is left after they eat. A muddled order
 * sends Nimo to the magic snack swap or to feed the fluffballs, where the server picks each help
 * round; then a fresh order of the same kind. Each new order picks its kind at random.
 */
export function NimoMonsterCafe({
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
		areaId: CAFE_AREA_ID,
		skillId: ONE_EXCHANGE_SKILL_ID,
		summaryFields: SUBTRACTION_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				cafeSounds.play("jingle-order", { steady: true });
				cafeSounds.play("sparkle", { delay: 0.8, volume: 0.6 });
			} else {
				cafeSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			cafeSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastOrder = useRef<string | null>(null);
	const order = useMemo(
		() => readOrder(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => cafeSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			cafeSounds.play("jingle-train", { steady: true });
		if (phase === "training") cafeSounds.play("unwrap");
		if (phase === "return") cafeSounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") cafeSounds.play("shelf");
		if (phase === "victory")
			cafeSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") cafeSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => cafeSounds.play("tap");
	const newOrder = () => {
		const skills = missionOrder(lastOrder.current);
		lastOrder.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const place = cafeTrainingPlace(
		round?.scaffold_type ?? "",
		(round?.activity ?? round?.worked_example)?.skill_id ??
			round?.skill_id ??
			"",
	);

	return (
		<LandscapeGameStage label="නිමෝගේ මධ්‍යම රාත්‍රී රාක්ෂ කැෆේ" onBack={onBack}>
			<section
				className="monster-cafe"
				data-cafe-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<MonsterOrderMission
						key={manifest.revision_id}
						order={order}
						prompt={
							order.story ? manifest.prompt_si : "රාක්ෂයෝ කෑවට පස්සේ කෑම කීයක් ඉතිරිද?"
						}
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
							<CafeTrainingBoard {...props} place={place} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ මධ්‍යම රාත්‍රී රාක්ෂ කැෆේ"
						image={cafeArtUrl(
							cafeArtReady("nimoChef") ? "nimoChef" : "nimoIdle",
						)}
						lines={[
							"මධ්‍යම රාත්‍රියට විතරක් අරින පුංචි කැෆේ එකක් නිමෝට හම්බුණා. ඇතුළේ ඉන්නේ හුරතල් පුංචි රාක්ෂයෝ!",
							"අද රෑ නිමෝ තමයි කැෆේ එකේ කෝකියා. රාක්ෂයෝ කෑවට පස්සේ ඉතිරි කීයද කියලා හොයමු!",
						]}
						action="කැෆේ එක අරිමු!"
						busy={busy}
						onPress={tap}
						onAction={newOrder}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="කුස්සියේ පුහුණුව"
						image={cafeArtUrl("nimoThink")}
						lines={["ඇණවුම ටිකක් පැටලුණා.", "කුස්සියේ පුහුණු වෙලා බලවත් වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={cafeArtUrl("nimoCheer")}
						lines={["අලුත් ඇණවුමක් කවුන්ටරයට ආවා."]}
						action="කවුන්ටරයට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="කවුන්ටරයට යනවා…"
						image={cafeArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="ඇණවුම හරි!"
						image={cafeArtUrl("nimoCheer")}
						lines={["රාක්ෂයෝ සතුටින් බඩ අතගානවා!"]}
						action="ඊළඟ ඇණවුම"
						busy={busy}
						onPress={tap}
						onAction={newOrder}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={cafeArtUrl("nimoIdle")}
						lines={["අද රෑ නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් ඇණවුමක් ගමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newOrder}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** The snack swap for most help, the fluffball feeding for the plainest. */
export function CafeTrainingBoard({
	activity,
	demo,
	hint,
	onResponse,
	place,
	evidence,
}: TrainingBoardProps & {
	place: CafePlace;
	evidence: ReturnType<typeof useMoveEvidence>;
}) {
	const order = useMemo(
		() => readOrder(activity.game as Record<string, unknown>),
		[activity.game],
	);
	const Board = place === "fluffball-feast" ? FluffballFeast : SnackSwap;
	return (
		<Board
			order={order}
			demo={demo}
			hint={hint}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}
