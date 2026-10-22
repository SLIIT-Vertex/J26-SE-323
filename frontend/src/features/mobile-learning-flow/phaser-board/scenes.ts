import type { BoardSceneArt } from "./boardScene";

/**
 * One illustrated banner per English area, built only from artwork the app already ships:
 * playfields and backdrops, the friendly guide characters, and emoji props for the theme.
 */
const ART = "/curriculum/game";
const BACKDROP = `${ART}/shared/game-backdrop-vertical.png`;
const CLASSROOM = `${ART}/G5-AREA-ENG-01/classroom-playfield.png`;
const GARDEN = `${ART}/G5-AREA-ENG-03/plant-garden-playfield.png`;
const WILD = `${ART}/G5-AREA-ENG-04/wildlife-ranger-playfield.png`;
const CHILD = `${ART}/shared/child-celebrating-stars.png`;
const STUDENT = `${ART}/G5-AREA-ENG-01/student-standing-neutral.png`;
const STUDENT_WAVE = `${ART}/G5-AREA-ENG-01/student-arms-stretched.png`;
const STUDENT_RUN = `${ART}/G5-AREA-ENG-01/student-running.png`;
const BIRD = `${ART}/G5-AREA-ENG-01/action-quest-companion.png`;
const LEAF = `${ART}/G5-AREA-ENG-03/plant-explorer-companion.png`;
const DROP = `${ART}/G5-AREA-MAT-11/water-drop-companion.png`;
const TIMEKEEPER = `${ART}/G5-AREA-MAT-07/timekeeper-companion.png`;
const DIRECTION_CHILD = `${ART}/G5-AREA-MAT-14/direction-child.png`;

export const ENGLISH_SCENES: Record<string, BoardSceneArt> = {
	"G5-AREA-ENG-02": {
		backdrop: BACKDROP,
		guide: STUDENT_WAVE,
		props: ["🇱🇰", "🪔", "🐘"],
	},
	"G5-AREA-ENG-03": { backdrop: GARDEN, guide: LEAF, props: ["🌼", "🦋"] },
	"G5-AREA-ENG-04": { backdrop: WILD, guide: BIRD, props: ["🐾", "🦚"] },
	"G5-AREA-ENG-05": {
		backdrop: CLASSROOM,
		guide: STUDENT,
		props: ["✏️", "📏", "🎒"],
	},
	"G5-AREA-ENG-06": {
		backdrop: BACKDROP,
		guide: CHILD,
		props: ["🥭", "🍌", "🥥"],
	},
	"G5-AREA-ENG-07": {
		backdrop: BACKDROP,
		guide: STUDENT_WAVE,
		props: ["👕", "👟", "🧦"],
	},
	"G5-AREA-ENG-08": {
		backdrop: GARDEN,
		guide: DROP,
		props: ["💧", "🚿", "🌱"],
	},
	"G5-AREA-ENG-09": {
		backdrop: BACKDROP,
		guide: STUDENT_RUN,
		props: ["🚌", "🚲", "✈️"],
	},
	"G5-AREA-ENG-10": {
		backdrop: GARDEN,
		guide: LEAF,
		props: ["🌻", "🌹", "🐝"],
	},
	"G5-AREA-ENG-11": {
		backdrop: BACKDROP,
		guide: STUDENT,
		props: ["🧑‍🌾", "🧑‍🏫", "🛠️"],
	},
	"G5-AREA-ENG-12": {
		backdrop: BACKDROP,
		guide: CHILD,
		props: ["⭐", "🏠", "💖"],
	},
	"G5-AREA-ENG-13": {
		backdrop: WILD,
		guide: DIRECTION_CHILD,
		props: ["☀️", "🌈", "☁️"],
	},
	"G5-AREA-ENG-14": {
		backdrop: CLASSROOM,
		guide: STUDENT_WAVE,
		props: ["🏫", "🏠", "📐"],
	},
	"G5-AREA-ENG-15": {
		backdrop: BACKDROP,
		guide: BIRD,
		props: ["📰", "☎️", "✉️"],
	},
	"G5-AREA-ENG-16": {
		backdrop: BACKDROP,
		guide: TIMEKEEPER,
		props: ["👑", "🏯", "🗿"],
	},
	"G5-AREA-ENG-17": {
		backdrop: CLASSROOM,
		guide: BIRD,
		props: ["🙋", "👏", "💬"],
	},
};

export function sceneFor(areaId: string): BoardSceneArt | undefined {
	return ENGLISH_SCENES[areaId];
}
