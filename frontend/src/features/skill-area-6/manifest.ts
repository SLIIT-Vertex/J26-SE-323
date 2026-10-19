export type MultiplicationChapter =
	| "table_explorer"
	| "column_workshop"
	| "story_mission";

export const MULTIPLICATION_SKILLS = [
	{ id: "G5-MAT-MUL-TABLE-01", chapter: "table_explorer", name: "ගුණන වගු ගවේෂණය" },
	{ id: "G5-MAT-MUL-BY-2-3-01", chapter: "column_workshop", name: "×2 සහ ×3" },
	{ id: "G5-MAT-MUL-BY-4-6-01", chapter: "column_workshop", name: "×4 සිට ×6" },
	{ id: "G5-MAT-MUL-BY-7-10-01", chapter: "column_workshop", name: "×7 සිට ×10" },
	{ id: "G5-MAT-MUL-STORY-01", chapter: "story_mission", name: "ගුණන කතා මෙහෙයුම" },
] as const;

export const MULTIPLICATION_CHAPTERS: Array<{
	id: MultiplicationChapter;
	title: string;
	asset: string;
	difficulty: string;
}> = [
	{
		id: "table_explorer",
		title: "ගුණන වගු ගවේෂණය",
		asset: "/curriculum/game/G5-AREA-MAT-02/addition-skill-badge.png",
		difficulty: "පහසු",
	},
	{
		id: "column_workshop",
		title: "තීරු ගුණන වැඩමුළුව",
		asset: "/curriculum/game/G5-AREA-MAT-02/carrying-crane.png",
		difficulty: "මධ්‍යම",
	},
	{
		id: "story_mission",
		title: "ගුණන කතා මෙහෙයුම",
		asset: "/curriculum/game/G5-AREA-MAT-02/cargo-parcel.png",
		difficulty: "අභියෝගාත්මක",
	},
];
