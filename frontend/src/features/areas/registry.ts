/**
 * The single registry of playable Grade 5 area games.
 *
 * One row per area: the curriculum area id, the app screen that shows it, and the lazily loaded
 * game component. The folder of each game is `features/areas/<subject>/<code>-<slug>/`, where
 * `<slug>` matches the backend flow (`backend/app/gamification/application/<slug>_flow.py`).
 * See `features/areas/README.md` for the full id → backend → data → frontend table.
 */

import { type ComponentType, type LazyExoticComponent, lazy } from "react";
import type { ExperimentCondition } from "../mobile-learning-flow/api/generated";
import type { MobileLearningService } from "../mobile-learning-flow/MobileLearningApp";

/** Every area game receives exactly these props from the app shell. */
export type AreaGameProps = {
	api: MobileLearningService;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack: () => void;
	onFailure: (error: unknown) => void;
};

type GameExport<Module> = {
	[Name in keyof Module]: Module[Name] extends ComponentType<AreaGameProps> ? Name : never;
}[keyof Module];

export type AreaGame<Screen extends string = string> = {
	areaId: string;
	screen: Screen;
	Component: LazyExoticComponent<ComponentType<AreaGameProps>>;
};

function areaGame<Screen extends string, Module>(
	areaId: string,
	screen: Screen,
	loader: () => Promise<Module>,
	exportName: GameExport<Module>,
): AreaGame<Screen> {
	return {
		areaId,
		screen,
		Component: lazy(async () => ({
			default: (await loader())[exportName] as ComponentType<AreaGameProps>,
		})),
	};
}

