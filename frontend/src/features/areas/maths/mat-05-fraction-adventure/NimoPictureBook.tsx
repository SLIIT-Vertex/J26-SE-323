import { useEffect, useMemo } from "react";
import { GameStoryCard } from "../../../mobile-learning-flow/landscape/GameStoryCard";
import { LandscapeGameStage } from "../../../mobile-learning-flow/landscape/LandscapeGameStage";
import {
	type TrainingBoardProps,
	TrainingRoom,
} from "../../../mobile-learning-flow/landscape/TrainingRoom";
import { useHardFirstEpisode } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import type { AreaGameProps } from "../../registry";
import { bookArtReady, bookArtUrl } from "./bookArt";
import {
	BOOK_AREA_ID,
	type BookPlace,
	bookTrainingPlace,
	missionOrder,
	QUARTER_TABLE_SKILL_ID,
	readPage,
} from "./bookRules";
import { bookSounds } from "./bookSounds";
import { ColorSplashComic } from "./ColorSplashComic";
import { FoldPop } from "./FoldPop";
import { StickerParty } from "./StickerParty";
import "./picture-book.css";

/** The interaction-summary fields the Fractions flow accepts. */
const FRACTIONS_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

/** Both help games play in front of the picture-book room. */
const ROOM = bookArtReady("bgBook") ? bookArtUrl("bgBook") : undefined;

const PLACES: Record<
	BookPlace,
	{ title: string; backdrop: string | undefined }
> = {
	"sticker-party": { title: "ස්ටිකර් බෙදන සෙල්ලම", backdrop: ROOM },
	"fold-and-pop": { title: "නමමු! පාට කරමු! මැජික් බලමු!", backdrop: ROOM },
};

/**
 * Nimo's Magic Picture Book (Fractions). Colouring a page of a huge blank picture book brings it to
 * life; Pipi the paper bird asks for a fraction of each comic page. A muddled page sends Nimo to the
 * sticker party or to fold-and-pop, where the server picks each help round; then a fresh page of the
 * same kind. Each new page is a quarter garden or tenth panels, at random.
 */
export function NimoPictureBook({
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
		areaId: BOOK_AREA_ID,
		skillId: QUARTER_TABLE_SKILL_ID,
		summaryFields: FRACTIONS_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				bookSounds.play("jingle-comic", { steady: true });
				bookSounds.play("magic", { delay: 0.7, volume: 0.6 });
			} else {
				bookSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			bookSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const page = useMemo(
		() => readPage(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => bookSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			bookSounds.play("jingle-train", { steady: true });
		if (phase === "training") bookSounds.play("page");
		if (phase === "return") bookSounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") bookSounds.play("page");
		if (phase === "victory")
			bookSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") bookSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => bookSounds.play("tap");
	const newPage = () => void episode.startMission(missionOrder());
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = bookTrainingPlace(readPage(helpGame));
	const nimo = bookArtReady("nimoPainter") ? "nimoPainter" : "nimoIdle";

	return (
		<LandscapeGameStage label="නිමෝගේ මැජික් චිත්‍ර පොත" onBack={onBack}>
			<section
				className="picture-book"
				data-book-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<ColorSplashComic
						key={manifest.revision_id}
						page={page}
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
							<BookTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ මැජික් චිත්‍ර පොත"
						image={bookArtUrl(nimo)}
						lines={[
							"වැස්ස දවසක නිමෝට හිස් පිටු තියෙන ලොකු චිත්‍ර පොතක් හම්බුණා. පාට කරපු ගමන් චිත්‍ර පණ ලබනවා!",
							"කඩදාසි කුරුල්ලා පිපී එක්ක ලෝකයේ හිනායන්නම චිත්‍ර කතාව හදමු!",
						]}
						action="පොත අරිමු!"
						busy={busy}
						onPress={tap}
						onAction={newPage}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="පොතේ රහස් පිටු"
						image={bookArtUrl("nimoThink")}
						lines={["පාට ගණන ටිකක් පැටලුණා.", "පොතේ රහස් පිටුවල සෙල්ලම් කරලා බලවත් වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={bookArtUrl("nimoCheer")}
						lines={["අලුත් චිත්‍ර පිටුවක් පාට කරන්න බලාගෙන ඉන්නවා."]}
						action="පිටුවට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="පිටුව පෙරළනවා…"
						image={bookArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="චිත්‍රය පණ ලැබුවා!"
						image={bookArtUrl("nimoCheer")}
						lines={["මල් නටනවා, පිපී සතුටින් පියාඹනවා!"]}
						action="ඊළඟ පිටුව"
						busy={busy}
						onPress={tap}
						onAction={newPage}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={bookArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් පිටුවක් පාට කරමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newPage}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Sharing and quarter-table pages at the sticker party; shapes and tenths in fold-and-pop. */
export function BookTrainingBoard({
	activity,
	demo,
	hint,
	onResponse,
	evidence,
}: TrainingBoardProps & { evidence: ReturnType<typeof useMoveEvidence> }) {
	const page = useMemo(
		() => readPage(activity.game as Record<string, unknown>),
		[activity.game],
	);
	const Board =
		bookTrainingPlace(page) === "sticker-party" ? StickerParty : FoldPop;
	return (
		<Board
			page={page}
			demo={demo}
			hint={hint}
			evidence={evidence}
			onResponse={onResponse}
		/>
	);
}
