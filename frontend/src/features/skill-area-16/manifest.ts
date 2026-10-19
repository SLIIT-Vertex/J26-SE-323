export const ROMAN_ASSET_ROOT = "/curriculum/game/G5-AREA-MAT-16";
export const ROMAN_SKILLS = [
	{
		id: "G5-MAT-ROMAN-MATCH-01",
		chapter: "roman_match",
		name: "අංකය හා රෝම සංඛ්‍යාව ගළපමු",
	},
	{
		id: "G5-MAT-ROMAN-COUNT-01",
		chapter: "emoji_count",
		name: "රූප ගණන රෝම සංඛ්‍යාවක් කරමු",
	},
	{
		id: "G5-MAT-ROMAN-ARITHMETIC-01",
		chapter: "roman_arithmetic",
		name: "රෝම සංඛ්‍යා එකතු කර අඩු කරමු",
	},
] as const;
export const ROMAN_GAMES = [
	{
		id: "roman_match",
		title: "රෝම පාලම",
		difficulty: "පහසු",
		challengeLabel: "අභියෝග 1ක්",
		asset: "roman-arch-frame.png",
	},
	{
		id: "emoji_count",
		title: "ඉමෝජි ගණන් කරමු",
		difficulty: "පහසු–මධ්‍යම",
		challengeLabel: "අභියෝග 1ක්",
		asset: "roman-guide.png",
	},
	{
		id: "roman_arithmetic",
		title: "රෝම ගණිත වැඩහල",
		difficulty: "මධ්‍යම–අභියෝගාත්මක",
		challengeLabel: "අභියෝග 1ක්",
		asset: "roman-scroll-panel.png",
	},
] as const;
export const EMOJI_LABELS: Record<string, string> = {
	flower: "මල",
	football: "පාපන්දුව",
	mango: "අඹ ගෙඩිය",
	cherries: "චෙරි යුගලය",
	leaf: "කොළය",
	pencil: "පැන්සල",
	star: "තරුව",
	shell: "බෙල්ල",
};
