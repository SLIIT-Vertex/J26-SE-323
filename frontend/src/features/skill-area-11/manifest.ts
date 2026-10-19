export type CapacityChapter = "water_laboratory" | "litre_machine" | "water_delivery";

export const CAPACITY_SKILLS = [
	{ id: "G5-MAT-CAPACITY-READ-01", chapter: "water_laboratory", name: "දියර මට්ටම කියවමු" },
	{ id: "G5-MAT-CAPACITY-COMPOSE-01", chapter: "water_laboratory", name: "ලීටර් එකක් සාදමු" },
	{ id: "G5-MAT-CAPACITY-CONVERT-01", chapter: "litre_machine", name: "ලීටර්–මිලිලීටර් මාරු කරමු" },
	{ id: "G5-MAT-CAPACITY-ARITHMETIC-01", chapter: "litre_machine", name: "ධාරිතාව ගණනය කරමු" },
	{ id: "G5-MAT-CAPACITY-PROBLEM-01", chapter: "water_delivery", name: "ජල බෙදාහැරීමේ මෙහෙයුම" },
] as const;

export const CAPACITY_GAMES = [
	{ id: "water_laboratory", title: "ජල පරීක්ෂණාගාරය", asset: "/curriculum/game/G5-AREA-MAT-11/water-drop-companion.png", difficulty: "පහසු", challengeLabel: "අභියෝග 2ක්" },
	{ id: "litre_machine", title: "ලීටර් යන්ත්‍රය", asset: "/curriculum/game/G5-AREA-MAT-11/litre-tank-frame.png", difficulty: "මධ්‍යම", challengeLabel: "අභියෝග 2ක්" },
	{ id: "water_delivery", title: "ජල බෙදාහැරීම", asset: "/curriculum/game/G5-AREA-MAT-11/water-delivery-cart.png", difficulty: "අභියෝගාත්මක", challengeLabel: "අභියෝග 1ක්" },
] as const;
