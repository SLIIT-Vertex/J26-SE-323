export type MoneyChapter = "money_recognition" | "money_calculation" | "little_shop";

export const MONEY_SKILLS = [
	{ id: "G5-MAT-MONEY-DENOMINATION-01", chapter: "money_recognition", name: "කාසි හා නෝට්ටු හඳුනා ගනිමු" },
	{ id: "G5-MAT-MONEY-COMPOSE-01", chapter: "money_recognition", name: "මුදලක් සාදමු" },
	{ id: "G5-MAT-MONEY-ADD-01", chapter: "money_calculation", name: "මුදල් එකතු කරමු" },
	{ id: "G5-MAT-MONEY-SUBTRACT-01", chapter: "money_calculation", name: "මුදල් අඩු කරමු" },
	{ id: "G5-MAT-MONEY-SHOP-01", chapter: "little_shop", name: "වෙළඳසැලේ ගණනය" },
] as const;

export const MONEY_GAMES = [
	{ id: "money_recognition", title: "මුදල් හඳුනා ගනිමු", asset: "/curriculum/game/G5-AREA-MAT-10/money-purse.png", difficulty: "පහසු", challengeLabel: "අභියෝග 2ක්" },
	{ id: "money_calculation", title: "මුදල් ගණනය කරමු", asset: "/curriculum/game/G5-AREA-MAT-10/shop-basket.png", difficulty: "මධ්‍යම", challengeLabel: "අභියෝග 2ක්" },
	{ id: "little_shop", title: "පුංචි වෙළඳසැල", asset: "/curriculum/game/G5-AREA-MAT-10/shop-counter.png", difficulty: "අභියෝගාත්මක", challengeLabel: "අභියෝග 1ක්" },
] as const;
