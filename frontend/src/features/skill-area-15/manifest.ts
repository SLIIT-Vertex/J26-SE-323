export const DECIMAL_ASSET_ROOT = "/curriculum/game/G5-AREA-MAT-15";

export const DECIMAL_SKILLS = [
	{
		id: "G5-MAT-DECIMAL-READ-01",
		chapter: "decimal_reading_match",
		name: "නිවැරදි කියවීම ගළපමු",
	},
	{
		id: "G5-MAT-DECIMAL-SHADE-01",
		chapter: "decimal_tenths_shading",
		name: "දශමය රූපයෙන් පෙන්වමු",
	},
	{
		id: "G5-MAT-TENTHS-TO-DECIMAL-01",
		chapter: "tenths_fraction_to_decimal",
		name: "භාගයෙන් දශමයට",
	},
	{
		id: "G5-MAT-DECIMAL-TO-TENTHS-01",
		chapter: "decimal_to_tenths_fraction",
		name: "දශමයෙන් භාගයට",
	},
] as const;

export const DECIMAL_GAMES = [
	{
		id: "decimal_reading_match",
		title: "දශමය කියවමු",
		difficulty: "පහසු",
		challengeLabel: "අභියෝග 1ක්",
	},
	{
		id: "decimal_tenths_shading",
		title: "කොටස් අඳුරු කරමු",
		difficulty: "පහසු–මධ්‍යම",
		challengeLabel: "අභියෝග 1ක්",
	},
	{
		id: "tenths_fraction_to_decimal",
		title: "දහයෙන් කොටස දශමයක් කරමු",
		difficulty: "මධ්‍යම",
		challengeLabel: "අභියෝග 1ක්",
	},
	{
		id: "decimal_to_tenths_fraction",
		title: "දශමය දහයෙන් කොටසක් කරමු",
		difficulty: "මධ්‍යම–අභියෝගාත්මක",
		challengeLabel: "අභියෝග 1ක්",
	},
] as const;

export const DECIMAL_READINGS: Record<number, string> = {
	1: "බින්දුවයි දශම එක",
	2: "බින්දුවයි දශම දෙක",
	3: "බින්දුවයි දශම තුන",
	4: "බින්දුවයි දශම හතර",
	5: "බින්දුවයි දශම පහ",
	6: "බින්දුවයි දශම හය",
	7: "බින්දුවයි දශම හත",
	8: "බින්දුවයි දශම අට",
	9: "බින්දුවයි දශම නවය",
};