export const AREA_GAMES = [
	// Mathematics
	areaGame("G5-AREA-MAT-01", "number-world", () => import("./maths/mat-01-number-world/NumberWorldJourney"), "NumberWorldJourney"),
	areaGame("G5-AREA-MAT-02", "addition-adventure", () => import("./maths/mat-02-addition-adventure/AdditionAdventureJourney"), "AdditionAdventureJourney"),
	areaGame("G5-AREA-MAT-03", "number-pattern-adventure", () => import("./maths/mat-03-number-patterns/NumberPatternJourney"), "NumberPatternJourney"),
	areaGame("G5-AREA-MAT-04", "subtraction-adventure", () => import("./maths/mat-04-subtraction-adventure/SubtractionAdventureJourney"), "SubtractionAdventureJourney"),
	areaGame("G5-AREA-MAT-05", "fraction-adventure", () => import("./maths/mat-05-fraction-adventure/FractionAdventureJourney"), "FractionAdventureJourney"),
	areaGame("G5-AREA-MAT-06", "multiplication-adventure", () => import("./maths/mat-06-multiplication-adventure/MultiplicationAdventureJourney"), "MultiplicationAdventureJourney"),
	areaGame("G5-AREA-MAT-07", "time-adventure", () => import("./maths/mat-07-time-adventure/TimeAdventureJourney"), "TimeAdventureJourney"),
	areaGame("G5-AREA-MAT-08", "division-adventure", () => import("./maths/mat-08-division-adventure/DivisionAdventureJourney"), "DivisionAdventureJourney"),
	areaGame("G5-AREA-MAT-09", "distance-adventure", () => import("./maths/mat-09-distance-adventure/DistanceAdventureJourney"), "DistanceAdventureJourney"),
	areaGame("G5-AREA-MAT-10", "money-adventure", () => import("./maths/mat-10-money-adventure/MoneyAdventureJourney"), "MoneyAdventureJourney"),
	areaGame("G5-AREA-MAT-11", "capacity-adventure", () => import("./maths/mat-11-capacity-adventure/CapacityAdventureJourney"), "CapacityAdventureJourney"),
	areaGame("G5-AREA-MAT-12", "mass-adventure", () => import("./maths/mat-12-mass-adventure/MassAdventureJourney"), "MassAdventureJourney"),
	areaGame("G5-AREA-MAT-13", "shape-adventure", () => import("./maths/mat-13-shape-adventure/ShapeAdventureJourney"), "ShapeAdventureJourney"),
	areaGame("G5-AREA-MAT-14", "direction-adventure", () => import("./maths/mat-14-direction-adventure/DirectionAdventureJourney"), "DirectionAdventureJourney"),
	areaGame("G5-AREA-MAT-15", "decimal-adventure", () => import("./maths/mat-15-decimal-adventure/DecimalAdventureJourney"), "DecimalAdventureJourney"),
	areaGame("G5-AREA-MAT-16", "roman-adventure", () => import("./maths/mat-16-roman-adventure/RomanAdventureJourney"), "RomanAdventureJourney"),
	// English
	areaGame("G5-AREA-ENG-01", "classroom-action-quest", () => import("./english/eng-01-classroom-action-quest/ClassroomActionQuest"), "ClassroomActionQuest"),
	areaGame("G5-AREA-ENG-02", "sri-lanka-discovery", () => import("./english/eng-02-sri-lanka-discovery/SriLankaDiscovery"), "SriLankaDiscovery"),
	areaGame("G5-AREA-ENG-03", "plant-explorer", () => import("./english/eng-03-plant-explorer/PlantExplorerQuest"), "PlantExplorerQuest"),
	areaGame("G5-AREA-ENG-04", "wildlife-ranger", () => import("./english/eng-04-wildlife-ranger/WildlifeRangerQuest"), "WildlifeRangerQuest"),
	areaGame("G5-AREA-ENG-05", "everyday-object-quest", () => import("./english/eng-05-everyday-object-quest/EverydayObjectQuest"), "EverydayObjectQuest"),
	areaGame("G5-AREA-ENG-06", "island-food-festival", () => import("./english/eng-06-island-food-festival/IslandFoodFestival"), "IslandFoodFestival"),
	areaGame("G5-AREA-ENG-07", "rainbow-wardrobe-quest", () => import("./english/eng-07-rainbow-wardrobe-quest/RainbowWardrobeQuest"), "RainbowWardrobeQuest"),
	areaGame("G5-AREA-ENG-08", "water-works-adventure", () => import("./english/eng-08-water-works-adventure/WaterWorksAdventure"), "WaterWorksAdventure"),
	areaGame("G5-AREA-ENG-09", "transit-terminal-quest", () => import("./english/eng-09-transit-terminal-quest/TransitTerminalQuest"), "TransitTerminalQuest"),
	areaGame("G5-AREA-ENG-10", "bloom-builder-garden", () => import("./english/eng-10-bloom-builder-garden/BloomBuilderGarden"), "BloomBuilderGarden"),
	areaGame("G5-AREA-ENG-11", "workplace-link-city", () => import("./english/eng-11-workplace-link-city/WorkplaceLinkCity"), "WorkplaceLinkCity"),
	areaGame("G5-AREA-ENG-12", "family-word-constellation", () => import("./english/eng-12-family-word-constellation/FamilyWordConstellation"), "FamilyWordConstellation"),
	areaGame("G5-AREA-ENG-13", "earth-sky-explorer", () => import("./english/eng-13-earth-sky-explorer/EarthSkyExplorer"), "EarthSkyExplorer"),
	areaGame("G5-AREA-ENG-14", "blueprint-quest", () => import("./english/eng-14-blueprint-quest/SchoolHomeBlueprintQuest"), "SchoolHomeBlueprintQuest"),
	areaGame("G5-AREA-ENG-15", "information-station", () => import("./english/eng-15-information-station/InformationStation"), "InformationStation"),
	areaGame("G5-AREA-ENG-16", "heritage-museum", () => import("./english/eng-16-heritage-museum-quest/HeritageMuseumQuest"), "HeritageMuseumQuest"),
	areaGame("G5-AREA-ENG-17", "classroom-language-live", () => import("./english/eng-17-classroom-language-live/ClassroomLanguageLive"), "ClassroomLanguageLive"),
	areaGame("G5-AREA-ENG-18", "conversation-street", () => import("./english/eng-18-conversation-street/ConversationStreet"), "ConversationStreet"),
	// Sinhala
	areaGame("G5-AREA-SIN-01", "pillam-journey", () => import("./sinhala/sin-01-pillam/PillamJourney"), "PillamJourney"),
	areaGame("G5-AREA-SIN-02", "punctuation-journey", () => import("./sinhala/sin-02-punctuation/PunctuationJourney"), "PunctuationJourney"),
	areaGame("G5-AREA-SIN-03", "riddle-journey", () => import("./sinhala/sin-03-riddles/RiddleJourney"), "RiddleJourney"),
] as const;

export type AreaGameScreen = (typeof AREA_GAMES)[number]["screen"];

const BY_AREA = new Map<string, AreaGame<AreaGameScreen>>(AREA_GAMES.map((game) => [game.areaId, game]));
const BY_SCREEN = new Map<string, AreaGame<AreaGameScreen>>(AREA_GAMES.map((game) => [game.screen, game]));

export function areaGameForArea(areaId: string): AreaGame<AreaGameScreen> | undefined {
	return BY_AREA.get(areaId);
}

export function areaGameForScreen(screen: string): AreaGame<AreaGameScreen> | undefined {
	return BY_SCREEN.get(screen);
}
