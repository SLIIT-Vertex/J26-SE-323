export type NumberWorldChapter =
	| "place_value_harbour"
	| "firefly_abacus"
	| "kite_workshop"
	| "river_route_rally";

export const NUMBER_WORLD_SKILLS = [
	{ id: "G5-MAT-NUM-POSITION-01", chapter: "place_value_harbour", name: "ඉලක්කම නිවැරදි තොටුපළට ගෙන යමු" },
	{ id: "G5-MAT-NUM-REPRESENTED-01", chapter: "place_value_harbour", name: "නිරූපිත අගය සහිත බඩු ටැගය" },
	{ id: "G5-MAT-NUM-100000-01", chapter: "place_value_harbour", name: "100 000 තෙක් සංඛ්‍යා ගොඩනඟමු" },
	{ id: "G5-MAT-NUM-ABACUS-01", chapter: "firefly_abacus", name: "කණාමැදිරි ගණක රාමුව" },
	{ id: "G5-MAT-NUM-EXPAND-01", chapter: "firefly_abacus", name: "සංඛ්‍යාව හා විහිදුණු ආකාරය" },
	{ id: "G5-MAT-NUM-EXTREME-01", chapter: "kite_workshop", name: "විශාලතම හෝ කුඩාතම කයිට් කේතය" },
	{ id: "G5-MAT-NUM-LEADING-ZERO-01", chapter: "kite_workshop", name: "මුල් ශූන්‍යය නොමැති කයිට් කේතය" },
	{ id: "G5-MAT-NUM-ORDER-01", chapter: "river_route_rally", name: "ගඟ හරහා සංඛ්‍යා පිළිවෙළ" },
] as const;

export const NUMBER_WORLD_GAMES = [
	{
		id: "place-and-abacus",
		title: "ස්ථාන අගය සොයා ගණක රාමුව හදමු",
		asset: "/curriculum/game/G5-AREA-MAT-01/harbour-crate.png",
		skillIds: [
			"G5-MAT-NUM-POSITION-01",
			"G5-MAT-NUM-REPRESENTED-01",
			"G5-MAT-NUM-ABACUS-01",
		],
		difficulty: "පහසු",
	},
	{
		id: "expand-to-lakh",
		title: "විහිදුණු සංඛ්‍යාවෙන් ලක්ෂය තෙක් යමු",
		asset: "/curriculum/game/G5-AREA-MAT-01/firefly-bead.png",
		skillIds: ["G5-MAT-NUM-EXPAND-01", "G5-MAT-NUM-100000-01"],
		difficulty: "මධ්‍යම",
	},
	{
		id: "value-and-extremes",
		title: "විශාලම හා කුඩාම සංඛ්‍යා හදමු",
		asset: "/curriculum/game/G5-AREA-MAT-01/kite-body.png",
		skillIds: [
			"G5-MAT-NUM-EXTREME-01",
			"G5-MAT-NUM-LEADING-ZERO-01",
			"G5-MAT-NUM-ORDER-01",
		],
		difficulty: "අභියෝගාත්මක",
	},
] as const;

const ROOT = "/curriculum/game/G5-AREA-MAT-01";

export const CHAPTERS: Array<{ id: NumberWorldChapter; title: string; asset: string }> = [
	{ id: "place_value_harbour", title: "ස්ථානීය අගය වරාය", asset: `${ROOT}/harbour-crate.png` },
	{ id: "firefly_abacus", title: "කණාමැදිරි ගණක රාමුව", asset: `${ROOT}/firefly-bead.png` },
	{ id: "kite_workshop", title: "සංඛ්‍යා කයිට් වැඩමුළුව", asset: `${ROOT}/kite-body.png` },
	{ id: "river_route_rally", title: "ගඟ මාර්ග තරගය", asset: `${ROOT}/river-stone.png` },
];

export const NUMBER_WORLD_ASSET_ROOT = ROOT;
