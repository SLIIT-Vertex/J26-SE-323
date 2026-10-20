export type SubtractionChapter =
	| "place_value_board"
	| "regrouping_workshop"
	| "difference_story";

export const SUBTRACTION_SKILLS = [
	{
		id: "G5-MAT-SUB-NO-REGROUP-01",
		chapter: "place_value_board",
		name: "ගෙන ඒමක් නැති අඩු කිරීම",
	},
	{
		id: "G5-MAT-SUB-EXPANDED-01",
		chapter: "place_value_board",
		name: "විහිදුණු ආකාරයෙන් අඩු කිරීම",
	},
	{
		id: "G5-MAT-C07-L01-O01",
		chapter: "regrouping_workshop",
		name: "ගෙන ඒම් එකක්",
	},
	{
		id: "G5-MAT-C07-L01-O02",
		chapter: "regrouping_workshop",
		name: "ගෙන ඒම් දෙකක්",
	},
	{
		id: "G5-MAT-SUB-DIFF-BETWEEN-01",
		chapter: "difference_story",
		name: "කාණ්ඩ දෙකක වෙනස",
	},
	{
		id: "G5-MAT-SUB-HOW-MANY-MORE-01",
		chapter: "difference_story",
		name: "කොපමණ වැඩියිද",
	},
] as const;

export const SUBTRACTION_CHAPTERS: Array<{
	id: SubtractionChapter;
	title: string;
	asset: string;
	difficulty: string;
}> = [
	{
		id: "place_value_board",
		title: "ස්ථාන අගය වෙනස පුවරුව",
		asset: "/curriculum/game/G5-AREA-MAT-01/harbour-crate.png",
		difficulty: "පහසු",
	},
	{
		id: "regrouping_workshop",
		title: "ගෙන ඒමේ හුවමාරු වැඩමුළුව",
		asset: "/curriculum/game/G5-AREA-MAT-02/carrying-crane.png",
		difficulty: "මධ්‍යම",
	},
	{
		id: "difference_story",
		title: "වෙනස සොයන මෙහෙයුම",
		asset: "/curriculum/game/G5-AREA-MAT-01/route-boat.png",
		difficulty: "අභියෝගාත්මක",
	},
];

export const PLACE_NAMES: Record<string, string> = {
	thousands: "දහස්",
	hundreds: "සිය",
	tens: "දහය",
	ones: "එක",
};

export function exchangeLabel(fromPlace: string, toPlace: string) {
	return `${PLACE_NAMES[fromPlace] ?? fromPlace} තැනින් එකක් ගෙන ${PLACE_NAMES[toPlace] ?? toPlace} තැනට දහයක් එක් කරන්න`;
}

export function resultDigitLabel(place: string) {
	if (place === "ones") return "එක තැනේ පිළිතුරු ඉලක්කම ඇතුළත් කරන්න";
	return `${PLACE_NAMES[place] ?? place} තැනේ පිළිතුරු ඉලක්කම ඇතුළත් කරන්න`;
}
