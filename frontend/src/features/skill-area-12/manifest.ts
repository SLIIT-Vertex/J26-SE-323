export type MassChapter = "weighing_station" | "kilogram_machine" | "market_delivery";

export const MASS_SKILLS = [
	{ id: "G5-MAT-MASS-INSTRUMENT-01", chapter: "weighing_station", name: "නිවැරදි තරාදිය සොයමු" },
	{ id: "G5-MAT-MASS-BALANCE-01", chapter: "weighing_station", name: "තරාදිය සමබර කරමු" },
	{ id: "G5-MAT-MASS-CONVERT-01", chapter: "kilogram_machine", name: "කිලෝග්‍රෑම් හා ග්‍රෑම් මාරු කරමු" },
	{ id: "G5-MAT-MASS-ARITHMETIC-01", chapter: "kilogram_machine", name: "බර ගණනය කරමු" },
	{ id: "G5-MAT-MASS-PROBLEM-01", chapter: "market_delivery", name: "වෙළඳපොළ බර මෙහෙයුම" },
] as const;

export const MASS_GAMES = [
	{ id: "weighing_station", title: "බර මිනුම් මධ්‍යස්ථානය", asset: "/curriculum/game/G5-AREA-MAT-12/market-produce-crate.png", difficulty: "පහසු", challengeLabel: "අභියෝග 2ක්" },
	{ id: "kilogram_machine", title: "කිලෝග්‍රෑම් යන්ත්‍රය", asset: "/curriculum/game/G5-AREA-MAT-12/weighing-parcel.png", difficulty: "මධ්‍යම", challengeLabel: "අභියෝග 2ක්" },
	{ id: "market_delivery", title: "වෙළඳපොළ බෙදාහැරීම", asset: "/curriculum/game/G5-AREA-MAT-12/market-delivery-cart.png", difficulty: "අභියෝගාත්මක", challengeLabel: "අභියෝග 1ක්" },
] as const;
