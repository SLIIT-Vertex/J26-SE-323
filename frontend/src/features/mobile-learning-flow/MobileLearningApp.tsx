// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import {
	type ComponentType,
	type FunctionComponent,
	type LazyExoticComponent,
	lazy,
	Suspense,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import {
	AREA_GAMES,
	type AreaGameScreen,
	areaGameForArea,
	areaGameForScreen,
} from "../areas/registry";
import { CameraStatusBadge } from "../learner-state/game/CameraStatusBadge";
import type { CameraProblem } from "../learner-state/game/cameraText";
import { LearnerSupportPrompt } from "../learner-state/game/LearnerSupportPrompt";
import {
	learnerStatePromptsEnabled,
	NO_PROMPT_YET,
	nextSupportPrompt,
	type PromptMemory,
	type SupportPrompt,
} from "../learner-state/game/supportPrompts";
import { useGameVisualFeatures } from "../learner-state/game/useGameVisualFeatures";
import { SHARED_LEARNER_ID } from "../papers/hooks";
import { PapersApp } from "../papers/PapersApp";
import { go, usePapersRoute } from "../papers/router";
import { ResearchButton } from "../research-dashboard/ResearchButton";
import { isResearchMode } from "../research-dashboard/researchMode";
import {
	createFixtureRoundClient,
	type FixtureRoundClient,
} from "./api/fixtureRoundClient";
import type {
	DraftMissionRecord,
	DraftTemplateId,
	ExperimentCondition,
	LearnerStateAction,
} from "./api/generated";
import {
	createDraftMissionCatalogClient,
	createLearningFlowClient,
	type DraftMissionCatalogClient,
	LearningFlowApiError,
	type LearningFlowClient,
} from "./api/learningFlowClient";
import { FixtureRoundPlayer } from "./FixtureRoundPlayer";
import { Account } from "./shell/Account";
import { BottomNavigation } from "./shell/BottomNavigation";
import type { AvatarTone } from "./shell/common";
import { DraftTemplatePlayer } from "./shell/DraftTemplatePlayer";
import { GamesHome, type SubjectCode } from "./shell/GamesHome";
import { HomeScreen } from "./shell/HomeScreen";
import {
	LanguageSetup,
	Onboarding,
	ProfileSetup,
	Splash,
} from "./shell/Onboarding";
import { ProgressScreen } from "./shell/ProgressScreen";
import { RewardsHub } from "./shell/RewardsHub";
import { Failure, Settings, type SyncState } from "./shell/Settings";

type LazyNamedComponent<Module, Name extends keyof Module> =
	Module[Name] extends ComponentType<infer Props>
		? LazyExoticComponent<ComponentType<Props>>
		: never;

function lazyNamed<Module, Name extends keyof Module>(
	loader: () => Promise<Module>,
	exportName: Name,
): LazyNamedComponent<Module, Name> {
	// React.lazy's public constraint uses `any`; the conditional return type above
	// restores the exact props inferred from the selected named export.
	// biome-ignore lint/suspicious/noExplicitAny: required by React.lazy's ComponentType constraint
	return lazy<FunctionComponent<any>>(async () => ({
		// biome-ignore lint/suspicious/noExplicitAny: narrowed by LazyNamedComponent at the boundary
		default: (await loader())[exportName] as FunctionComponent<any>,
	})) as unknown as LazyNamedComponent<Module, Name>;
}

const TutorDemo = lazyNamed(
	() => import("../adaptiveTutor/TutorDemo"),
	"TutorDemo",
);

type Screen =
	| "splash"
	| "onboarding"
	| "language"
	| "profile-setup"
	| "home"
	| "learn"
	| "practice"
	| "mindy"
	| "rewards"
	| "account"
	| "progress"
	| "settings"
	| "failure"
	| "draft-player"
	| "fixture-round"
	| AreaGameScreen;

