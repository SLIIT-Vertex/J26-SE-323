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
import { CashBox } from "./CashBox";
import { CoinBox } from "./CoinBox";
import { GroceryShop } from "./GroceryShop";
import { shopArtReady, shopArtUrl } from "./shopArt";
import {
	missionOrder,
	readTask,
	SHOP_AREA_ID,
	SHOP_SKILL_ID,
	type ShopPlace,
	shopTrainingPlace,
} from "./shopRules";
import { shopSounds } from "./shopSounds";
import "./nimo-shop.css";

/** The interaction-summary fields the Money flow accepts. */
const MONEY_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

const backdrop = (key: "bgShop" | "bgPlayshop") =>
	shopArtReady(key) ? shopArtUrl(key) : undefined;
const SHOP = backdrop("bgShop");

const PLACES: Record<
	ShopPlace,
	{ title: string; backdrop: string | undefined }
> = {
	"cash-box": { title: "සල්ලි මාරු කරමු!", backdrop: SHOP },
	"coin-box": { title: "කාසි පෙට්ටිය!", backdrop: backdrop("bgPlayshop") },
};

/**
 * Nimo's Shopping Day (Money). The school party needs rice, dhal and sugar: Nimo fills his basket
 * at the little shop, works out the bill and pays. A muddled bill sends him to the talking cash box
 * or the play shop's coin box, where the server picks each help round; then a fresh shopping trip
 * of the same kind. Each new trip picks its kind at random.
 */
export function NimoShopDay({
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
		areaId: SHOP_AREA_ID,
		skillId: SHOP_SKILL_ID,
		summaryFields: MONEY_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				shopSounds.play("coin");
				shopSounds.play("jingle-paid", { steady: true, delay: 0.6 });
			} else {
				shopSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			shopSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastTrip = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => shopSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			shopSounds.play("jingle-train", { steady: true });
		if (phase === "return") shopSounds.play("jingle-return", { steady: true });
		if (phase === "victory")
			shopSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") shopSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => shopSounds.play("tap");
	const newTrip = () => {
		const skills = missionOrder(lastTrip.current);
		lastTrip.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = shopTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝගේ සාප්පු දවස" onBack={onBack}>
			<section
				className="shop-day"
				data-shop-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
				style={
					SHOP
						? ({ "--shop-bg": `url("${SHOP}")` } as CSSProperties)
						: undefined
				}
			>
				{phase === "mission" && manifest && (
					<GroceryShop
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
							<ShopTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ සාප්පු දවස"
						image={shopArtUrl("nimoIdle")}
						lines={[
							"අද ඉස්කෝලේ පුංචි උත්සවයක්! කෑම හදන්න හාල්, පරිප්පු, සීනි ඕනේ.",
							"අද අපි කඩේට යමු! ඕනේ බඩු ටික හොයාගමුද?",
						]}
						action="කඩේට යමු!"
						busy={busy}
						onPress={tap}
						onAction={newTrip}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="පොඩි නැවතීමක්"
						image={shopArtUrl("nimoThink")}
						lines={["සල්ලි ගණන පොඩ්ඩක් පැටලුණා.", "සල්ලි එක්ක පොඩ්ඩක් සෙල්ලම් කරමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් ලෑස්තියි!"
						image={shopArtUrl("nimoCheer")}
						lines={["අලුත් බඩු ලැයිස්තුවක් තියෙනවා."]}
						action="කඩේට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="කඩේට යනවා…"
						image={shopArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="බඩු ටික ගත්තා!"
						image={shopArtUrl("nimoCheer")}
						lines={["දැන් උත්සවයට කෑම හදන්න පුළුවන්! 🍚"]}
						action="ඊළඟ ලැයිස්තුව"
						busy={busy}
						onPress={tap}
						onAction={newTrip}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={shopArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් කඩේට යමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newTrip}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Sums and shopping at the cash box; coins and notes at the coin box. */
export function ShopTrainingBoard({
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
	const Board = shopTrainingPlace(task) === "coin-box" ? CoinBox : CashBox;
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
