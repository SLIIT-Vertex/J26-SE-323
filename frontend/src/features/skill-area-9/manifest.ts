export type DistanceChapter =
	| "unit_path"
	| "distance_calculation"
	| "distance_problems";
export const DISTANCE_SKILLS = [
	{ id: "G5-MAT-LENGTH-RELATION-01", chapter: "unit_path", name: "ඒකක සම්බන්ධය" },
	{ id: "G5-MAT-LENGTH-CONVERT-01", chapter: "unit_path", name: "දුර මාරු කරමු" },
	{
		id: "G5-MAT-LENGTH-ADD-01",
		chapter: "distance_calculation",
		name: "දුර එකතු කරමු",
	},
	{
		id: "G5-MAT-LENGTH-SUBTRACT-01",
		chapter: "distance_calculation",
		name: "දුර අඩු කරමු",
	},
	{
		id: "G5-MAT-LENGTH-PROBLEM-01",
		chapter: "distance_problems",
		name: "දුර කතාව විසඳමු",
	},
] as const;
export const DISTANCE_GAMES = [
	{
		id: "unit_path",
		title: "ඒකක මාරු මාවත",
		asset: "/curriculum/game/G5-AREA-MAT-09/distance-marker.png",
		difficulty: "පහසු",
		challengeCount: 2,
	},
	{
		id: "distance_calculation",
		title: "දුර ගණනය කරමු",
		asset: "/curriculum/game/G5-AREA-MAT-09/distance-journey-bus.png",
		difficulty: "මධ්‍යම",
		challengeCount: 2,
	},
	{
		id: "distance_problems",
		title: "දුර ගැටලු",
		asset: "/curriculum/game/G5-AREA-MAT-09/distance-marker.png",
		difficulty: "අභියෝගාත්මක",
		challengeCount: 1,
	},
] as const;
