export type DirectionId =
	| "north"
	| "north_east"
	| "east"
	| "south_east"
	| "south"
	| "south_west"
	| "west"
	| "north_west";

export const DIRECTION_LABELS: Record<DirectionId, string> = {
	north: "උතුර",
	north_east: "ඊසාන",
	east: "නැගෙනහිර",
	south_east: "ගිනිකොණ",
	south: "දකුණ",
	south_west: "නිරිත",
	west: "බස්නාහිර",
	north_west: "වයඹ",
};

export const DIRECTION_SKILLS = [
	{
		id: "G5-MAT-DIRECTION-MAIN-01",
		chapter: "main_direction_compass",
		name: "ප්‍රධාන දිශා තෝරමු",
	},
	{
		id: "G5-MAT-DIRECTION-SECONDARY-01",
		chapter: "secondary_direction_compass",
		name: "අනු දිශා තෝරමු",
	},
	{
		id: "G5-MAT-DIRECTION-SCENE-01",
		chapter: "place_direction_scene",
		name: "ස්ථානය කියමු",
	},
] as const;

export const DIRECTION_GAMES = [
	{
		id: "direction_compass",
		title: "දිශා මාලිමාව",
		difficulty: "පහසු → මධ්‍යම",
		challengeLabel: "අභියෝග 2ක්",
		firstSkillIndex: 0,
	},
	{
		id: "child_places",
		title: "ළමයා වටා ස්ථාන",
		difficulty: "මධ්‍යම–අභියෝගාත්මක",
		challengeLabel: "අභියෝග 1ක්",
		firstSkillIndex: 2,
	},
] as const;

export const PLACE_LABELS: Record<string, string> = {
	dagoba: "චෛත්‍යය",
	mango_tree: "අඹ ගස",
	house: "නිවස",
	school: "පාසල",
	shop: "වෙළඳසැල",
	gate: "ගේට්ටුව",
	coconut_tree: "පොල් ගස",
	post_office: "තැපැල් කාර්යාලය",
};

export const PLACE_ASSETS: Record<string, { src: string; fallback: string }> = {
	dagoba: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-dagoba.png",
		fallback: "🛕",
	},
	mango_tree: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-mango-tree.png",
		fallback: "🥭",
	},
	house: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-house.png",
		fallback: "🏠",
	},
	school: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-school.png",
		fallback: "🏫",
	},
	shop: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-shop.png",
		fallback: "🏪",
	},
	gate: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-gate.png",
		fallback: "🚪",
	},
	coconut_tree: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-coconut-tree.png",
		fallback: "🌴",
	},
	post_office: {
		src: "/curriculum/game/G5-AREA-MAT-14/place-post-office.png",
		fallback: "📮",
	},
};
