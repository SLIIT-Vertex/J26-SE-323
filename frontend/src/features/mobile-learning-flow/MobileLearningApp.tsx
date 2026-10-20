// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { Capacitor } from "@capacitor/core";
import {
	type ComponentType,
	type FunctionComponent,
	lazy,
	type LazyExoticComponent,
	type ReactNode,
	Suspense,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { PapersApp } from "../papers/PapersApp";
import { go, usePapersRoute } from "../papers/router";
import { CameraConsentCard } from "../learner-state/game/CameraConsentCard";
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
import {
	createFixtureRoundClient,
	type FixtureRoundClient,
} from "./api/fixtureRoundClient";
import type {
	ChildEpisodeResponse,
	DraftMissionRecord,
	DraftTemplateId,
	ExperimentCondition,
	LearnerStateAction,
	PresentationManifest,
	SupportView,
} from "./api/generated";
import {
	createDraftMissionCatalogClient,
	createLearningFlowClient,
	type DraftMissionCatalogClient,
	LearningFlowApiError,
	type LearningFlowClient,
} from "./api/learningFlowClient";
import type { ServerScore } from "./api/runtime";
import type { HalfSetManifest, SceneDomainEvent } from "./bridge/contracts";
import { FixtureRoundPlayer } from "./FixtureRoundPlayer";
import { HalfSetGame } from "./game/HalfSetGame";
import { ENGLISH_LEARNING_AREAS, learningAreaName } from "./learningAreas";
import {
	EncryptedEventQueue,
	IndexedDbNonExtractableKeyProvider,
	MemoryEncryptedStore,
	WebCryptoLocalStore,
} from "./offline/EncryptedEventQueue";

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

const NumberWorldJourney = lazyNamed(
	() => import("../skill-area-1/NumberWorldJourney"),
	"NumberWorldJourney",
);
const AdditionAdventureJourney = lazyNamed(
	() => import("../skill-area-2/AdditionAdventureJourney"),
	"AdditionAdventureJourney",
);
const NumberPatternJourney = lazyNamed(
	() => import("../skill-area-3/NumberPatternJourney"),
	"NumberPatternJourney",
);
const SubtractionAdventureJourney = lazyNamed(
	() => import("../skill-area-4/SubtractionAdventureJourney"),
	"SubtractionAdventureJourney",
);
const FractionAdventureJourney = lazyNamed(
	() => import("../skill-area-5/FractionAdventureJourney"),
	"FractionAdventureJourney",
);
const MultiplicationAdventureJourney = lazyNamed(
	() => import("../skill-area-6/MultiplicationAdventureJourney"),
	"MultiplicationAdventureJourney",
);
const TimeAdventureJourney = lazyNamed(
	() => import("../skill-area-7/TimeAdventureJourney"),
	"TimeAdventureJourney",
);
const DivisionAdventureJourney = lazyNamed(
	() => import("../skill-area-8/DivisionAdventureJourney"),
	"DivisionAdventureJourney",
);
const DistanceAdventureJourney = lazyNamed(
	() => import("../skill-area-9/DistanceAdventureJourney"),
	"DistanceAdventureJourney",
);
const MoneyAdventureJourney = lazyNamed(
	() => import("../skill-area-10/MoneyAdventureJourney"),
	"MoneyAdventureJourney",
);
const CapacityAdventureJourney = lazyNamed(
	() => import("../skill-area-11/CapacityAdventureJourney"),
	"CapacityAdventureJourney",
);
const MassAdventureJourney = lazyNamed(
	() => import("../skill-area-12/MassAdventureJourney"),
	"MassAdventureJourney",
);
const ShapeAdventureJourney = lazyNamed(
	() => import("../skill-area-13/ShapeAdventureJourney"),
	"ShapeAdventureJourney",
);
const DirectionAdventureJourney = lazyNamed(
	() => import("../skill-area-14/DirectionAdventureJourney"),
	"DirectionAdventureJourney",
);
const DecimalAdventureJourney = lazyNamed(
	() => import("../skill-area-15/DecimalAdventureJourney"),
	"DecimalAdventureJourney",
);
const RomanAdventureJourney = lazyNamed(
	() => import("../skill-area-16/RomanAdventureJourney"),
	"RomanAdventureJourney",
);
const ClassroomActionQuest = lazyNamed(
	() => import("../english-area-1/ClassroomActionQuest"),
	"ClassroomActionQuest",
);
const SriLankaDiscovery = lazyNamed(
	() => import("../english-area-2/SriLankaDiscovery"),
	"SriLankaDiscovery",
);
const PlantExplorerQuest = lazyNamed(
	() => import("../english-area-3/PlantExplorerQuest"),
	"PlantExplorerQuest",
);
const WildlifeRangerQuest = lazyNamed(
	() => import("../english-area-4/WildlifeRangerQuest"),
	"WildlifeRangerQuest",
);
const EverydayObjectQuest = lazyNamed(
	() => import("../english-area-5/EverydayObjectQuest"),
	"EverydayObjectQuest",
);
const IslandFoodFestival = lazyNamed(
	() => import("../english-area-6/IslandFoodFestival"),
	"IslandFoodFestival",
);
const RainbowWardrobeQuest = lazyNamed(
	() => import("../english-area-7/RainbowWardrobeQuest"),
	"RainbowWardrobeQuest",
);
const WaterWorksAdventure = lazyNamed(
	() => import("../english-area-8/WaterWorksAdventure"),
	"WaterWorksAdventure",
);
const TransitTerminalQuest = lazyNamed(
	() => import("../english-area-9/TransitTerminalQuest"),
	"TransitTerminalQuest",
);
const BloomBuilderGarden = lazyNamed(
	() => import("../english-area-10/BloomBuilderGarden"),
	"BloomBuilderGarden",
);
const WorkplaceLinkCity = lazyNamed(
	() => import("../english-area-11/WorkplaceLinkCity"),
	"WorkplaceLinkCity",
);
const FamilyWordConstellation = lazyNamed(
	() => import("../english-area-12/FamilyWordConstellation"),
	"FamilyWordConstellation",
);
const EarthSkyExplorer = lazyNamed(
	() => import("../english-area-13/EarthSkyExplorer"),
	"EarthSkyExplorer",
);
const SchoolHomeBlueprintQuest = lazyNamed(
	() => import("../english-area-14/SchoolHomeBlueprintQuest"),
	"SchoolHomeBlueprintQuest",
);
const InformationStation = lazyNamed(
	() => import("../english-area-15/InformationStation"),
	"InformationStation",
);
const HeritageMuseumQuest = lazyNamed(
	() => import("../english-area-16/HeritageMuseumQuest"),
	"HeritageMuseumQuest",
);
const ClassroomLanguageLive = lazyNamed(
	() => import("../english-area-17/ClassroomLanguageLive"),
	"ClassroomLanguageLive",
);
const ConversationStreet = lazyNamed(
	() => import("../english-area-18/ConversationStreet"),
	"ConversationStreet",
);
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
	| "mission"
	| "overview"
	| "baseline"
	| "difficulty"
	| "support"
	| "withdrawal"
	| "after"
	| "result"
	| "reward"
	| "summary"
	| "progress"
	| "settings"
	| "failure"
	| "draft-player"
	| "fixture-round"
	| "number-world"
	| "addition-adventure"
	| "number-pattern-adventure"
	| "subtraction-adventure"
	| "fraction-adventure"
	| "multiplication-adventure"
	| "time-adventure"
	| "division-adventure"
	| "distance-adventure"
	| "money-adventure"
	| "capacity-adventure"
	| "mass-adventure"
	| "shape-adventure"
	| "direction-adventure"
	| "decimal-adventure"
	| "roman-adventure"
	| "classroom-action-quest"
	| "sri-lanka-discovery"
	| "plant-explorer"
	| "wildlife-ranger"
	| "everyday-object-quest"
	| "island-food-festival"
	| "rainbow-wardrobe-quest"
	| "water-works-adventure"
	| "transit-terminal-quest"
	| "bloom-builder-garden"
	| "workplace-link-city"
	| "family-word-constellation"
	| "earth-sky-explorer"
	| "blueprint-quest"
	| "information-station"
	| "heritage-museum"
	| "classroom-language-live"
	| "conversation-street";

const GAME_SCREENS = new Set<Screen>([
	"mission",
	"overview",
	"baseline",
	"difficulty",
	"support",
	"withdrawal",
	"after",
	"result",
	"reward",
	"summary",
	"draft-player",
	"fixture-round",
	"number-world",
	"addition-adventure",
	"number-pattern-adventure",
	"subtraction-adventure",
	"fraction-adventure",
	"multiplication-adventure",
	"time-adventure",
	"division-adventure",
	"distance-adventure",
	"money-adventure",
	"capacity-adventure",
	"mass-adventure",
	"shape-adventure",
	"direction-adventure",
	"decimal-adventure",
	"roman-adventure",
	"classroom-action-quest",
	"sri-lanka-discovery",
	"plant-explorer",
	"wildlife-ranger",
	"everyday-object-quest",
	"island-food-festival",
	"rainbow-wardrobe-quest",
	"water-works-adventure",
	"transit-terminal-quest",
	"bloom-builder-garden",
	"workplace-link-city",
	"family-word-constellation",
	"earth-sky-explorer",
	"blueprint-quest",
	"information-station",
	"heritage-museum",
	"classroom-language-live",
	"conversation-street",
]);

type SyncState = "synced" | "pending" | "offline" | "conflict";
type AvatarTone = "violet" | "sky" | "teal" | "orange";

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
		Partial<Pick<LearningFlowClient, "cameraConsent" | "setCameraConsent">> {}

const DEV_LEARNER = "00000000-0000-4000-8000-000000000721";
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
	"G5-AREA-SIN-01": "word_workshop",
	"G5-AREA-SIN-02": "word_workshop",
	"G5-AREA-SIN-03": "word_workshop",
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
	"G5-AREA-SIN-16": "word_workshop",
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
const DRAFT_TEMPLATE_LABELS = {
	market_mission: "Market Mission",
	pattern_temple: "Pattern Temple",
	parcel_workshop: "Parcel Workshop",
	word_workshop: "Word Workshop",
	story_studio: "Story Studio",
	eco_explorer: "Eco Explorer",
} as const;
const labels: Record<SyncState, string> = {
	synced: "සමමුහුර්තයි",
	pending: "සමමුහුර්ත වෙමින්",
	offline: "අන්තර්ජාලය නොමැත",
	conflict: "නැවත සම්බන්ධ කිරීම අවශ්‍යයි",
};

export function MobileLearningApp({
	service,
	initialScreen = "splash",
	enableOnboarding = false,
	learnerId = import.meta.env.VITE_MOBILE_LEARNING_LEARNER_ID ?? DEV_LEARNER,
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
	const papersRoute = usePapersRoute();
	const [learnerName, setLearnerName] = useState("කවිඳු");
	const [avatarTone, setAvatarTone] = useState<AvatarTone>("violet");
	const [episode, setEpisode] = useState<ChildEpisodeResponse | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [selected, setSelected] = useState<string | null>(null);
	const [completionProof, setCompletionProof] = useState<{
		manifestRevisionId: string;
		groupedCount: number;
		groupSizes: [number, number];
	} | null>(null);
	const [withdrawing, setWithdrawing] = useState(false);
	const [withdrawalRequest, setWithdrawalRequest] = useState<{
		requestId: string;
		supportRevisionId: string;
	} | null>(null);
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
	const handledWithdrawal = useRef<string | null>(null);
	const apiTail = useRef<Promise<void>>(Promise.resolve());
	const syncConflict = useRef(false);
	const [queueReady, setQueueReady] = useState(false);
	const [syncTick, setSyncTick] = useState(0);
	const [draftMissions, setDraftMissions] = useState<DraftMissionRecord[]>([]);
	const [draftCatalogStatus, setDraftCatalogStatus] = useState<
		"idle" | "loading" | "ready" | "error"
	>("idle");
	const [selectedAreaId, setSelectedAreaId] = useState<string | null>(null);
	const [openSubject, setOpenSubject] = useState<SubjectCode | null>(null);
	const [draftAnswerSent, setDraftAnswerSent] = useState(false);
	const [serverScores, setServerScores] = useState<ServerScore[]>([]);
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
	const [cameraProblem, setCameraProblem] = useState<CameraProblem | null>(null);
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
	const [supportPrompt, setSupportPrompt] = useState<SupportPrompt | null>(null);
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
	const queue = useMemo(
		() =>
			new EncryptedEventQueue(
				!Capacitor.isNativePlatform() &&
					globalThis.crypto?.subtle &&
					globalThis.localStorage &&
					globalThis.indexedDB
					? new WebCryptoLocalStore(
							"mindbridge.mobile-learning.queue.v1",
							new IndexedDbNonExtractableKeyProvider(),
						)
					: new MemoryEncryptedStore(),
			),
		[],
	);

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
		void queue
			.initialize()
			.then(() => {
				setQueueReady(true);
				if (queue.pendingCount)
					setSyncState(navigator.onLine ? "pending" : "offline");
			})
			.catch(() => setSyncState("conflict"));
	}, [queue]);
	useEffect(() => {
		const online = () => {
			syncConflict.current = false;
			setSyncState(
				episode && queue.pendingCountFor(episode.episode_id)
					? "pending"
					: "synced",
			);
			setSyncTick((value) => value + 1);
		};
		const offline = () => setSyncState("offline");
		window.addEventListener("online", online);
		window.addEventListener("offline", offline);
		return () => {
			window.removeEventListener("online", online);
			window.removeEventListener("offline", offline);
		};
	}, [episode, queue]);

	const safeFailure = useCallback((error: unknown) => {
		const code =
			error instanceof LearningFlowApiError || error instanceof Error
				? error.message
				: "BACKEND_UNAVAILABLE";
		setFailure(code);
		setScreen("failure");
		setBusy(false);
	}, []);

	const record = useCallback(
		async (event: SceneDomainEvent, critical = false) => {
			if (!episode) return;
			const payload: Record<string, string | number | boolean> = {
				event_type: event.type,
			};
			if ("groupedCount" in event) payload.grouped_count = event.groupedCount;
			if ("group" in event) payload.group = event.group;
			if ("step" in event) payload.step = event.step;
			await queue.enqueue(episode.episode_id, payload, critical);
			setSyncState(navigator.onLine ? "pending" : "offline");
		},
		[episode, queue],
	);

	const chooseMission = (areaId: string) => {
		setDraftAnswerSent(false);
		setServerScores([]);
		const mission = draftMissions.find((item) => item.area_id === areaId);
		if (areaId === "G5-AREA-ENG-01") {
			setSelectedAreaId(areaId);
			setScreen("classroom-action-quest");
			return;
		}
		if (areaId === "G5-AREA-ENG-02") {
			setSelectedAreaId(areaId);
			setScreen("sri-lanka-discovery");
			return;
		}
		if (areaId === "G5-AREA-ENG-03") {
			setSelectedAreaId(areaId);
			setScreen("plant-explorer");
			return;
		}
		if (areaId === "G5-AREA-ENG-04") {
			setSelectedAreaId(areaId);
			setScreen("wildlife-ranger");
			return;
		}
		if (areaId === "G5-AREA-ENG-05") {
			setSelectedAreaId(areaId);
			setScreen("everyday-object-quest");
			return;
		}
		if (areaId === "G5-AREA-ENG-06") {
			setSelectedAreaId(areaId);
			setScreen("island-food-festival");
			return;
		}
		if (areaId === "G5-AREA-ENG-07") {
			setSelectedAreaId(areaId);
			setScreen("rainbow-wardrobe-quest");
			return;
		}
		if (areaId === "G5-AREA-ENG-08") {
			setSelectedAreaId(areaId);
			setScreen("water-works-adventure");
			return;
		}
		if (areaId === "G5-AREA-ENG-09") {
			setSelectedAreaId(areaId);
			setScreen("transit-terminal-quest");
			return;
		}
		if (areaId === "G5-AREA-ENG-10") {
			setSelectedAreaId(areaId);
			setScreen("bloom-builder-garden");
			return;
		}
		if (areaId === "G5-AREA-ENG-11") {
			setSelectedAreaId(areaId);
			setScreen("workplace-link-city");
			return;
		}
		if (areaId === "G5-AREA-ENG-12") {
			setSelectedAreaId(areaId);
			setScreen("family-word-constellation");
			return;
		}
		if (areaId === "G5-AREA-ENG-13") {
			setSelectedAreaId(areaId);
			setScreen("earth-sky-explorer");
			return;
		}
		if (areaId === "G5-AREA-ENG-14") {
			setSelectedAreaId(areaId);
			setScreen("blueprint-quest");
			return;
		}
		if (areaId === "G5-AREA-ENG-15") {
			setSelectedAreaId(areaId);
			setScreen("information-station");
			return;
		}
		if (areaId === "G5-AREA-ENG-16") {
			setSelectedAreaId(areaId);
			setScreen("heritage-museum");
			return;
		}
		if (areaId === "G5-AREA-ENG-17") {
			setSelectedAreaId(areaId);
			setScreen("classroom-language-live");
			return;
		}
		if (areaId === "G5-AREA-ENG-18") {
			setSelectedAreaId(areaId);
			setScreen("conversation-street");
			return;
		}
		if (!mission) return;
		setSelectedAreaId(areaId);
		if (areaId === "G5-AREA-MAT-01") {
			setScreen("number-world");
			return;
		}
		if (areaId === "G5-AREA-MAT-02") {
			setScreen("addition-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-03") {
			setScreen("number-pattern-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-04") {
			setScreen("subtraction-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-05") {
			setScreen("fraction-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-06") {
			setScreen("multiplication-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-07") {
			setScreen("time-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-08") {
			setScreen("division-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-09") {
			setScreen("distance-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-10") {
			setScreen("money-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-11") {
			setScreen("capacity-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-12") {
			setScreen("mass-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-13") {
			setScreen("shape-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-14") {
			setScreen("direction-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-15") {
			setScreen("decimal-adventure");
			return;
		}
		if (areaId === "G5-AREA-MAT-16") {
			setScreen("roman-adventure");
			return;
		}
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
						environment: "development",
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

	const begin = async () => {
		setBusy(true);
		setServerScores([]);
		try {
			const opened = await runApi(() =>
				api.open(
					{
						learner_id: learnerId,
						session_id: sessionId.current,
						grade: 5,
						medium: "si",
						condition: engineeringCondition,
						environment: "development",
						allow_draft: true,
					},
					crypto.randomUUID(),
				),
			);
			setEpisode(opened);
			setManifest(opened.manifest);
			setScreen("baseline");
			setBusy(false);
		} catch (error) {
			safeFailure(error);
		}
	};

	const rememberScore = (score: ServerScore | null | undefined) => {
		if (!score) return;
		setServerScores((current) => [
			...current.filter(
				(item) => item.measurement_role !== score.measurement_role,
			),
			score,
		]);
	};

	const submitBefore = async () => {
		if (!episode || !selected) return;
		setBusy(true);
		await record({ type: "answer_submitted", groupedCount: 0 }, true);
		try {
			const response = await runApi(() =>
				api.answerBefore(
					episode.episode_id,
					{ option_id: selected },
					crypto.randomUUID(),
				),
			);
			setEpisode(response);
			rememberScore(response.server_score);
			setSelected(null);
			if (response.status === "support_active" && response.support) {
				setSupport(response.support);
				setScreen("difficulty");
			} else setScreen("result");
			setBusy(false);
		} catch (error) {
			safeFailure(error);
		}
	};

	const onGameEvent = useCallback(
		(event: SceneDomainEvent) => {
			if (event.type !== "withdrawal_acknowledged") {
				void record(event, event.type === "answer_submitted").catch(() =>
					setSyncState("conflict"),
				);
			}
			if (event.type === "support_interaction_completed") {
				setCompletionProof(event);
			}
			if (
				event.type === "withdrawal_acknowledged" &&
				episode &&
				support &&
				withdrawalRequest &&
				event.requestId === withdrawalRequest.requestId &&
				event.supportRevisionId === support.revision_id &&
				event.manifestRevisionId === support.game_manifest.revision_id &&
				handledWithdrawal.current !== event.requestId
			) {
				handledWithdrawal.current = event.requestId;
				void (async () => {
					try {
						setBusy(true);
						await record(event, true);
						const response = await runApi(() =>
							api.withdrawSupport(
								episode.episode_id,
								{
									request_id: event.requestId,
									support_revision_id: event.supportRevisionId,
									manifest_revision_id: event.manifestRevisionId,
									all_support_removed: event.allSupportRemoved,
									answer_revealing_state_cleared:
										event.answerRevealingStateCleared,
									input_handlers_cleared: event.inputHandlersCleared,
								},
								crypto.randomUUID(),
							),
						);
						setEpisode(response);
						setSupport(null);
						setWithdrawing(false);
						setScreen("withdrawal");
						setBusy(false);
					} catch (error) {
						safeFailure(error);
					}
				})();
			}
		},
		[api, episode, record, runApi, safeFailure, support, withdrawalRequest],
	);

	const finishSupport = async () => {
		if (!episode || !support || !completionProof) return;
		setBusy(true);
		try {
			const response = await runApi(() =>
				api.completeSupport(
					episode.episode_id,
					{
						duration_ms: 1_200,
						steps_viewed: Math.min(
							support.maximum_steps,
							support.body_si.length,
						),
						manifest_revision_id: completionProof.manifestRevisionId,
						grouped_count: completionProof.groupedCount,
						group_sizes: completionProof.groupSizes,
					},
					crypto.randomUUID(),
				),
			);
			setEpisode(response);
			setWithdrawing(true);
			setWithdrawalRequest({
				requestId: crypto.randomUUID(),
				supportRevisionId: support.revision_id,
			});
			setBusy(false);
		} catch (error) {
			safeFailure(error);
		}
	};

	const presentAfter = async () => {
		if (!episode) return;
		setBusy(true);
		try {
			const response = await runApi(() =>
				api.presentAfter(episode.episode_id, crypto.randomUUID()),
			);
			if (response.status === "invalidated") {
				setFailure("INTERRUPTED_OR_CONTAMINATED");
				setScreen("failure");
			} else {
				setEpisode(response);
				setManifest(response.manifest);
				setScreen("after");
			}
			setBusy(false);
		} catch (error) {
			safeFailure(error);
		}
	};

	const submitAfter = async () => {
		if (!episode || !selected) return;
		setBusy(true);
		await record({ type: "answer_submitted", groupedCount: 0 }, true);
		try {
			const response = await runApi(() =>
				api.answerAfter(
					episode.episode_id,
					{ option_id: selected },
					crypto.randomUUID(),
				),
			);
			setEpisode(response);
			rememberScore(response.server_score);
			setSelected(null);
			setScreen("result");
			setBusy(false);
		} catch (error) {
			safeFailure(error);
		}
	};

	const sync = useCallback(async () => {
		if (busy) return false;
		if (!navigator.onLine) {
			setSyncState("offline");
			return false;
		}
		if (!episode) {
			// No game is open, so there is nothing of this episode to send. This is not a lost
			// connection: show events of earlier episodes as still waiting, otherwise synced.
			setSyncState(queue.pendingCount ? "pending" : "synced");
			return false;
		}
		const batch = queue.takeBatch(episode.episode_id);
		if (!batch) {
			setSyncState("synced");
			return true;
		}
		setSyncState("pending");
		try {
			const ack = await runApi(() =>
				api.telemetry(episode.episode_id, batch, batch.batch_id),
			);
			await queue.acknowledge(episode.episode_id, ack.next_sequence);
			setSyncState(
				queue.pendingCountFor(episode.episode_id) ? "pending" : "synced",
			);
			return true;
		} catch (error) {
			if (
				error instanceof LearningFlowApiError &&
				error.code.includes("SEQUENCE") &&
				error.expectedSequence !== undefined
			) {
				try {
					await queue.reconcileExpectedSequence(
						episode.episode_id,
						error.expectedSequence,
					);
					setSyncState(
						queue.pendingCountFor(episode.episode_id) ? "pending" : "synced",
					);
				} catch {
					syncConflict.current = true;
					setSyncState("conflict");
				}
			} else {
				setSyncState("offline");
			}
			return false;
		}
	}, [api, busy, episode, queue, runApi]);

	useEffect(() => {
		void syncTick;
		if (
			!queueReady ||
			!episode ||
			busy ||
			!navigator.onLine ||
			queue.pendingCountFor(episode.episode_id) === 0 ||
			syncConflict.current
		)
			return;
		let cancelled = false;
		let timer = 0;
		const attempt = async () => {
			if (cancelled || !navigator.onLine || syncConflict.current) return;
			const complete = await sync();
			if (
				!complete &&
				!cancelled &&
				navigator.onLine &&
				!syncConflict.current
			) {
				timer = window.setTimeout(attempt, queue.nextBackoffMs());
			}
		};
		timer = window.setTimeout(attempt, 0);
		return () => {
			cancelled = true;
			window.clearTimeout(timer);
		};
	}, [busy, episode, queue, queueReady, sync, syncTick]);

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

	return (
		<main
			className="mobile-shell"
			lang="si"
			data-screen={screen}
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
						onContinue={() => setScreen(papersRoute ? "practice" : "home")}
					/>
				)}
				{screen === "home" && (
					<HomeScreen
						name={learnerName}
						avatarTone={avatarTone}
						onProfile={() => setScreen("account")}
						onMission={() => setScreen("mission")}
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
						avatarTone={avatarTone}
					/>
				)}
				{screen === "practice" && (
					<div className="papers-tab">
						<PapersApp embedded route={papersRoute ?? { name: "papers" }} />
					</div>
				)}
				{screen === "mindy" && <TutorDemo embedded />}
				{screen === "rewards" && <RewardsHub onBack={() => setScreen("home")} />}
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
				{screen === "mission" && (
					<Mission
						onContinue={() => setScreen("overview")}
						onBack={() => setScreen("learn")}
					/>
				)}
				{screen === "overview" && (
					<Overview
						busy={busy}
						onStart={begin}
						onBack={() => setScreen("learn")}
					/>
				)}
				{screen === "baseline" && manifest && (
					<ChoiceActivity
						title="ඔබම උත්සාහ කරන්න"
						manifest={manifest}
						selected={selected}
						busy={busy}
						onSelect={setSelected}
						onSubmit={submitBefore}
					/>
				)}
				{screen === "difficulty" && (
					<Transition
						title="වෙනත් ක්‍රමයකින් උත්සාහ කරමු"
						body="අපි කුඩා ක්‍රීඩාවකින් සමාන කාණ්ඩ දෙකක් සාදමු."
						onContinue={() => setScreen("support")}
					/>
				)}
				{screen === "support" && support && (
					<SupportPractice
						support={support}
						done={Boolean(completionProof)}
						withdrawing={withdrawing}
						withdrawalRequest={withdrawalRequest}
						busy={busy}
						reducedMotion={reducedMotion}
						onEvent={onGameEvent}
						onFinish={finishSupport}
					/>
				)}
				{screen === "withdrawal" && (
					<Transition
						title="දැන් අලුත් එකක් ඔබම උත්සාහ කරන්න"
						body="උදව් අවසන්. අලුත් ප්‍රශ්නයේදී ඔබට ඉඟි නොපෙන්වයි."
						onContinue={presentAfter}
						busy={busy}
					/>
				)}
				{screen === "after" && manifest && (
					<ChoiceActivity
						title="අලුත් එක ඔබම උත්සාහ කරන්න"
						manifest={manifest}
						selected={selected}
						busy={busy}
						onSelect={setSelected}
						onSubmit={submitAfter}
					/>
				)}
				{screen === "result" && (
					<Result
						hasReward={Boolean(episode?.reward?.points)}
						onContinue={() => setScreen("reward")}
					/>
				)}
				{screen === "reward" && (
					<Reward
						points={episode?.reward?.points ?? 0}
						onContinue={() => setScreen("summary")}
					/>
				)}
				{screen === "summary" && (
					<Summary
						supported={Boolean(support || completionProof)}
						onProgress={() => setScreen("progress")}
						onHome={() => setScreen("home")}
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
				{serverScores.length > 0 &&
					[
						"difficulty",
						"support",
						"withdrawal",
						"after",
						"result",
						"reward",
						"summary",
					].includes(screen) && (
						<ul aria-label="සේවාදායක ලකුණු">
							{serverScores.map((score) => (
								<li
									key={score.measurement_role}
									data-server-score={score.earned_score}
									data-maximum-score={score.maximum_score}
									data-scoring-version={score.scoring_version}
									data-server-authoritative="true"
									data-measurement-role={score.measurement_role}
								>
									සේවාදායක ලකුණු {score.earned_score}/{score.maximum_score}
								</li>
							))}
						</ul>
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
				{screen === "number-world" && (
					<NumberWorldJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onFailure={safeFailure}
						onBack={() => setScreen("learn")}
					/>
				)}
				{screen === "addition-adventure" && (
					<AdditionAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onFailure={safeFailure}
						onBack={() => setScreen("learn")}
					/>
				)}
				{screen === "number-pattern-adventure" && (
					<NumberPatternJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "subtraction-adventure" && (
					<SubtractionAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "fraction-adventure" && (
					<FractionAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "multiplication-adventure" && (
					<MultiplicationAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "time-adventure" && (
					<TimeAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "division-adventure" && (
					<DivisionAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "distance-adventure" && (
					<DistanceAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "money-adventure" && (
					<MoneyAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "capacity-adventure" && (
					<CapacityAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "mass-adventure" && (
					<MassAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "shape-adventure" && (
					<ShapeAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "direction-adventure" && (
					<DirectionAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "decimal-adventure" && (
					<DecimalAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "roman-adventure" && (
					<RomanAdventureJourney
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "classroom-action-quest" && (
					<ClassroomActionQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "sri-lanka-discovery" && (
					<SriLankaDiscovery
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "plant-explorer" && (
					<PlantExplorerQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "wildlife-ranger" && (
					<WildlifeRangerQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "everyday-object-quest" && (
					<EverydayObjectQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "island-food-festival" && (
					<IslandFoodFestival
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "rainbow-wardrobe-quest" && (
					<RainbowWardrobeQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "water-works-adventure" && (
					<WaterWorksAdventure
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "transit-terminal-quest" && (
					<TransitTerminalQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "bloom-builder-garden" && (
					<BloomBuilderGarden
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "workplace-link-city" && (
					<WorkplaceLinkCity
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "family-word-constellation" && (
					<FamilyWordConstellation
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "earth-sky-explorer" && (
					<EarthSkyExplorer
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "blueprint-quest" && (
					<SchoolHomeBlueprintQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "information-station" && (
					<InformationStation
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "heritage-museum" && (
					<HeritageMuseumQuest
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "classroom-language-live" && (
					<ClassroomLanguageLive
						api={api}
						learnerId={learnerId}
						condition={engineeringCondition}
						reducedMotion={reducedMotion}
						onBack={() => setScreen("learn")}
						onFailure={safeFailure}
					/>
				)}
				{screen === "conversation-street" && (
					<ConversationStreet
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
				{["home", "learn", "mission", "practice", "mindy", "progress"].includes(
					screen,
				) && (
					<BottomNavigation
						active={screen === "mission" ? "learn" : screen}
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
			</Suspense>
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

function DraftTemplatePlayer({
	mission,
	busy,
	submitted,
	onSubmit,
	onBack,
}: {
	mission: DraftMissionRecord & {
		template_id: Exclude<DraftTemplateId, "half_set">;
	};
	busy: boolean;
	submitted: boolean;
	onSubmit(): void;
	onBack(): void;
}) {
	const draftItems = [...mission.outcome_slots, ...mission.draft_item_slots];
	return (
		<section
			className="draft-player"
			data-draft-player={mission.template_id}
			data-template-id={mission.template_id}
		>
			<Back onClick={onBack} />
			<p className="eyebrow">{DRAFT_TEMPLATE_LABELS[mission.template_id]}</p>
			<h1>{learningAreaName(mission.area_id)}</h1>
			<p data-template-id={mission.template_id}>{mission.template_id}</p>
			{draftItems.map((slot) => (
				<p className="draft-item" key={slot.node_id}>
					{slot.item_text.split(" Medium-confidence trace.")[0]}
				</p>
			))}
			{mission.held_slots.length > 0 && (
				<p className="held-slots" data-held-count={mission.held_slots.length}>
					රඳවා ඇති සටහන් ප්‍රශ්නයක් නොවේ.
				</p>
			)}
			<button
				className="primary-action"
				disabled={busy || submitted}
				onClick={onSubmit}
			>
				පිළිතුර යවන්න
			</button>
		</section>
	);
}

function Splash({ onContinue }: { onContinue(): void }) {
	return (
		<section className="center-screen splash-screen">
			<div className="splash-orbit splash-orbit--one" />
			<div className="splash-orbit splash-orbit--two" />
			<BrandMark variant="primary" className="brand-mark--hero" />
			<h1>ඉගෙන ගමු. ක්‍රීඩා කරමු. දියුණු වෙමු.</h1>
			<p>ඔබට ගැළපෙන සතුටුදායක ඉගෙනුම් ගමනක්.</p>
			<button className="primary-action" onClick={onContinue}>
				මගේ පැතිකඩට යන්න
			</button>
		</section>
	);
}

const onboardingSlides = [
	{
		icon: "book" as const,
		kicker: "ඔබට ගැළපෙන ඉගෙනීම",
		title: "කුඩා පියවර, ලොකු දියුණුව",
		body: "ඔබගේ වේගයට ගැළපෙන කෙටි පාඩම් සහ සරල පැහැදිලි කිරීම්.",
		tone: "violet",
	},
	{
		icon: "game" as const,
		kicker: "ක්‍රීඩාවෙන් පුහුණුව",
		title: "සෙල්ලම් කරන අතරතුර ඉගෙන ගන්න",
		body: "අභියෝග සම්පූර්ණ කර XP, කාසි සහ නව ලාංඡන දිනා ගන්න.",
		tone: "orange",
	},
	{
		icon: "sparkle" as const,
		kicker: "අවශ්‍ය විට සහාය",
		title: "Mindy හැම පියවරකම ඔබ සමඟයි",
		body: "පිළිතුර නොදී, ඔබටම සොයා ගන්නට උපකාරී වන කුඩා ඉඟි.",
		tone: "teal",
	},
];

function Onboarding({
	onBack,
	onContinue,
}: {
	onBack(): void;
	onContinue(): void;
}) {
	const [index, setIndex] = useState(0);
	const pointerStart = useRef<number | null>(null);
	const slide = onboardingSlides[index];
	const moveSlide = (direction: -1 | 1) => {
		setIndex((current) =>
			Math.max(0, Math.min(onboardingSlides.length - 1, current + direction)),
		);
	};
	return (
		// Swiping is a touch shortcut; the previous/next buttons give keyboard and screen-reader
		// users the same navigation.
		<section
			className="onboarding-screen"
			aria-roledescription="carousel"
			aria-label="MindBridge හඳුන්වාදීම"
			onPointerDown={(event) => {
				pointerStart.current = event.clientX;
			}}
			onPointerUp={(event) => {
				if (pointerStart.current === null) return;
				const distance = event.clientX - pointerStart.current;
				pointerStart.current = null;
				if (Math.abs(distance) > 48) moveSlide(distance > 0 ? -1 : 1);
			}}
			onPointerCancel={() => {
				pointerStart.current = null;
			}}
		>
			<header className="onboarding-brand">
				<button
					type="button"
					className="setup-back"
					aria-label="ආරම්භක පිටුවට ආපසු"
					onClick={onBack}
				>
					<AppIcon name="back" size={19} />
				</button>
				<span className="onboarding-wordmark">
					<BrandMark variant="submark" /> MindBridge
				</span>
				<small>
					{index + 1} / {onboardingSlides.length}
				</small>
			</header>
			<div className={`onboarding-art onboarding-art--${slide.tone}`}>
				<button
					type="button"
					className="slide-arrow slide-arrow--previous"
					aria-label="පෙර විනිවිදකය"
					disabled={index === 0}
					onClick={() => moveSlide(-1)}
				>
					<AppIcon name="back" size={18} />
				</button>
				<div className="onboarding-art__ring" />
				<AppIcon name={slide.icon} size={72} />
				<span className="art-star art-star--one">✦</span>
				<span className="art-star art-star--two">✦</span>
				<button
					type="button"
					className="slide-arrow slide-arrow--next"
					aria-label="ඊළඟ විනිවිදකය"
					disabled={index === onboardingSlides.length - 1}
					onClick={() => moveSlide(1)}
				>
					<AppIcon name="arrow" size={18} />
				</button>
			</div>
			<div className="onboarding-copy" aria-live="polite">
				<p className="eyebrow">{slide.kicker}</p>
				<h1>{slide.title}</h1>
				<p>{slide.body}</p>
			</div>
			<nav
				className="pager"
				aria-label={`${index + 1} / ${onboardingSlides.length}`}
			>
				{onboardingSlides.map((item, itemIndex) => (
					<button
						key={item.title}
						className={
							itemIndex === index ? "pager-dot pager-dot--active" : "pager-dot"
						}
						aria-label={`${itemIndex + 1} වන පිටුව`}
						onClick={() => setIndex(itemIndex)}
					/>
				))}
			</nav>
			<div className="onboarding-actions">
				<button className="text-action" onClick={onContinue}>
					මඟ හරින්න
				</button>
				<button
					className="primary-action"
					onClick={() =>
						index === onboardingSlides.length - 1
							? onContinue()
							: setIndex(index + 1)
					}
				>
					{index === onboardingSlides.length - 1 ? "ආරම්භ කරමු" : "ඊළඟට"}{" "}
					<span aria-hidden="true">→</span>
				</button>
			</div>
		</section>
	);
}

function LanguageSetup({
	onBack,
	onContinue,
}: {
	onBack(): void;
	onContinue(): void;
}) {
	const [selected, setSelected] = useState(true);
	const [previewOpen, setPreviewOpen] = useState(false);
	return (
		<section className="setup-screen language-setup">
			<SetupProgress current={2} onBack={onBack} />
			<div className="setup-icon">
				<AppIcon name="globe" size={34} />
			</div>
			<p className="eyebrow">ඉගෙනුම් භාෂාව</p>
			<h1>සිංහල මාධ්‍ය ඉගෙනීම</h1>
			<p className="quiet">මෙම ඉගෙනුම් ගමන 5 ශ්‍රේණිය සඳහා සිංහලෙන් සකස් කර ඇත.</p>
			<div className="language-list">
				<button
					type="button"
					className={
						selected ? "language-card language-card--selected" : "language-card"
					}
					aria-pressed={selected}
					onClick={() => setSelected((value) => !value)}
				>
					<span className="language-sample">ආයුබෝවන්</span>
					<span>
						<strong>සිංහල</strong>
						<small>Sinhala · 5 ශ්‍රේණිය</small>
					</span>
					<span className="selection-check" aria-hidden="true">
						✓
					</span>
				</button>
			</div>
			<button
				className="language-preview-toggle"
				type="button"
				aria-expanded={previewOpen}
				onClick={() => setPreviewOpen((open) => !open)}
			>
				<span>
					<AppIcon name="book" size={19} /> භාෂා පෙරදසුන
				</span>
				<b aria-hidden="true">{previewOpen ? "−" : "+"}</b>
			</button>
			{previewOpen && (
				<div className="language-preview" aria-live="polite">
					<p>
						<span>ආයුබෝවන්</span>
						<small>සුබ පැතුමක්</small>
					</p>
					<p>
						<span>ගණිතය</span>
						<small>අංක සහ හැඩතල</small>
					</p>
					<p>
						<span>පරිසරය</span>
						<small>අප වටා ලෝකය</small>
					</p>
				</div>
			)}
			<p className="language-help">
				<AppIcon name="shield" size={17} /> පසුව පැතිකඩෙන් භාෂාව නැවත තහවුරු කළ හැක.
			</p>
			<button
				className="primary-action setup-continue"
				disabled={!selected}
				onClick={onContinue}
			>
				ඉදිරියට යමු
			</button>
		</section>
	);
}

function SetupProgress({
	current,
	onBack,
}: {
	current: number;
	onBack(): void;
}) {
	return (
		<header className="setup-progress-row">
			<button
				type="button"
				className="setup-back"
				aria-label="පෙර පිටුවට"
				onClick={onBack}
			>
				<AppIcon name="back" size={19} />
			</button>
			<div
				className="setup-progress-track"
				role="progressbar"
				aria-label="පැතිකඩ සැකසීමේ ප්‍රගතිය"
				aria-valuemin={1}
				aria-valuemax={3}
				aria-valuenow={current}
			>
				<span style={{ width: `${(current / 3) * 100}%` }} />
			</div>
			<small>{current} / 3</small>
		</header>
	);
}

function ProfileSetup({
	name,
	onNameChange,
	avatarTone,
	onAvatarToneChange,
	onBack,
	onContinue,
}: {
	name: string;
	onNameChange(value: string): void;
	avatarTone: AvatarTone;
	onAvatarToneChange(value: AvatarTone): void;
	onBack(): void;
	onContinue(): void;
}) {
	const tones: AvatarTone[] = ["violet", "sky", "teal", "orange"];
	const toneLabels: Record<AvatarTone, string> = {
		violet: "දම්",
		sky: "නිල්",
		teal: "කොළ",
		orange: "තැඹිලි",
	};
	return (
		<section className="setup-screen profile-setup">
			<SetupProgress current={3} onBack={onBack} />
			<p className="eyebrow">අවසන් පියවර</p>
			<h1>ඔබව හඳුනා ගනිමු</h1>
			<p className="quiet">ඔබගේ ඉගෙනුම් ගමන පුද්ගලීකරණය කිරීමට මෙය උපකාරී වේ.</p>
			<div className="avatar-picker">
				<LearnerAvatar tone={avatarTone} />
				<button
					className="avatar-edit"
					aria-label="අවතාරයේ වර්ණය වෙනස් කරන්න"
					onClick={() => {
						const index = tones.indexOf(avatarTone);
						onAvatarToneChange(tones[(index + 1) % tones.length]);
					}}
				>
					✎
				</button>
			</div>
			<fieldset className="setup-avatar-tones">
				<legend>ඔබ කැමති වර්ණය</legend>
				<div>
					{tones.map((tone) => (
						<button
							className={`avatar-tone avatar-tone--${tone}`}
							type="button"
							key={tone}
							aria-label={`${toneLabels[tone]} වර්ණය`}
							aria-pressed={avatarTone === tone}
							onClick={() => onAvatarToneChange(tone)}
						>
							{avatarTone === tone && <span>✓</span>}
						</button>
					))}
				</div>
			</fieldset>
			<label className="field-card">
				<span>
					ඔබේ නම <small>{name.length} / 24</small>
				</span>
				<input
					value={name}
					maxLength={24}
					onChange={(event) => onNameChange(event.target.value)}
					placeholder="උදා: කවිඳු"
				/>
			</label>
			<fieldset className="field-card grade-field">
				<legend>ශ්‍රේණිය</legend>
				<div>
					<span className="grade-pill grade-pill--selected">5 ශ්‍රේණිය</span>
				</div>
			</fieldset>
			<div className="privacy-note">
				<AppIcon name="shield" size={20} />
				<span>ඔබගේ තොරතුරු ආරක්ෂිතව තබා ගනී.</span>
			</div>
			<button
				className="primary-action setup-continue"
				disabled={!name.trim()}
				onClick={onContinue}
			>
				මගේ ගමන අරඹන්න
			</button>
		</section>
	);
}


function HomeScreen({
	name,
	avatarTone,
	onProfile,
	onMission,
	onLearn,
	onPractice,
	onMindy,
	onProgress,
	onRewards,
}: {
	name: string;
	avatarTone: AvatarTone;
	onProfile(): void;
	onMission(): void;
	onLearn(): void;
	onPractice(): void;
	onMindy(): void;
	onProgress(): void;
	onRewards(): void;
}) {
	const [notificationsOpen, setNotificationsOpen] = useState(false);
	const [hasUnread, setHasUnread] = useState(true);
	return (
		<section className="tab-screen home-screen">
			<header className="home-header">
				<button
					className="home-identity"
					type="button"
					aria-label={`${name}ගේ පැතිකඩ බලන්න`}
					onClick={onProfile}
				>
					<LearnerAvatar tone={avatarTone} />
					<span>
						<p>සුබ දවසක්!</p>
						<h1>{name} 👋</h1>
					</span>
				</button>
				<button
					className="notification-button"
					type="button"
					aria-label={hasUnread ? "නව දැනුම්දීම් 1ක්" : "දැනුම්දීම්"}
					aria-expanded={notificationsOpen}
					onClick={() => setNotificationsOpen((open) => !open)}
				>
					<AppIcon name="bell" size={21} />
					{hasUnread && <span aria-hidden="true" />}
				</button>
			</header>

			{notificationsOpen && (
				<aside className="home-notification-panel" aria-label="දැනුම්දීම්">
					<span className="notification-symbol" aria-hidden="true">
						★
					</span>
					<div>
						<strong>අද මෙහෙයුම සූදානම්!</strong>
						<p>මිනිත්තු 5ක බාග අභියෝගයක් ඔබ බලා සිටී.</p>
					</div>
					<button
						type="button"
						aria-label="දැනුම්දීම කියවූ ලෙස සලකුණු කරන්න"
						onClick={() => {
							setHasUnread(false);
							setNotificationsOpen(false);
						}}
					>
						✓
					</button>
				</aside>
			)}

			<ul className="stats" aria-label="අද ප්‍රගතිය">
				<li>
					<span className="stat-icon stat-icon--fire">
						<AppIcon name="fire" size={18} />
					</span>
					<strong>දින 3</strong>
					<small>අඛණ්ඩ මාලාව</small>
				</li>
				<li>
					<span className="stat-icon stat-icon--star">
						<AppIcon name="trophy" size={18} />
					</span>
					<strong>60 XP</strong>
					<small>මුළු ලකුණු</small>
				</li>
				<li>
					<span className="stat-icon stat-icon--coin">●</span>
					<strong>28</strong>
					<small>කාසි</small>
				</li>
			</ul>

			<article className="mission-card home-mission-card">
				<img
					className="home-mission-art"
					src="/curriculum/game/shared/child-celebrating-stars.png"
					alt=""
					aria-hidden="true"
				/>
				<p className="eyebrow">
					<AppIcon name="target" size={16} /> අද මෙහෙයුම
				</p>
				<h2>බාගය සොයමු!</h2>
				<p>වස්තු සමාන කොටස් දෙකකට බෙදා බාගය හඳුනා ගන්න.</p>
				<div className="mission-progress">
					<span
						role="progressbar"
						aria-label="අද මෙහෙයුමේ ප්‍රගතිය"
						aria-valuemin={0}
						aria-valuemax={3}
						aria-valuenow={1}
					>
						<i />
					</span>
					<strong>1 / 3</strong>
				</div>
				<button className="primary-action" type="button" onClick={onMission}>
					දිගටම කරගෙන යමු <AppIcon name="arrow" size={18} />
				</button>
			</article>

			<button
				className="recommendation-card"
				type="button"
				onClick={onPractice}
			>
				<span className="recommendation-icon">
					<AppIcon name="document" size={23} />
				</span>
				<span>
					<small>ඔබට නිර්දේශිතයි</small>
					<strong>පසුගිය ප්‍රශ්න පත්‍ර පුහුණුව</strong>
					<em>කෙටි ප්‍රශ්න 5ක් · මිනිත්තු 8යි</em>
				</span>
				<b aria-hidden="true">›</b>
			</button>

			<button className="smart-support-card" type="button" onClick={onMindy}>
				<span>
					<AppIcon name="sparkle" size={23} />
				</span>
				<span>
					<strong>Mindyගෙන් උදව්වක් ඕනෑ ද?</strong>
					<small>පිළිතුර නොකියා ඔබටම සොයා ගන්නට කුඩා ඉඟියක්</small>
				</span>
				<b aria-hidden="true">›</b>
			</button>

			<div className="section-heading home-section-heading">
				<div>
					<p className="eyebrow">ඉක්මන් පිවිසුම්</p>
					<h2>දැන් මොනවා කරමු ද?</h2>
				</div>
			</div>
			<div className="feature-grid">
				<button type="button" onClick={onLearn}>
					<span className="feature-icon feature-icon--purple">
						<AppIcon name="game" size={24} />
					</span>
					<strong>ක්‍රීඩා කරමින් ඉගෙන ගන්න</strong>
					<small>විෂයක් තෝරා අලුත් අභියෝගයක් අරඹන්න.</small>
				</button>
				<button type="button" onClick={onProgress}>
					<span className="feature-icon feature-icon--sky">
						<AppIcon name="chart" size={24} />
					</span>
					<strong>මගේ ප්‍රගතිය බලන්න</strong>
					<small>ඔබ දියුණු වූ කුසලතා එකම තැනකින් බලන්න.</small>
				</button>
				<button type="button" onClick={onRewards}>
					<span className="feature-icon feature-icon--orange">
						<AppIcon name="trophy" size={24} />
					</span>
					<strong>ත්‍යාග සහ ලාංඡන</strong>
					<small>ඔබ දිනාගත් ලාංඡන සහ මාලාව පරීක්ෂා කරන්න.</small>
				</button>
				<button type="button" onClick={onProfile}>
					<span className="feature-icon feature-icon--teal">
						<AppIcon name="user" size={24} />
					</span>
					<strong>මගේ පැතිකඩ</strong>
					<small>නම, අවතාරය සහ යෙදුම් සැකසුම් වෙනස් කරන්න.</small>
				</button>
			</div>
		</section>
	);
}

type SubjectCode = "MAT" | "SIN" | "ENV" | "ENG";

const GAME_SUBJECTS: Array<{
	code: SubjectCode;
	title: string;
	image: string;
	tone: "math" | "sinhala" | "env" | "english";
}> = [
	{
		code: "MAT",
		title: "ගණිතය",
		image: "/curriculum/math.svg",
		tone: "math",
	},
	{
		code: "SIN",
		title: "සිංහල",
		image: "/curriculum/sinhala.svg",
		tone: "sinhala",
	},
	{
		code: "ENV",
		title: "පරිසර අධ්‍යයනය",
		image: "/curriculum/environmental-studies.svg",
		tone: "env",
	},
	{
		code: "ENG",
		title: "ඉංග්‍රීසි",
		image: "/curriculum/english.svg",
		tone: "english",
	},
];

function missionsForSubject(
	subject: SubjectCode,
	missions: DraftMissionRecord[],
) {
	return missions
		.filter((mission) => mission.area_id.includes(`-${subject}-`))
		.slice()
		.sort((left, right) => left.area_id.localeCompare(right.area_id));
}

function GamesHome({
	missions = [],
	catalogStatus = "idle",
	onChoose,
	openSubject = null,
	onOpenSubject,
	avatarTone = "violet",
}: {
	missions?: DraftMissionRecord[];
	catalogStatus?: "idle" | "loading" | "ready" | "error";
	onChoose?(areaId: string): void;
	openSubject?: SubjectCode | null;
	onOpenSubject?(subject: SubjectCode | null): void;
	avatarTone?: AvatarTone;
}) {
	const subject = GAME_SUBJECTS.find((item) => item.code === openSubject);
	const subjectMissions = subject
		? missionsForSubject(subject.code, missions)
		: [];
	const englishAreas = subject?.code === "ENG" ? ENGLISH_LEARNING_AREAS : [];
	return (
		<section className="tab-screen games-screen">
			{subject ? (
				<section className="learning-areas" data-subject-areas={subject.code}>
					<button
						className="back-button"
						type="button"
						aria-label="ආපසු"
						onClick={() => onOpenSubject?.(null)}
					>
						<AppIcon name="back" size={19} />
					</button>
					<header className="learning-areas__intro">
						<img src={subject.image} alt="" aria-hidden="true" />
						<h1>{subject.title}</h1>
					</header>
					{subjectMissions.length > 0 ? (
						<ul>
							{subjectMissions.map((mission) => (
								<li key={mission.area_id}>
									<button
										className="mission-choice"
										data-area-id={mission.area_id}
										onClick={() => onChoose?.(mission.area_id)}
									>
										{learningAreaName(mission.area_id)}
									</button>
								</li>
							))}
						</ul>
					) : englishAreas.length > 0 ? (
						<ul>
							{englishAreas.map((area) => (
								<li key={area.areaId}>
									<button
										className="mission-choice"
										data-area-id={area.areaId}
										type="button"
										onClick={() => onChoose?.(area.areaId)}
									>
										{area.title}
									</button>
								</li>
							))}
						</ul>
					) : (
						<p className="quiet">මෙම විෂය සඳහා ඉගෙනුම් ක්ෂේත්‍ර තවම නොමැත.</p>
					)}
				</section>
			) : (
				<>
					<img
						src="/curriculum/mobile_adventure_frame.svg"
						alt=""
						aria-hidden="true"
						className="games-frame"
					/>
					<header className="games-hero">
						<div className="games-title">
							<span>ක්‍රීඩා</span>
							<strong>කරමින්</strong>
							<em>ඉගෙන ගමු!</em>
						</div>
						<div className="games-avatar">
							<LearnerAvatar tone={avatarTone} />
						</div>
					</header>
					<div className="subject-cards">
						{GAME_SUBJECTS.map((item) => {
							const count =
								item.code === "ENG"
									? ENGLISH_LEARNING_AREAS.length
									: missionsForSubject(item.code, missions).length;
							return (
								<button
									className={`subject-card subject-card--${item.tone}`}
									data-subject={item.code}
									key={item.code}
									onClick={() => onOpenSubject?.(item.code)}
								>
									<span className="subject-badge">
										<img src={item.image} alt="" aria-hidden="true" />
									</span>
									<span className="subject-copy">
										<strong>{item.title}</strong>
										{count > 0 && <em>{count} ඉගෙනුම් ක්ෂේත්‍ර</em>}
									</span>
									<span className="subject-start" aria-hidden="true">
										<AppIcon name="arrow" size={18} />
									</span>
								</button>
							);
						})}
					</div>
					{catalogStatus === "error" && (
						<p role="status">
							සිංහල සහ පරිසර අධ්‍යයන මෙහෙයුම් ලබා ගත නොහැක. API සේවාව ක්‍රියාත්මක නොවේ.
						</p>
					)}
				</>
			)}
		</section>
	);
}

function Mission({
	onContinue,
	onBack,
}: {
	onContinue(): void;
	onBack(): void;
}) {
	return (
		<section>
			<Back onClick={onBack} />
			<p className="eyebrow">නිර්දේශිත මෙහෙයුම</p>
			<h1>බාගය සොයමු</h1>
			<div className="illustration" role="img" aria-label="සමාන කාණ්ඩ දෙකක ද්‍රව්‍ය">
				● ● ●　│　● ● ●
			</div>
			<button className="primary-action" onClick={onContinue}>
				මෙහෙයුම බලන්න
			</button>
		</section>
	);
}
function Overview({
	busy,
	onStart,
	onBack,
}: {
	busy: boolean;
	onStart(): void;
	onBack(): void;
}) {
	return (
		<section>
			<Back onClick={onBack} />
			<p className="eyebrow">පළමු කුසලතාව</p>
			<h1>ද්‍රව්‍ය සමූහයක බාගය</h1>
			<div className="info-card">
				<p>⏱ විනාඩි 5ක් පමණ</p>
				<p>🧠 මුලින් ප්‍රශ්නයක් ඔබම උත්සාහ කරයි.</p>
				<p>🌱 අවශ්‍ය නම් තාවකාලික උදව් ලැබේ.</p>
			</div>
			<button className="primary-action" disabled={busy} onClick={onStart}>
				ආරම්භ කරන්න
			</button>
		</section>
	);
}

function ChoiceActivity({
	title,
	manifest,
	selected,
	busy,
	onSelect,
	onSubmit,
}: {
	title: string;
	manifest: PresentationManifest;
	selected: string | null;
	busy: boolean;
	onSelect(id: string): void;
	onSubmit(): void;
}) {
	return (
		<section>
			<p className="independent-badge">🔒 ඉඟි නොමැත</p>
			<h1>{title}</h1>
			<p className="question">
				<span className="sr-only">{manifest.accessibility_label_si}</span>
				<span aria-hidden="true">{manifest.prompt_si}</span>
			</p>
			<div className="choice-grid">
				{manifest.options.map((option) => (
					<button
						key={option.option_id}
						className={
							selected === option.option_id
								? "choice choice--selected"
								: "choice"
						}
						aria-pressed={selected === option.option_id}
						onClick={() => onSelect(option.option_id)}
					>
						{option.text_si}
					</button>
				))}
			</div>
			<button
				className="primary-action"
				disabled={!selected || busy}
				onClick={onSubmit}
			>
				පිළිතුර යවන්න
			</button>
		</section>
	);
}
function Transition({
	title,
	body,
	onContinue,
	busy = false,
}: {
	title: string;
	body: string;
	onContinue(): void;
	busy?: boolean;
}) {
	return (
		<section className="center-screen">
			<div className="mascot" aria-hidden="true">
				☀
			</div>
			<h1>{title}</h1>
			<p>{body}</p>
			<button className="primary-action" disabled={busy} onClick={onContinue}>
				ඉදිරියට
			</button>
		</section>
	);
}

function SupportPractice({
	support,
	done,
	withdrawing,
	withdrawalRequest,
	busy,
	reducedMotion,
	onEvent,
	onFinish,
}: {
	support: SupportView;
	done: boolean;
	withdrawing: boolean;
	withdrawalRequest: { requestId: string; supportRevisionId: string } | null;
	busy: boolean;
	reducedMotion: boolean;
	onEvent(event: SceneDomainEvent): void;
	onFinish(): void;
}) {
	const halfSetManifest =
		support.game_manifest.schema_version === "half-set-manifest-v1"
			? support.game_manifest
			: null;
	const gameManifest: HalfSetManifest = useMemo(() => {
		if (!halfSetManifest) throw new Error("HALF_SET_MANIFEST_REQUIRED");
		return {
			schemaVersion: halfSetManifest.schema_version,
			activityId: halfSetManifest.activity_id,
			revisionId: halfSetManifest.revision_id,
			deterministicSeed: halfSetManifest.deterministic_seed,
			totalObjects: halfSetManifest.total_objects,
			groupCount: halfSetManifest.group_count,
			objectLabelSi: halfSetManifest.object_label_si,
			instructionSi: halfSetManifest.instruction_si,
		};
	}, [halfSetManifest]);
	return (
		<section>
			<p className="support-badge">තාවකාලික උදව්</p>
			<h1>{withdrawing ? "උදව් ඉවත් කරමින්" : support.title_si}</h1>
			{!withdrawing && (
				<aside className="support-panel" data-support-visible="true">
					{support.body_si.slice(0, support.maximum_steps).map((line) => (
						<p key={line}>{line}</p>
					))}
				</aside>
			)}
			<HalfSetGame
				manifest={gameManifest}
				support={
					withdrawing
						? null
						: { titleSi: support.title_si, stepsSi: support.body_si }
				}
				withdrawalRequest={withdrawalRequest}
				reducedMotion={reducedMotion}
				onEvent={onEvent}
			/>
			<button
				className="primary-action"
				disabled={!done || busy || withdrawing}
				onClick={onFinish}
			>
				උදව් අවසන් කරන්න
			</button>
		</section>
	);
}

function Result({
	hasReward,
	onContinue,
}: {
	hasReward: boolean;
	onContinue(): void;
}) {
	return (
		<section className="center-screen">
			<div className="success-mark" aria-hidden="true">
				✓
			</div>
			<h1>හොඳ උත්සාහයක්!</h1>
			<p>
				{hasReward ? "ඔබ මෙහෙයුම අවසන් කළා." : "ඔබගේ උත්සාහය සුරැකිණි. ඊළඟ පියවරට යමු."}
			</p>
			<p className="quiet">මෙය එක් ඉගෙනුම් සාක්ෂියක් පමණි.</p>
			<button className="primary-action" onClick={onContinue}>
				ත්‍යාගය බලන්න
			</button>
		</section>
	);
}
function Reward({
	points,
	onContinue,
}: {
	points: number;
	onContinue(): void;
}) {
	return (
		<section className="center-screen">
			<div className="reward-coin" aria-hidden="true">
				★
			</div>
			<h1>සහභාගීත්ව ත්‍යාගය</h1>
			<p className="reward-value">+{points} කාසිය</p>
			<p>මෙය ඔබ මෙහෙයුම සම්පූර්ණ කළ නිසා ලැබුණු ත්‍යාගයකි.</p>
			<button className="primary-action" onClick={onContinue}>
				සාරාංශය
			</button>
		</section>
	);
}
function Summary({
	supported,
	onProgress,
	onHome,
}: {
	supported: boolean;
	onProgress(): void;
	onHome(): void;
}) {
	return (
		<section>
			<p className="eyebrow">අද සාරාංශය</p>
			<h1>ඉගෙනීම ඉදිරියට!</h1>
			<div className="summary-grid">
				<div>
					<strong>1</strong>
					<span>ක්‍රියාකාරකම</span>
				</div>
				<div>
					<strong>~5</strong>
					<span>මිනිත්තු</span>
				</div>
				<div>
					<strong>{supported ? "1" : "0"}</strong>
					<span>උදව් මොහොත</span>
				</div>
			</div>
			<p>ස්වාධීන සාක්ෂිය සේවාදායකය විසින් පරීක්ෂා කර ඇත. එය ත්‍යාගයෙන් වෙන්ව තබා ඇත.</p>
			<button className="primary-action" onClick={onProgress}>
				ප්‍රගතිය බලන්න
			</button>
			<button className="text-action" onClick={onHome}>
				මුල් පිටුව
			</button>
		</section>
	);
}
function Settings({
	syncState,
	onSync,
	reducedMotion,
	setReducedMotion,
	cameraConsent,
	cameraConsentSaving,
	cameraConsentFailed,
	cameraProblem,
	onCameraConsent,
	onBack,
}: {
	syncState: SyncState;
	onSync(): void;
	reducedMotion: boolean;
	setReducedMotion(value: boolean): void;
	cameraConsent: boolean;
	cameraConsentSaving: boolean;
	cameraConsentFailed: boolean;
	cameraProblem: CameraProblem | null;
	onCameraConsent(granted: boolean): void;
	onBack(): void;
}) {
	return (
		<section>
			<Back onClick={onBack} />
			<p className="eyebrow">වැඩිහිටි සැකසුම්</p>
			<h1>යෙදුම් තත්ත්වය</h1>
			<label className="toggle">
				<input
					type="checkbox"
					checked={reducedMotion}
					onChange={(event) => setReducedMotion(event.target.checked)}
				/>{" "}
				චලනය අඩු කරන්න
			</label>
			<CameraConsentCard
				granted={cameraConsent}
				saving={cameraConsentSaving}
				saveFailed={cameraConsentFailed}
				problem={cameraProblem}
				onChange={onCameraConsent}
			/>
			<p role="status">
				සමමුහුර්ත තත්ත්වය: <strong>{labels[syncState]}</strong>
			</p>
			<button className="secondary-action" onClick={onSync}>
				දැන් සමමුහුර්ත කරන්න
			</button>
		</section>
	);
}
function Failure({
	code,
	onSafePractice,
}: {
	code: string;
	onSafePractice(): void;
}) {
	const copy = code.includes("AUTH")
		? "පැතිකඩ තහවුරු කළ නොහැක."
		: code.includes("CONTENT") || code.includes("APPROVAL")
			? "මෙම ඉගෙනුම් අන්තර්ගතය තවම ලබා දිය නොහැක."
			: code.includes("SEQUENCE") || code.includes("CONTAMINATED")
				? "මෙම උත්සාහය ප්‍රගති සාක්ෂියක් ලෙස භාවිතා නොවේ."
				: "දැන් සේවාවට සම්බන්ධ විය නොහැක.";
	return (
		<section className="center-screen" data-failure-code={code}>
			<div className="mascot" aria-hidden="true">
				☁
			</div>
			<h1>මොහොතක් රැඳී සිටිමු</h1>
			<p>{copy}</p>
			<p>ආරක්ෂිත පුහුණුවට ආපසු යා හැක. මෙය නිල ප්‍රගති ප්‍රතිඵලයක් නොවේ.</p>
			<button className="primary-action" onClick={onSafePractice}>
				මුල් පිටුවට
			</button>
		</section>
	);
}
function Back({ onClick }: { onClick(): void }) {
	return (
		<button className="back-button" aria-label="ආපසු" onClick={onClick}>
			<AppIcon name="back" size={19} /> ආපසු
		</button>
	);
}

type ProgressRange = "week" | "month";

const progressSubjects = [
	{
		id: "math",
		title: "ගණිතය",
		note: "ඉතා හොඳින් ඉදිරියට යනවා",
		percent: 72,
		xp: 34,
		tone: "purple",
		symbol: "123",
		skills: [
			{ title: "බාග", percent: 82 },
			{ title: "එකතු කිරීම", percent: 76 },
			{ title: "හැඩතල", percent: 58 },
		],
	},
	{
		id: "sinhala",
		title: "සිංහල",
		note: "අද තවත් කුඩා පියවරක්",
		percent: 61,
		xp: 21,
		tone: "pink",
		symbol: "අ",
		skills: [
			{ title: "කියවීම", percent: 70 },
			{ title: "වචන", percent: 63 },
			{ title: "ව්‍යාකරණ", percent: 48 },
		],
	},
	{
		id: "environment",
		title: "පරිසරය",
		note: "තවත් පුහුණුවෙන් දියුණු වෙමු",
		percent: 48,
		xp: 13,
		tone: "teal",
		symbol: "✿",
		skills: [
			{ title: "අප වටා ලෝකය", percent: 60 },
			{ title: "සත්ව ලෝකය", percent: 46 },
			{ title: "පරිසර ආරක්ෂාව", percent: 38 },
		],
	},
	{
		id: "english",
		title: "ඉංග්‍රීසි",
		note: "අලුත් වචන සමඟ නැවත උත්සාහ කරමු",
		percent: 35,
		xp: 8,
		tone: "orange",
		symbol: "Aa",
		skills: [
			{ title: "Classroom words", percent: 51 },
			{ title: "Listening", percent: 34 },
			{ title: "Simple sentences", percent: 22 },
		],
	},
] as const;

function ProgressScreen({
	onLearn,
	onPractice,
}: {
	onLearn(): void;
	onPractice(): void;
}) {
	const [range, setRange] = useState<ProgressRange>("week");
	const [selectedDay, setSelectedDay] = useState(5);
	const [openSubject, setOpenSubject] = useState<string | null>("math");
	const activity =
		range === "week"
			? [
					{ label: "ස", value: 34, xp: 8 },
					{ label: "අ", value: 58, xp: 14 },
					{ label: "බ", value: 43, xp: 10 },
					{ label: "බ්‍ර", value: 72, xp: 18 },
					{ label: "සි", value: 50, xp: 12 },
					{ label: "සෙ", value: 88, xp: 22 },
					{ label: "ඉ", value: 62, xp: 16 },
				]
			: [
					{ label: "ස 1", value: 46, xp: 42 },
					{ label: "ස 2", value: 68, xp: 61 },
					{ label: "ස 3", value: 55, xp: 49 },
					{ label: "ස 4", value: 82, xp: 76 },
				];
	const overall = range === "week" ? 68 : 74;
	const totalXp = range === "week" ? 60 : 228;
	const activeIndex = Math.min(selectedDay, activity.length - 1);

	return (
		<section className="tab-screen progress-screen">
			<header className="progress-header">
				<div>
					<p className="eyebrow">මගේ ඉගෙනුම් ගමන</p>
					<h1>ප්‍රගතිය</h1>
				</div>
				<div className="progress-streak">
					<AppIcon name="fire" size={18} />
					<strong>3</strong>
					<small>දින</small>
				</div>
			</header>

			<fieldset className="progress-range">
				<legend className="sr-only">ප්‍රගති කාල පරාසය</legend>
				<button
					type="button"
					className={range === "week" ? "is-active" : ""}
					aria-pressed={range === "week"}
					onClick={() => {
						setRange("week");
						setSelectedDay(5);
					}}
				>
					මෙම සතිය
				</button>
				<button
					type="button"
					className={range === "month" ? "is-active" : ""}
					aria-pressed={range === "month"}
					onClick={() => {
						setRange("month");
						setSelectedDay(3);
					}}
				>
					මෙම මාසය
				</button>
			</fieldset>

			<article className="progress-overview-card">
				<div
					className="progress-ring"
					style={{
						background: `conic-gradient(#ffc542 ${overall}%, rgba(255,255,255,.2) 0)`,
					}}
				>
					<div>
						<strong>{overall}%</strong>
						<span>සම්පූර්ණයි</span>
					</div>
				</div>
				<div className="progress-overview-copy">
					<p className="eyebrow">සමස්ත දියුණුව</p>
					<h2>ඔබ හොඳින් ඉදිරියට යනවා!</h2>
					<p>
						මෙම {range === "week" ? "සතියේ" : "මාසයේ"} තවත් කුසලතා 3ක් ශක්තිමත් කර ඇත.
					</p>
				</div>
				<div className="progress-overview-stats">
					<span>
						<strong>{totalXp}</strong>
						<small>XP ලකුණු</small>
					</span>
					<span>
						<strong>9</strong>
						<small>ක්‍රියාකාරකම්</small>
					</span>
					<span>
						<strong>82%</strong>
						<small>හොඳම ලකුණ</small>
					</span>
				</div>
			</article>

			<article className="activity-card">
				<div className="progress-card-heading">
					<div>
						<p className="eyebrow">ක්‍රියාකාරීත්වය</p>
						<h2>{range === "week" ? "මෙම සතිය" : "පසුගිය සති 4"}</h2>
					</div>
					<span>{activity[activeIndex].xp} XP</span>
				</div>
				<figure
					className={`activity-chart activity-chart--${range}`}
					aria-label="ඉගෙනුම් ක්‍රියාකාරීත්ව සටහන"
				>
					{activity.map((day, index) => (
						<button
							type="button"
							key={`${range}-${day.label}`}
							className={index === activeIndex ? "is-active" : ""}
							aria-label={`${day.label}: XP ${day.xp}`}
							aria-pressed={index === activeIndex}
							onClick={() => setSelectedDay(index)}
						>
							<i style={{ height: `${day.value}%` }}>
								<span>{day.xp}</span>
							</i>
							<small>{day.label}</small>
						</button>
					))}
				</figure>
			</article>

			<div className="section-heading progress-section-heading">
				<div>
					<p className="eyebrow">විෂය අනුව</p>
					<h2>කුසලතා දියුණුව</h2>
				</div>
				<small>විවෘත කිරීමට තට්ටු කරන්න</small>
			</div>
			<div className="progress-subjects">
				{progressSubjects.map((subject) => {
					const open = openSubject === subject.id;
					return (
						<article
							className={`progress-subject-card progress-subject-card--${subject.tone}${open ? " is-open" : ""}`}
							key={subject.id}
						>
							<button
								type="button"
								className="progress-subject-summary"
								aria-expanded={open}
								onClick={() => setOpenSubject(open ? null : subject.id)}
							>
								<span className="progress-subject-icon">{subject.symbol}</span>
								<span className="progress-subject-copy">
									<strong>{subject.title}</strong>
									<small>{subject.note}</small>
									<i>
										<b style={{ width: `${subject.percent}%` }} />
									</i>
								</span>
								<span className="progress-subject-score">
									<strong>{subject.percent}%</strong>
									<small>+{subject.xp} XP</small>
									<b aria-hidden="true">⌄</b>
								</span>
							</button>
							{open && (
								<div className="progress-skill-details">
									{subject.skills.map((skill) => (
										<div key={skill.title}>
											<span>
												<strong>{skill.title}</strong>
												<small>{skill.percent}%</small>
											</span>
											<i>
												<b style={{ width: `${skill.percent}%` }} />
											</i>
										</div>
									))}
									<button type="button" onClick={onLearn}>
										මෙම විෂය පුහුණු වන්න <AppIcon name="arrow" size={17} />
									</button>
								</div>
							)}
						</article>
					);
				})}
			</div>

			<button className="progress-insight" type="button" onClick={onPractice}>
				<span>
					<AppIcon name="sparkle" size={24} />
				</span>
				<span>
					<small>Mindyගේ යෝජනාව</small>
					<strong>බාග සහ හැඩතල සඳහා කෙටි පුහුණුවක් කරමු.</strong>
				</span>
				<b aria-hidden="true">›</b>
			</button>
		</section>
	);
}

function RewardsHub({ onBack }: { onBack(): void }) {
	const achievements = [
		{
			icon: "★",
			title: "පළමු පියවර",
			note: "පළමු මෙහෙයුම",
			tone: "violet",
			earned: true,
		},
		{
			icon: "🔥",
			title: "දින 3 මාලාව",
			note: "දින තුනක් අඛණ්ඩව",
			tone: "orange",
			earned: true,
		},
		{
			icon: "½",
			title: "බාග වීරයා",
			note: "බාග 5ක් නිවැරදිව",
			tone: "teal",
			earned: false,
		},
		{
			icon: "◇",
			title: "කුතුහලය",
			note: "පාඩම් 10ක් උත්සාහ කරන්න",
			tone: "sky",
			earned: false,
		},
	];
	return (
		<section className="tab-screen rewards-screen">
			<Back onClick={onBack} />
			<div className="page-title-row">
				<div>
					<p className="eyebrow">මගේ එකතුව</p>
					<h1>ත්‍යාග</h1>
				</div>
				<div className="coin-balance">
					● <strong>28</strong>
				</div>
			</div>
			<article className="level-card">
				<div className="level-medal">
					<span>2</span>
				</div>
				<div>
					<small>දැනට මට්ටම</small>
					<h2>පුංචි ගවේෂකයා</h2>
					<p>මට්ටම 3 දක්වා තවත් XP 40යි</p>
				</div>
				<div
					className="level-progress"
					role="progressbar"
					aria-label="මට්ටමේ ප්‍රගතිය"
					aria-valuemin={0}
					aria-valuemax={100}
					aria-valuenow={60}
				>
					<span style={{ width: "60%" }} />
				</div>
			</article>
			<div className="section-heading">
				<div>
					<p className="eyebrow">ලාංඡන</p>
					<h2>ඔබගේ ජයග්‍රහණ</h2>
				</div>
				<span className="earned-count">2 / 4</span>
			</div>
			<div className="achievement-grid">
				{achievements.map((achievement) => (
					<article
						className={`achievement-card achievement-card--${achievement.tone}${achievement.earned ? "" : " achievement-card--locked"}`}
						key={achievement.title}
					>
						<div className="achievement-icon">
							{achievement.earned ? achievement.icon : "⌁"}
						</div>
						<h3>{achievement.title}</h3>
						<p>{achievement.note}</p>
					</article>
				))}
			</div>
			<article className="streak-card">
				<span className="streak-flame">🔥</span>
				<div>
					<small>මෙම සතියේ මාලාව</small>
					<h2>දින 3ක් අඛණ්ඩව!</h2>
					<div className="week-dots">
						{["ස", "අ", "බ", "බ්‍ර", "සි", "සෙ", "ඉ"].map((day, index) => (
							<span
								className={index < 3 ? "week-dot week-dot--done" : "week-dot"}
								key={day}
							>
								{index < 3 ? "✓" : day}
							</span>
						))}
					</div>
				</div>
			</article>
		</section>
	);
}

function Account({
	name,
	onNameChange,
	avatarTone,
	onAvatarToneChange,
	onBack,
	onRewards,
	onSettings,
	onOnboarding,
}: {
	name: string;
	onNameChange(value: string): void;
	avatarTone: AvatarTone;
	onAvatarToneChange(value: AvatarTone): void;
	onBack(): void;
	onRewards(): void;
	onSettings(): void;
	onOnboarding(): void;
}) {
	const [editing, setEditing] = useState(false);
	const [draftName, setDraftName] = useState(name);
	const [draftTone, setDraftTone] = useState<AvatarTone>(avatarTone);
	const [parentNoteOpen, setParentNoteOpen] = useState(false);
	const avatarChoices: Array<{ tone: AvatarTone; label: string }> = [
		{ tone: "violet", label: "දම්" },
		{ tone: "sky", label: "නිල්" },
		{ tone: "teal", label: "කොළ" },
		{ tone: "orange", label: "තැඹිලි" },
	];
	const openEditor = () => {
		setDraftName(name);
		setDraftTone(avatarTone);
		setEditing(true);
	};
	return (
		<section className="tab-screen account-screen">
			<header className="profile-topbar">
				<button
					className="icon-button"
					type="button"
					aria-label="මුල් පිටුවට ආපසු"
					onClick={onBack}
				>
					<AppIcon name="back" size={20} />
				</button>
				<div>
					<p className="eyebrow">MindBridge</p>
					<h1>මගේ පැතිකඩ</h1>
				</div>
				<button
					className="icon-button"
					type="button"
					aria-label="යෙදුම් සැකසුම්"
					onClick={onSettings}
				>
					<AppIcon name="settings" size={20} />
				</button>
			</header>
			<div className="profile-hero">
				<button
					className="profile-avatar-button"
					type="button"
					aria-label="පැතිකඩ සංස්කරණය කරන්න"
					onClick={openEditor}
				>
					<LearnerAvatar tone={avatarTone} />
					<span aria-hidden="true">✎</span>
				</button>
				<div className="profile-hero-copy">
					<p className="eyebrow">පුංචි ගවේෂකයා</p>
					<h1>{name}</h1>
					<p>5 ශ්‍රේණිය · සිංහල</p>
				</div>
				<button
					className="profile-edit-button"
					type="button"
					onClick={openEditor}
				>
					වෙනස් කරන්න
				</button>
			</div>

			{editing && (
				<section className="profile-edit-panel" aria-labelledby="profile-edit-title">
					<div className="profile-edit-heading">
						<div>
							<p className="eyebrow">පුද්ගලීකරණය</p>
							<h2 id="profile-edit-title">ඔබේ පැතිකඩ වෙනස් කරන්න</h2>
						</div>
						<button
							type="button"
							aria-label="සංස්කරණය වසන්න"
							onClick={() => setEditing(false)}
						>
							×
						</button>
					</div>
					<label className="field-card">
						<span>ඔබේ නම</span>
						<input
							value={draftName}
							maxLength={24}
							onChange={(event) => setDraftName(event.target.value)}
						/>
					</label>
					<fieldset className="avatar-tone-field">
						<legend>අවතාර වර්ණය</legend>
						<div>
							{avatarChoices.map((choice) => (
								<button
									className={`avatar-tone avatar-tone--${choice.tone}`}
									type="button"
									key={choice.tone}
									aria-label={`${choice.label} වර්ණය`}
									aria-pressed={draftTone === choice.tone}
									onClick={() => setDraftTone(choice.tone)}
								>
									{draftTone === choice.tone && <span>✓</span>}
								</button>
							))}
						</div>
					</fieldset>
					<div className="profile-edit-actions">
						<button
							className="text-action"
							type="button"
							onClick={() => setEditing(false)}
						>
							අවලංගු කරන්න
						</button>
						<button
							className="primary-action"
							type="button"
							disabled={!draftName.trim()}
							onClick={() => {
								onNameChange(draftName.trim());
								onAvatarToneChange(draftTone);
								setEditing(false);
							}}
						>
							වෙනස්කම් සුරකින්න
						</button>
					</div>
				</section>
			)}
			<div className="profile-stats">
				<div>
					<strong>2</strong>
					<span>මට්ටම</span>
				</div>
				<div>
					<strong>60</strong>
					<span>මුළු XP</span>
				</div>
				<button
					type="button"
					onClick={onRewards}
					aria-label="ලාංඡන 2ක් — ත්‍යාග බලන්න"
				>
					<strong>2</strong>
					<span>ලාංඡන ›</span>
				</button>
			</div>
			<h2 className="list-title">පැතිකඩ සහ යෙදුම</h2>
			<div className="settings-list">
				<button onClick={onSettings}>
					<span className="settings-icon">
						<AppIcon name="settings" size={21} />
					</span>
					<span>
						<strong>යෙදුම් සැකසුම්</strong>
						<small>ප්‍රවේශතාව සහ සමමුහුර්ත කිරීම</small>
					</span>
					<b>›</b>
				</button>
				<button onClick={onOnboarding}>
					<span className="settings-icon settings-icon--orange">
						<AppIcon name="sparkle" size={21} />
					</span>
					<span>
						<strong>හැඳින්වීම නැවත බලන්න</strong>
						<small>MindBridge භාවිත කරන ආකාරය</small>
					</span>
					<b>›</b>
				</button>
				<button
					type="button"
					onClick={() => setParentNoteOpen((open) => !open)}
					aria-expanded={parentNoteOpen}
				>
					<span className="settings-icon settings-icon--teal">
						<AppIcon name="shield" size={21} />
					</span>
					<span>
						<strong>දෙමාපිය ප්‍රදේශය</strong>
						<small>වැඩිහිටි අවසරය අවශ්‍යයි</small>
					</span>
					<b>›</b>
				</button>
			</div>
			{parentNoteOpen && (
				<div className="parent-note" role="status">
					<AppIcon name="shield" size={21} />
					<p>
						<strong>වැඩිහිටියෙකු සමඟ විවෘත කරන්න.</strong> කැමරා අවසර සහ ප්‍රවේශතා පාලන
						යෙදුම් සැකසුම් තුළ ඇත.
					</p>
					<button className="text-action" type="button" onClick={onSettings}>
						සැකසුම් බලන්න
					</button>
				</div>
			)}
			<div className="profile-brand">
				<BrandMark variant="submark" />
				<span>MindBridge</span>
				<small>Learn · Play · Grow</small>
			</div>
		</section>
	);
}

type TabDestination = "home" | "learn" | "practice" | "mindy" | "progress";
function BottomNavigation({
	active,
	onNavigate,
}: {
	active: string;
	onNavigate(destination: TabDestination): void;
}) {
	const tabs: Array<{ id: TabDestination; label: string; icon: IconName }> = [
		{ id: "home", label: "මුල් පිටුව", icon: "home" },
		{ id: "learn", label: "ක්‍රීඩා", icon: "game" },
		{ id: "practice", label: "පුහුණුව", icon: "document" },
		{ id: "mindy", label: "Mindy", icon: "sparkle" },
		{ id: "progress", label: "ප්‍රගතිය", icon: "chart" },
	];
	return (
		<nav className="bottom-navigation" aria-label="ප්‍රධාන මෙනුව">
			{tabs.map((tab) => {
				const selected = active === tab.id;
				return (
					<button
						key={tab.id}
						className={selected ? "nav-item nav-item--active" : "nav-item"}
						aria-current={selected ? "page" : undefined}
						onClick={() => onNavigate(tab.id)}
					>
						<span>
							<AppIcon name={tab.icon} size={23} />
						</span>
						<small>{tab.label}</small>
					</button>
				);
			})}
		</nav>
	);
}

function BrandMark({
	className = "",
	variant = "submark",
}: {
	className?: string;
	variant?: "primary" | "submark";
}) {
	const src = variant === "primary" ? "/primary_logo.png" : "/logo_submark.png";
	return (
		<img
			className={`brand-mark brand-mark--${variant} ${className}`.trim()}
			src={src}
			alt="MindBridge"
		/>
	);
}

function LearnerAvatar({ tone = "violet" }: { tone?: AvatarTone }) {
	const palette: Record<
		AvatarTone,
		{ background: string; shirt: string; backpack: string }
	> = {
		violet: { background: "#efecfd", shirt: "#6c5ce7", backpack: "#4ebbc4" },
		sky: { background: "#e8f5fe", shirt: "#3fa9f5", backpack: "#6c5ce7" },
		teal: { background: "#e4faf5", shirt: "#16bfa6", backpack: "#ff9f5a" },
		orange: { background: "#fff0e3", shirt: "#ff8b45", backpack: "#6c5ce7" },
	};
	const colors = palette[tone];
	return (
		<svg
			className="learner-avatar"
			viewBox="0 0 100 100"
			role="img"
			aria-label="තෝරාගත් අවතාරය"
		>
			<circle cx="50" cy="50" r="48" fill={colors.background} />
			<path
				d="M24 69q2-15 13-19l13 19-9 20H28q-5-9-4-20Z"
				fill={colors.backpack}
				opacity=".82"
			/>
			<ellipse cx="50" cy="71" rx="27" ry="20" fill={colors.shirt} />
			<circle cx="50" cy="43" r="23" fill="#f2bf91" />
			<path d="M27 38Q50 12 73 38Q72 20 50 19Q28 21 27 38Z" fill="#342a38" />
			<circle cx="42" cy="43" r="2.7" fill="#2e2a45" />
			<circle cx="58" cy="43" r="2.7" fill="#2e2a45" />
			<path
				d="M43 52q7 7 14 0"
				fill="none"
				stroke="#2e2a45"
				strokeLinecap="round"
				strokeWidth="2.4"
			/>
			<circle cx="34" cy="49" r="3" fill="#ff9f5a" opacity=".45" />
			<circle cx="66" cy="49" r="3" fill="#ff9f5a" opacity=".45" />
		</svg>
	);
}

type IconName =
	| "home"
	| "game"
	| "trophy"
	| "chart"
	| "user"
	| "book"
	| "sparkle"
	| "globe"
	| "shield"
	| "play"
	| "target"
	| "settings"
	| "back"
	| "bell"
	| "fire"
	| "arrow"
	| "support"
	| "document";
function AppIcon({ name, size = 24 }: { name: IconName; size?: number }) {
	const paths: Record<IconName, ReactNode> = {
		home: (
			<>
				<path d="m3 10 9-7 9 7" />
				<path d="M5 9v11h14V9M9 20v-6h6v6" />
			</>
		),
		game: (
			<>
				<path d="M8 8h8a5 5 0 0 1 4.7 6.7l-1.1 3.1a2.5 2.5 0 0 1-4.1 1l-1.3-1.2H9.8l-1.3 1.2a2.5 2.5 0 0 1-4.1-1l-1.1-3.1A5 5 0 0 1 8 8Z" />
				<path d="M7 12v4M5 14h4M16.5 12.5h.01M18.5 15h.01" />
			</>
		),
		trophy: (
			<>
				<path d="M8 4h8v5a4 4 0 0 1-8 0V4Z" />
				<path d="M8 6H5v2a3 3 0 0 0 3 3M16 6h3v2a3 3 0 0 1-3 3M12 13v4M8 21h8M9 17h6v4H9z" />
			</>
		),
		chart: (
			<>
				<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
			</>
		),
		user: (
			<>
				<circle cx="12" cy="8" r="4" />
				<path d="M4 21a8 8 0 0 1 16 0" />
			</>
		),
		book: (
			<>
				<path d="M4 5a3 3 0 0 1 3-2h5v17H7a3 3 0 0 0-3 2V5ZM20 5a3 3 0 0 0-3-2h-5v17h5a3 3 0 0 1 3 2V5Z" />
			</>
		),
		sparkle: (
			<>
				<path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z" />
				<path d="m19 14 .8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14Z" />
			</>
		),
		globe: (
			<>
				<circle cx="12" cy="12" r="9" />
				<path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
			</>
		),
		shield: (
			<>
				<path d="M12 3 4.5 6v5.5c0 4.7 3.2 8.1 7.5 9.5 4.3-1.4 7.5-4.8 7.5-9.5V6L12 3Z" />
				<path d="m9 12 2 2 4-5" />
			</>
		),
		play: <path d="m9 7 8 5-8 5V7Z" />,
		target: (
			<>
				<circle cx="12" cy="12" r="9" />
				<circle cx="12" cy="12" r="5" />
				<circle cx="12" cy="12" r="1" />
			</>
		),
		settings: (
			<>
				<circle cx="12" cy="12" r="3" />
				<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
			</>
		),
		back: (
			<>
				<path d="m15 18-6-6 6-6" />
				<path d="M9 12h10" />
			</>
		),
		bell: (
			<>
				<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
				<path d="M10 21h4" />
			</>
		),
		fire: (
			<path d="M12 22c4 0 7-3 7-7 0-3-1.5-5.5-4-8 .2 3-1.3 4-2 4-1-4-3-6-3-6-1 4-5 6-5 11 0 3.4 3 6 7 6Z" />
		),
		arrow: (
			<>
				<path d="M5 12h14M14 7l5 5-5 5" />
			</>
		),
		support: (
			<>
				<path d="M8.5 5.5A4.5 4.5 0 0 0 4 10c0 4.5 8 9 8 9s8-4.5 8-9a4.5 4.5 0 0 0-8-2.8 4.5 4.5 0 0 0-3.5-1.7Z" />
				<path d="m9 12 2 2 4-4" />
			</>
		),
		document: (
			<>
				<path d="M6 2h8l4 4v16H6z" />
				<path d="M14 2v5h5M9 12h6M9 16h6" />
			</>
		),
	};
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 24 24"
			aria-hidden="true"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.9"
			strokeLinecap="round"
			strokeLinejoin="round"
		>
			{paths[name]}
		</svg>
	);
}
