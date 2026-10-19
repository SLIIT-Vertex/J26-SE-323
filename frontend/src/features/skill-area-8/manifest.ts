export type DivisionChapter =
	| "equal_share"
	| "paper_division"
	| "division_story";

export const DIVISION_SKILLS = [
	{ id: "G5-MAT-DIV-SHARE-01", chapter: "equal_share", name: "දෙකට බෙදමු" },
	{ id: "G5-MAT-DIV-PLAN-01", chapter: "equal_share", name: "බෙදීමේ සැලැස්ම" },
	{
		id: "G5-MAT-DIV-WRITTEN-01",
		chapter: "paper_division",
		name: "දිගු බෙදීම පුරවමු",
	},
	{
		id: "G5-MAT-DIV-REMAINDER-01",
		chapter: "paper_division",
		name: "ඉතිරිය සොයමු",
	},
	{
		id: "G5-MAT-DIV-STORY-01",
		chapter: "division_story",
		name: "බෙදීමේ කතාව විසඳමු",
	},
] as const satisfies ReadonlyArray<{
	id: string;
	chapter: DivisionChapter;
	name: string;
}>;

export const DIVISION_GAMES = [
	{
		id: "equal_share",
		title: "බෙදා සමාන කරමු",
		asset: "/curriculum/game/G5-AREA-MAT-08/sharing-basket.png",
		difficulty: "පහසු",
		challengeCount: 2,
	},
	{
		id: "paper_division",
		title: "බෙදීම පියවරෙන් පියවර",
		asset: "/curriculum/game/G5-AREA-MAT-08/story-book-bundle.png",
		difficulty: "මධ්‍යම",
		challengeCount: 2,
	},
	{
		id: "division_story",
		title: "බෙදීමේ ගැටලු",
		asset: "/curriculum/game/G5-AREA-MAT-08/story-ball.png",
		difficulty: "අභියෝගාත්මක",
		challengeCount: 1,
	},
] as const satisfies ReadonlyArray<{
	id: DivisionChapter;
	title: string;
	asset: string;
	difficulty: string;
	challengeCount: number;
}>;
