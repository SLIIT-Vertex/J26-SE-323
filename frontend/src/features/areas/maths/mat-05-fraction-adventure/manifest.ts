export type FractionChapter =
	| "equal_share_studio"
	| "quarter_orchard"
	| "tenths_mosaic";

export const FRACTION_ASSET_ROOT = "/curriculum/game/G5-AREA-MAT-05";
export const FRACTION_SKILLS = [
	{
		id: "G5-MAT-FRC-HALF-WHOLE-01",
		chapter: "equal_share_studio",
		name: "සම්පූර්ණයක බාගය",
	},
	{
		id: "G5-MAT-C03-L01-O01",
		chapter: "equal_share_studio",
		name: "සමූහයක බාගය",
	},
	{
		id: "G5-MAT-FRC-QUARTER-WHOLE-01",
		chapter: "quarter_orchard",
		name: "සම්පූර්ණයක කාල",
	},
	{ id: "G5-MAT-C03-L01-O02", chapter: "quarter_orchard", name: "සමූහයක කාල" },
	{
		id: "G5-MAT-FRC-QUARTER-TABLE-01",
		chapter: "quarter_orchard",
		name: "කාල සම්බන්ධතා වගුව",
	},
	{
		id: "G5-MAT-FRC-TENTHS-BUILD-01",
		chapter: "tenths_mosaic",
		name: "දහයෙන් කොටස් සෑදීම",
	},
	{
		id: "G5-MAT-FRC-TENTHS-READ-01",
		chapter: "tenths_mosaic",
		name: "දහයෙන් කොටස් කියවීම",
	},
] as const satisfies ReadonlyArray<{
	id: string;
	chapter: FractionChapter;
	name: string;
}>;

export const FRACTION_GAMES = [
	{
		id: "equal_share_studio",
		title: "සමාන බෙදීමේ මැදිරිය",
		asset: `${FRACTION_ASSET_ROOT}/fraction-adventure-badge.png`,
		difficulty: "පහසු",
		challengeCount: 2,
	},
	{
		id: "quarter_orchard",
		title: "කාල පලතුරු වත්ත",
		asset: `${FRACTION_ASSET_ROOT}/apple-token.png`,
		difficulty: "මධ්‍යම",
		challengeCount: 3,
	},
	{
		id: "tenths_mosaic",
		title: "දහයෙන් මෝසෙයික්",
		asset: `${FRACTION_ASSET_ROOT}/fraction-adventure-badge.png`,
		difficulty: "අභියෝගාත්මක",
		challengeCount: 2,
	},
] as const satisfies ReadonlyArray<{
	id: FractionChapter;
	title: string;
	asset: string;
	difficulty: string;
	challengeCount: number;
}>;
