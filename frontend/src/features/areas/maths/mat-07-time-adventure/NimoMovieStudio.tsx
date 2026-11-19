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
import { FastForward } from "./FastForward";
import { MovieMayhem } from "./MovieMayhem";
import { PuppetShow } from "./PuppetShow";
import { ACTORS, studioArtReady, studioArtUrl } from "./studioArt";
import {
	ELAPSED_SKILL_ID,
	missionOrder,
	readTask,
	STUDIO_AREA_ID,
	type StudioPlace,
	studioTrainingPlace,
} from "./studioRules";
import { studioSounds } from "./studioSounds";
import "./movie-studio.css";

/** The interaction-summary fields the Time flow accepts. */
const TIME_SUMMARY_FIELDS = [
	"move_count",
	"correction_count",
	"first_action_ms",
	"active_time_ms",
	"attempt_count",
] as const;

const LOT = studioArtReady("bgStudio") ? studioArtUrl("bgStudio") : undefined;

const PLACES: Record<
	StudioPlace,
	{ title: string; backdrop: string | undefined }
> = {
	"fast-forward": { title: "කාලය ඉස්සරහට! ආපස්සට!", backdrop: LOT },
	"puppet-show": { title: "ටික් ටොක් රූකඩ සෙල්ලම!", backdrop: LOT },
};

/** The same scene always gets the same actor; different scenes get different ones. */
function actorFor(revision: string) {
	let hash = 0;
	for (const char of revision) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
	return ACTORS[hash % ACTORS.length] ?? "zombie";
}

/**
 * Nimo's Silly Movie Studio (Time). Bakā the owl director hands Nimo the clapperboard: each scene
 * needs its length, its start on the 24-hour clock, or two scenes' lengths together or apart. A
 * muddled scene sends Nimo to the editing room or the puppet theatre, where the server picks each
 * help round; then a fresh scene of the same kind. Each new scene picks its kind at random.
 */
export function NimoMovieStudio({
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
		areaId: STUDIO_AREA_ID,
		skillId: ELAPSED_SKILL_ID,
		summaryFields: TIME_SUMMARY_FIELDS,
		onMissionResult: (correct) => {
			if (correct) {
				studioSounds.play("jingle-scene", { steady: true });
				studioSounds.play("sparkle", { delay: 0.8, volume: 0.6 });
			} else {
				studioSounds.play("puzzled");
			}
		},
		onNextHelpRound: (previousCorrect) =>
			studioSounds.play(previousCorrect === false ? "hmm" : "sparkle", {
				volume: 0.7,
			}),
	});
	const { phase, manifest, support, busy, evidence } = episode;
	const lastScene = useRef<string | null>(null);
	const task = useMemo(
		() => readTask(manifest?.game as Record<string, unknown> | undefined),
		[manifest],
	);

	useEffect(() => studioSounds.preload(), []);

	useEffect(() => {
		if (phase === "to-training")
			studioSounds.play("jingle-train", { steady: true });
		if (phase === "training") studioSounds.play("reel");
		if (phase === "return")
			studioSounds.play("jingle-return", { steady: true });
		if (phase === "withdrawing") studioSounds.play("clap");
		if (phase === "victory")
			studioSounds.play("jingle-victory", { steady: true });
		if (phase === "rest") studioSounds.play("jingle-rest", { steady: true });
	}, [phase]);

	const tap = () => studioSounds.play("tap");
	const newScene = () => {
		const skills = missionOrder(lastScene.current);
		lastScene.current = skills[0] ?? null;
		void episode.startMission(skills);
	};
	const round =
		support?.game_manifest.schema_version === "support-round-v1"
			? support.game_manifest
			: null;
	const helpGame = (round?.activity ?? round?.worked_example)?.game as
		| Record<string, unknown>
		| undefined;
	const place = studioTrainingPlace(readTask(helpGame));

	return (
		<LandscapeGameStage label="නිමෝගේ හිනා සිනමා ලෝකය" onBack={onBack}>
			<section
				className="movie-studio"
				data-studio-phase={phase}
				data-episode-id={episode.episodeId ?? undefined}
			>
				{phase === "mission" && manifest && (
					<MovieMayhem
						key={manifest.revision_id}
						task={task}
						prompt={manifest.prompt_si}
						actor={actorFor(manifest.revision_id)}
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
							<StudioTrainingBoard {...props} evidence={evidence} />
						)}
						onAnswer={(response, activity) =>
							void episode.answerTraining(response, activity)
						}
						onViewComplete={() => void episode.finishDemonstration()}
					/>
				)}
				{phase === "story" && (
					<GameStoryCard
						title="නිමෝගේ හිනා සිනමා ලෝකය"
						image={studioArtUrl("nimoDirector")}
						lines={[
							"බකා බකමූණා අධ්‍යක්ෂක නිමෝට ක්ලැපර් පුවරුව දුන්නා: අද නිමෝ තමයි අලුත් අධ්‍යක්ෂක!",
							"හැම දර්ශනයක්ම පටන් ගන්න, ඉවර වෙන, ගත වෙන වෙලාව හොයලා හිනායන චිත්‍රපටයක් හදමු!",
						]}
						action="රූගත කරමු!"
						busy={busy}
						onPress={tap}
						onAction={newScene}
					/>
				)}
				{phase === "to-training" && (
					<GameStoryCard
						title="ස්ටූඩියෝවේ රහස් කාමර"
						image={studioArtUrl("nimoThink")}
						lines={["වෙලාව ටිකක් පැටලුණා.", "ස්ටූඩියෝවේ රහස් කාමරවල පුහුණු වෙලා බලවත් වෙමු!"]}
						action="යමු!"
						onPress={tap}
						onAction={episode.goTraining}
					/>
				)}
				{phase === "return" && (
					<GameStoryCard
						title="දැන් සූදානම්!"
						image={studioArtUrl("nimoCheer")}
						lines={["අලුත් දර්ශනයක් රූගත කරන්න සූදානම්."]}
						action="සෙට් එකට යමු"
						onPress={tap}
						onAction={episode.flyBack}
					/>
				)}
				{phase === "withdrawing" && (
					<GameStoryCard
						title="සෙට් එකට යනවා…"
						image={studioArtUrl("nimoIdle")}
						lines={[]}
						busy
					/>
				)}
				{phase === "victory" && (
					<GameStoryCard
						title="කට්!"
						image={studioArtUrl("nimoCheer")}
						lines={["දර්ශනය නියමයි! නළු නිළියෝ සතුටින් නටනවා!"]}
						action="ඊළඟ දර්ශනය"
						busy={busy}
						onPress={tap}
						onAction={newScene}
					/>
				)}
				{phase === "rest" && (
					<GameStoryCard
						title="හොඳ උත්සාහයක්!"
						image={studioArtUrl("nimoIdle")}
						lines={["අද නිමෝ ගොඩක් ඉගෙන ගත්තා.", "ආයෙත් දර්ශනයක් රූගත කරමු!"]}
						action="ආයෙත් යමු"
						busy={busy}
						onPress={tap}
						onAction={newScene}
					/>
				)}
			</section>
		</LandscapeGameStage>
	);
}

/** Durations in the editing room; clocks, 24-hour time and units at the puppet theatre. */
export function StudioTrainingBoard({
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
		studioTrainingPlace(task) === "fast-forward" ? FastForward : PuppetShow;
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
