export type TimeChapter = "time_tools" | "twenty_four_hour_mission" | "time_journey";

export const TIME_ASSET_ROOT = "/curriculum/game/G5-AREA-MAT-07";
export const TIME_SKILLS = [
	{ id: "G5-MAT-TIME-UNITS-01", chapter: "time_tools", name: "කාල ඒකක යුගල" },
	{ id: "G5-MAT-TIME-ANALOG-01", chapter: "time_tools", name: "ඔරලෝසු අත් සකසමු" },
	{ id: "G5-MAT-TIME-24H-01", chapter: "twenty_four_hour_mission", name: "පැය 24 ඔරලෝසුව" },
	{ id: "G5-MAT-TIME-ELAPSED-01", chapter: "time_journey", name: "ගමනේ ගත වූ කාලය" },
	{ id: "G5-MAT-TIME-ARITHMETIC-01", chapter: "time_journey", name: "කාල අභියෝගය" },
] as const satisfies ReadonlyArray<{ id: string; chapter: TimeChapter; name: string }>;

export const TIME_GAMES = [
	{ id: "time_tools", title: "කාල මෙවලම්", asset: `${TIME_ASSET_ROOT}/timekeeper-companion.png`, difficulty: "පහසු", challengeCount: 2 },
	{ id: "twenty_four_hour_mission", title: "පැය 24 මෙහෙයුම", asset: `${TIME_ASSET_ROOT}/timekeeper-companion.png`, difficulty: "මධ්‍යම", challengeCount: 1 },
	{ id: "time_journey", title: "කාල ගමන් මාර්ගය", asset: `${TIME_ASSET_ROOT}/time-journey-bus.png`, difficulty: "අභියෝගාත්මක", challengeCount: 2 },
] as const satisfies ReadonlyArray<{ id: TimeChapter; title: string; asset: string; difficulty: string; challengeCount: number }>;
