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
import { BalanceScale } from "./BalanceScale";
import { ParcelCart } from "./ParcelCart";
import { WeighingRoom } from "./WeighingRoom";
import { weighArtReady, weighArtUrl } from "./weighArt";
import {
	ARITHMETIC_SKILL_ID,
	missionOrder,
	readTask,
	WEIGH_AREA_ID,
	type WeighPlace,
	weighTrainingPlace,
} from "./weighRules";
import { weighSounds } from "./weighSounds";
import "./parcel-day.css";

/** The interaction-summary fields the Mass flow accepts. */
const MASS_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

const backdrop = (key: "bgYard" | "bgRoom") =>
	weighArtReady(key) ? weighArtUrl(key) : undefined;
const YARD = backdrop("bgYard");
const ROOM = backdrop("bgRoom");

const PLACES: Record<
	WeighPlace,
	{ title: string; backdrop: string | undefined }
> = {
	"balance-scale": { title: "තරාදිය සම කරමු!", backdrop: ROOM },
	"weighing-room": { title: "බර බලලා හොයමු!", backdrop: ROOM },
};

/**
 * Nimo's Parcel Day (Mass). Mystery boxes are waiting for the village: Nimo weighs them, loads his
 * cart and works out the load. A muddled load sends him to the old balance or the weighing room,
 * where the server picks each help round; then a fresh delivery of the same kind. Each new delivery
 * picks its kind at random.
 */
export function NimoParcelDay({
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
		areaId: WEIGH_AREA_ID,
		skillId: ARITHMETIC_SKILL_ID,
		summaryFields: MASS_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				weighSounds.play("pop", { delay: 0.6 });
				weighSounds.play("jingle-delivered", { steady: true, delay: 0.9 });
			} else {
				weighSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			weighSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastDelivery = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => weighSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			weighSounds.play("jingle-train", { steady: true });
		if (phase === "return") weighSounds.play("jingle-return", { steady: true });
		if (phase === "victory")
			weighSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") weighSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => weighSounds.play("tap");
	const newDelivery = () => {
		const skills = missionOrder(lastDelivery.current);
		lastDelivery.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = weighTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝගේ පුංචි බඩු පෙට්ටි ගමන" onBack={onBack}>
			<section
				className="parcel-day"
				data-parcel-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
				style={
					YARD
						? ({ "--parcel-bg": `url("${YARD}")` } as CSSProperties)
						: undefined
				}
			>
				{phase === "mission" && manifest && (
					<ParcelCart
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
							<ParcelTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ පුංචි බඩු පෙට්ටි ගමන"
						image={weighArtUrl("nimoIdle")}
						lines={[
							"ගමේ යාළුවන්ට යවන්න පුදුම බඩු පෙට්ටි ගොඩක් තියෙනවා!",
							"මේ පෙට්ටි ටික ගෙනියමුද? මුලින්ම බර බලමු!",
						]}
						action="පටවමු!"
						busy={busy}
						onPress={tap}
						onAction={newDelivery}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="පොඩි නැවතීමක්"
						image={weighArtUrl("nimoThink")}
						lines={["බර ගාණ පොඩ්ඩක් පැටලුණා.", "තරාදි එක්ක පොඩ්ඩක් සෙල්ලම් කරමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් ලෑස්තියි!"
						image={weighArtUrl("nimoCheer")}
						lines={["අලුත් පෙට්ටි ටිකක් ලෑස්තියි."]}
						action="කරත්තේ ළඟට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="කරත්තේ ළඟට යනවා…"
						image={weighArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="පෙට්ටි ගෙනිච්චා!"
						image={weighArtUrl("nimoCheer")}
						lines={["පෙට්ටිය ඇරියාම පුදුම සෙල්ලම් බඩුවක්! 🎁"]}
						action="ඊළඟ ගමන"
						busy={busy}
						onPress={tap}
						onAction={newDelivery}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={weighArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් පෙට්ටි පටවමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newDelivery}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Weights and sums at the balance; the five scales in the weighing room. */
export function ParcelTrainingBoard({
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
		weighTrainingPlace(task) === "weighing-room" ? WeighingRoom : BalanceScale;
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
