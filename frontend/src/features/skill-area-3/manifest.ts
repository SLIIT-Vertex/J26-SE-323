export type NumberPatternChapter =
	| "number_step_trail"
	| "multiplication_bridge"
	| "pattern_power_machine";

export const NUMBER_PATTERN_SKILLS = [
	{
		id: "G5-MAT-PAT-DIFF-ASC-01",
		chapter: "number_step_trail",
		name: "වැඩිවන රටාව",
	},
	{
		id: "G5-MAT-PAT-DIFF-DESC-01",
		chapter: "number_step_trail",
		name: "අඩුවන රටාව",
	},
	{
		id: "G5-MAT-PAT-RATIO-2-01",
		chapter: "multiplication_bridge",
		name: "දෙගුණ රටාව",
	},
	{
		id: "G5-MAT-PAT-RATIO-3-01",
		chapter: "multiplication_bridge",
		name: "තුන්ගුණ රටාව",
	},
	{
		id: "G5-MAT-PAT-RATIO-4-01",
		chapter: "pattern_power_machine",
		name: "හතරගුණ රටාව",
	},
	{
		id: "G5-MAT-PAT-RATIO-5-01",
		chapter: "pattern_power_machine",
		name: "පස්ගුණ රටාව",
	},
] as const;

const ROOT = "/curriculum/game/G5-AREA-MAT-03";

export const NUMBER_PATTERN_CHAPTERS: Array<{
	id: NumberPatternChapter;
	title: string;
	asset: string;
	difficulty: string;
}> = [
	{
		id: "number_step_trail",
		title: "සංඛ්‍යා පියවර මාවත",
		asset: `${ROOT}/number-patterns-badge.png`,
		difficulty: "පහසු",
	},
	{
		id: "multiplication_bridge",
		title: "ගුණ කිරීමේ පාලම",
		asset: `${ROOT}/pattern-step-stone.png`,
		difficulty: "මධ්‍යම",
	},
	{
		id: "pattern_power_machine",
		title: "රටා බල යන්ත්‍රය",
		asset: `${ROOT}/pattern-rule-machine.png`,
		difficulty: "අභියෝගාත්මක",
	},
];

export const NUMBER_PATTERN_ASSET_ROOT = ROOT;