const GAME_SCREENS = new Set<Screen>([
	"draft-player",
	"fixture-round",
	...AREA_GAMES.map((game) => game.screen),
]);

export interface MobileLearningService
	extends Pick<
			LearningFlowClient,
			| "open"
			| "answerBefore"
			| "completeSupport"
			| "withdrawSupport"
			| "presentAfter"
			| "answerAfter"
			| "telemetry"
		>,
		Partial<
			Pick<
				LearningFlowClient,
				"answerSupported" | "cameraConsent" | "setCameraConsent" | "saveProfile"
			>
		> {}

const EPISODE_ENVIRONMENT: "development" | "test" | "pilot" =
	import.meta.env.VITE_MOBILE_LEARNING_ENVIRONMENT === "pilot"
		? "pilot"
		: import.meta.env.VITE_MOBILE_LEARNING_ENVIRONMENT === "test"
			? "test"
			: "development";
const FIXTURE_LOOPS: Partial<Record<string, DraftTemplateId>> = {
	"G5-AREA-MAT-05": "half_set",
	"G5-AREA-MAT-04": "market_mission",
	"G5-AREA-MAT-06": "market_mission",
	"G5-AREA-MAT-07": "parcel_workshop",
	"G5-AREA-MAT-08": "market_mission",
	"G5-AREA-MAT-09": "parcel_workshop",
	"G5-AREA-MAT-10": "market_mission",
	"G5-AREA-MAT-11": "parcel_workshop",
	"G5-AREA-MAT-12": "parcel_workshop",
	"G5-AREA-MAT-13": "pattern_temple",
	"G5-AREA-MAT-14": "pattern_temple",
	"G5-AREA-MAT-15": "market_mission",
	"G5-AREA-MAT-16": "word_workshop",
	"G5-AREA-SIN-01": "pillam_journey",
	"G5-AREA-SIN-02": "punctuation_journey",
	"G5-AREA-SIN-03": "riddle_journey",
	"G5-AREA-SIN-04": "word_workshop",
	"G5-AREA-SIN-05": "word_workshop",
	"G5-AREA-SIN-06": "word_workshop",
	"G5-AREA-SIN-07": "word_workshop",
	"G5-AREA-SIN-08": "word_workshop",
	"G5-AREA-SIN-09": "word_workshop",
	"G5-AREA-SIN-10": "word_workshop",
	"G5-AREA-SIN-11": "word_workshop",
	"G5-AREA-SIN-12": "word_workshop",
	"G5-AREA-SIN-13": "story_studio",
	"G5-AREA-SIN-14": "word_workshop",
	"G5-AREA-SIN-15": "word_workshop",
	"G5-AREA-SIN-17": "word_workshop",
	"G5-AREA-SIN-18": "word_workshop",
	"G5-AREA-SIN-19": "word_workshop",
	"G5-AREA-SIN-20": "word_workshop",
	"G5-AREA-SIN-21": "word_workshop",
	"G5-AREA-SIN-22": "word_workshop",
	"G5-AREA-SIN-23": "word_workshop",
	"G5-AREA-SIN-24": "word_workshop",
	"G5-AREA-SIN-25": "word_workshop",
	"G5-AREA-ENV-01": "eco_explorer",
	"G5-AREA-ENV-02": "eco_explorer",
	"G5-AREA-ENV-03": "eco_explorer",
	"G5-AREA-ENV-04": "eco_explorer",
	"G5-AREA-ENV-05": "eco_explorer",
	"G5-AREA-ENV-06": "eco_explorer",
	"G5-AREA-ENV-07": "eco_explorer",
	"G5-AREA-ENV-08": "eco_explorer",
	"G5-AREA-ENV-09": "eco_explorer",
	"G5-AREA-ENV-10": "eco_explorer",
	"G5-AREA-ENV-11": "eco_explorer",
	"G5-AREA-ENV-12": "eco_explorer",
	"G5-AREA-ENV-13": "eco_explorer",
	"G5-AREA-ENV-14": "eco_explorer",
	"G5-AREA-ENV-15": "eco_explorer",
	"G5-AREA-ENV-16": "eco_explorer",
};
const PLAYABLE_PLACEHOLDER_IDS = new Set(["G5-AREA-SIN-11", "G5-AREA-SIN-12"]);
const PLAYABLE_PLACEHOLDER_MISSIONS: DraftMissionRecord[] = [
	{
		area_id: "G5-AREA-SIN-11",
		cited_node_id: "",
		template_id: "word_workshop",
		outcome_slots: [],
		draft_item_slots: [],
		held_slots: [],
	},
	{
		area_id: "G5-AREA-SIN-12",
		cited_node_id: "",
		template_id: "word_workshop",
		outcome_slots: [],
		draft_item_slots: [],
		held_slots: [],
	},
];

export function MobileLearningApp({
	service,
	initialScreen = "splash",
	enableOnboarding = false,
	// The same child account the Adaptive Tutor (papers) uses.
	learnerId = SHARED_LEARNER_ID,
	engineeringCondition = import.meta.env.VITE_MOBILE_LEARNING_CONDITION ===
	"proposed"
		? "proposed"
		: "baseline",
	catalog,
	fixtureRounds,
}: {
	service?: MobileLearningService;
	initialScreen?: Screen;
	enableOnboarding?: boolean;
	learnerId?: string;
	engineeringCondition?: ExperimentCondition;
	catalog?: Pick<DraftMissionCatalogClient, "listDraftMissions">;
	fixtureRounds?: Pick<FixtureRoundClient, "open" | "answer" | "continue">;
}) {
	const [screen, setScreen] = useState<Screen>(initialScreen);
	const [researchMode] = useState(isResearchMode);
	const papersRoute = usePapersRoute();
	const [learnerName, setLearnerName] = useState("කවිඳු");
	const [avatarTone, setAvatarTone] = useState<AvatarTone>("violet");
	const [busy, setBusy] = useState(false);
	const [failure, setFailure] = useState("BACKEND_UNAVAILABLE");
	const [syncState, setSyncState] = useState<SyncState>(
		navigator.onLine ? "synced" : "offline",
	);
	const [reducedMotion, setReducedMotion] = useState(
		() =>
			globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ??
			false,
	);
	const sessionId = useRef(crypto.randomUUID());
	const apiTail = useRef<Promise<void>>(Promise.resolve());
	const [draftMissions, setDraftMissions] = useState<DraftMissionRecord[]>([]);
	const [draftCatalogStatus, setDraftCatalogStatus] = useState<
		"idle" | "loading" | "ready" | "error"
	>("idle");
	const [selectedAreaId, setSelectedAreaId] = useState<string | null>(null);
	const [openSubject, setOpenSubject] = useState<SubjectCode | null>(null);
	const [draftAnswerSent, setDraftAnswerSent] = useState(false);
	const draftCatalog = useMemo(
		() => catalog ?? createDraftMissionCatalogClient({}),
		[catalog],
	);
	const rounds = useMemo(
		() => fixtureRounds ?? createFixtureRoundClient({ learnerId }),
		[fixtureRounds, learnerId],
	);
	const [cameraConsent, setCameraConsent] = useState(false);
	const [cameraConsentSaving, setCameraConsentSaving] = useState(false);
	const [cameraConsentFailed, setCameraConsentFailed] = useState(false);
	const [cameraProblem, setCameraProblem] = useState<CameraProblem | null>(
		null,
	);
	// Learner-state camera: only with the guardian's consent, and only while a mathematics game
	// screen is open. Frames stay on the device; only 11 numbers go with each answer.
	const cameraEnabled =
		cameraConsent &&
		GAME_SCREENS.has(screen) &&
		screen !== "classroom-action-quest";
	const camera = useGameVisualFeatures({ enabled: cameraEnabled });
	// Remember the last camera problem so settings can explain it after the game is closed.
	useEffect(() => {
		if (camera.status.state === "error") setCameraProblem(camera.status.kind);
		if (camera.status.state === "running") setCameraProblem(null);
	}, [camera.status]);
	const visualFeatures = useRef(camera.visualFeatures);
	visualFeatures.current = camera.visualFeatures;
	// Gentle learner-state prompts after scored answers (off in silent mode).
	const [supportPrompt, setSupportPrompt] = useState<SupportPrompt | null>(
		null,
	);
	const promptMemory = useRef<PromptMemory>(NO_PROMPT_YET);
	const reactToLearnerState = useCallback((action: LearnerStateAction) => {
		if (!learnerStatePromptsEnabled()) return;
		const next = nextSupportPrompt(promptMemory.current, action, Date.now());
		promptMemory.current = next.memory;
		if (next.prompt) setSupportPrompt(next.prompt);
	}, []);
	useEffect(() => {
		if (!GAME_SCREENS.has(screen)) setSupportPrompt(null);
	}, [screen]);
	const api = useMemo(
		() =>
			service ??
			createLearningFlowClient({
				learnerId,
				visualFeatures: () => visualFeatures.current(),
				onLearnerStateAction: reactToLearnerState,
			}),
		[learnerId, service, reactToLearnerState],
	);
	useEffect(() => {
		api.cameraConsent?.().then(setCameraConsent, () => setCameraConsent(false));
	}, [api]);
	const changeCameraConsent = useCallback(
		(granted: boolean) => {
			if (!api.setCameraConsent) return;
			setCameraConsentSaving(true);
			setCameraConsentFailed(false);
			api.setCameraConsent(granted).then(
				(saved) => {
					setCameraConsent(saved);
					setCameraConsentSaving(false);
				},
				() => {
					setCameraConsentFailed(true);
					setCameraConsentSaving(false);
				},
			);
		},
		[api],
	);
	const runApi = useCallback(<T,>(operation: () => Promise<T>): Promise<T> => {
		const result = apiTail.current.then(operation, operation);
		apiTail.current = result.then(
			() => undefined,
			() => undefined,
		);
		return result;
	}, []);

	useEffect(() => {
		let cancelled = false;
		setDraftCatalogStatus("loading");
		void draftCatalog.listDraftMissions().then(
			(loaded) => {
				if (cancelled) return;
				setDraftMissions([
					...loaded.missions.filter(
						(mission) => !PLAYABLE_PLACEHOLDER_IDS.has(mission.area_id),
					),
					...PLAYABLE_PLACEHOLDER_MISSIONS,
				]);
				setDraftCatalogStatus("ready");
			},
			() => {
				if (cancelled) return;
				setDraftMissions([]);
				setDraftCatalogStatus("error");
			},
		);
		return () => {
			cancelled = true;
		};
	}, [draftCatalog]);
	useEffect(() => {
		if (papersRoute) {
			setScreen((current) => (isSetupScreen(current) ? current : "practice"));
			return;
		}
		const path =
			window.location.hash
				.replace(/^#/, "")
				.split("?")[0]
				.replace(/\/+$/, "") || "/";
		if (path === "/" || path === "") {
			setScreen((current) => (current === "practice" ? "home" : current));
		}
	}, [papersRoute]);
	useEffect(() => {
		const online = () => setSyncState("synced");
		const offline = () => setSyncState("offline");
		window.addEventListener("online", online);
		window.addEventListener("offline", offline);
		return () => {
			window.removeEventListener("online", online);
			window.removeEventListener("offline", offline);
		};
	}, []);

	const safeFailure = useCallback((error: unknown) => {
		const code =
			error instanceof LearningFlowApiError || error instanceof Error
				? error.message
				: "BACKEND_UNAVAILABLE";
		setFailure(code);
		setScreen("failure");
		setBusy(false);
	}, []);

	const chooseMission = (areaId: string) => {
		setDraftAnswerSent(false);
		setSelectedAreaId(areaId);
		const mission = draftMissions.find((item) => item.area_id === areaId);
		const game = areaGameForArea(areaId);
		if (game) {
			setScreen(game.screen);
			return;
		}
		if (!mission) return;
		setScreen(isFixtureLoop(mission) ? "fixture-round" : "draft-player");
	};

	const submitDraftAnswer = async () => {
		const mission = draftMissions.find(
			(item) => item.area_id === selectedAreaId,
		);
		if (!mission || mission.template_id === "half_set" || draftAnswerSent) {
			return;
		}
		setBusy(true);
		try {
			const opened = await runApi(() =>
				api.open(
					{
						learner_id: learnerId,
						session_id: sessionId.current,
						grade: 5,
						medium: "si",
						condition: engineeringCondition,
						environment: EPISODE_ENVIRONMENT,
						allow_draft: true,
					},
					crypto.randomUUID(),
				),
			);
			const optionId = opened.manifest?.options[0]?.option_id;
			if (!optionId)
				throw new LearningFlowApiError("DRAFT_ANSWER_UNAVAILABLE", 0);
			await runApi(() =>
				api.answerBefore(
					opened.episode_id,
					{ option_id: optionId },
					crypto.randomUUID(),
				),
			);
			setDraftAnswerSent(true);
			setBusy(false);
		} catch (error) {
			safeFailure(error);
		}
	};

	const sync = useCallback(() => {
		setSyncState(navigator.onLine ? "synced" : "offline");
	}, []);

	const selectedDraftMission = draftMissions.find(
		(item) => item.area_id === selectedAreaId,
	);
	const sharedDraftMission = isSharedDraftMission(selectedDraftMission)
		? selectedDraftMission
		: null;
	const fixtureMission =
		selectedDraftMission && isFixtureLoop(selectedDraftMission)
			? selectedDraftMission
			: null;
	const activeGame = areaGameForScreen(screen);

	return (
		<main
			className="mobile-shell"
			lang="si"
			data-screen={screen}
			data-reduced-motion={reducedMotion ? "true" : undefined}
			data-game={GAME_SCREENS.has(screen) ? "true" : undefined}
		>
			{cameraEnabled && <CameraStatusBadge status={camera.status} />}
			{supportPrompt && GAME_SCREENS.has(screen) && (
				<LearnerSupportPrompt
					prompt={supportPrompt}
					onDismiss={() => setSupportPrompt(null)}
				/>
			)}
			<Suspense fallback={<p role="status">ක්‍රීඩාව පූරණය වෙමින්…</p>}>
				{screen === "splash" && (
					<Splash
						onContinue={() =>
							setScreen(
								enableOnboarding
									? "onboarding"
									: papersRoute
										? "practice"
										: "home",
							)
						}
					/>
				)}
				{screen === "onboarding" && (
					<Onboarding
						onBack={() => setScreen("splash")}
						onContinue={() => setScreen("language")}
					/>
				)}
				{screen === "language" && (
					<LanguageSetup
						onBack={() => setScreen("onboarding")}
						onContinue={() => setScreen("profile-setup")}
					/>
				)}
				{screen === "profile-setup" && (
					<ProfileSetup
						name={learnerName}
						onNameChange={setLearnerName}
						avatarTone={avatarTone}
						onAvatarToneChange={setAvatarTone}
						onBack={() => setScreen("language")}
						onContinue={async () => {
							await api.saveProfile?.(learnerName);
							setScreen(papersRoute ? "practice" : "home");
						}}
					/>
				)}
				{screen === "home" && (
					<HomeScreen
						name={learnerName}
						avatarTone={avatarTone}
						onProfile={() => setScreen("account")}
						onMission={chooseMission}
						onLearn={() => setScreen("learn")}
						onPractice={() => {
							go({ name: "papers" });
							setScreen("practice");
						}}
						onMindy={() => setScreen("mindy")}
						onProgress={() => setScreen("progress")}
						onRewards={() => setScreen("rewards")}
					/>
				)}
				{screen === "learn" && (
					<GamesHome
						missions={draftMissions}
						catalogStatus={draftCatalogStatus}
						onChoose={chooseMission}
						openSubject={openSubject}
						onOpenSubject={setOpenSubject}
					/>
				)}
				{screen === "practice" && (
					<div className="papers-tab">
						<PapersApp embedded route={papersRoute ?? { name: "papers" }} />
					</div>
				)}
				{screen === "mindy" && <TutorDemo embedded />}
				{screen === "rewards" && (
					<RewardsHub onBack={() => setScreen("home")} />
				)}
				{screen === "account" && (
					<Account
						name={learnerName}
						onNameChange={setLearnerName}
						avatarTone={avatarTone}
						onAvatarToneChange={setAvatarTone}
						onBack={() => setScreen("home")}
						onRewards={() => setScreen("rewards")}
						onSettings={() => setScreen("settings")}
						onOnboarding={() => setScreen("onboarding")}
					/>
				)}
				{screen === "progress" && (
					<ProgressScreen
						onLearn={() => setScreen("learn")}
						onPractice={() => {
							go({ name: "papers" });
							setScreen("practice");
						}}
					/>
				)}
				{screen === "settings" && (
					<Settings
						syncState={syncState}
						onSync={sync}
						reducedMotion={reducedMotion}
						setReducedMotion={setReducedMotion}
						cameraConsent={cameraConsent}
						cameraConsentSaving={cameraConsentSaving}
						cameraConsentFailed={cameraConsentFailed}
						cameraProblem={cameraProblem}
						onCameraConsent={changeCameraConsent}
						onBack={() => setScreen("home")}
					/>
				)}
				{screen === "failure" && (
					<Failure code={failure} onSafePractice={() => setScreen("home")} />
				)}
				{screen === "fixture-round" && fixtureMission && (
					<FixtureRoundPlayer
						mission={fixtureMission}
						sessionId={sessionId.current}
						rounds={rounds}
						busy={busy}
						onBusy={setBusy}
						onFailure={safeFailure}
						onBack={() => setScreen("learn")}
					/>
				)}
				{activeGame && (
					<activeGame.Component
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "draft-player" && sharedDraftMission && (
					<DraftTemplatePlayer
						mission={sharedDraftMission}
						busy={busy}
						submitted={draftAnswerSent}
						onSubmit={submitDraftAnswer}
						onBack={() => setScreen("learn")}
					/>
				)}
			</Suspense>
			{["home", "learn", "practice", "mindy", "progress"].includes(screen) && (
				<BottomNavigation
					active={screen}
					onNavigate={(destination) => {
						if (destination === "practice") {
							go({ name: "papers" });
							setScreen("practice");
							return;
						}
						if (papersRoute) {
							window.location.hash = "#/";
						}
						setScreen(destination);
					}}
				/>
			)}
			{researchMode && (screen === "learn" || GAME_SCREENS.has(screen)) && (
				<ResearchButton learnerId={learnerId} />
			)}
		</main>
	);
}

function isSetupScreen(screen: Screen): boolean {
	return ["splash", "onboarding", "language", "profile-setup"].includes(screen);
}

function isFixtureLoop(mission: DraftMissionRecord): boolean {
	return FIXTURE_LOOPS[mission.area_id] === mission.template_id;
}

function isSharedDraftMission(
	mission: DraftMissionRecord | undefined,
): mission is DraftMissionRecord & {
	template_id: Exclude<DraftTemplateId, "half_set">;
} {
	return mission !== undefined && mission.template_id !== "half_set";
}
