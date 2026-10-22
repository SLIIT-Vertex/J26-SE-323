export type AdditionChapter =
	| "fruit_catch"
	| "tuk_tuk_journey"
	| "carrying_crane"
	| "market_delivery_planner"
	| "festival_data_detective";

export const ADDITION_SKILLS = [
	{ id: "G5-MAT-ADD-MENTAL-01", chapter: "fruit_catch", name: "පළතුරු එකතු කර මුළු ගණන හදමු" },
	{ id: "G5-MAT-C06-L01-O01", chapter: "carrying_crane", name: "ගෙනයාම් දෙකක් සහිත භාණ්ඩ හුවමාරුව" },
	{ id: "G5-MAT-C06-L01-O02", chapter: "carrying_crane", name: "ගෙනයාම් දෙකකට වැඩි භාණ්ඩ හුවමාරුව" },
	{ id: "G5-MAT-C06-L01-O03", chapter: "carrying_crane", name: "භාණ්ඩ කාණ්ඩ තුනක් එකතු කරමු" },
	{ id: "G5-MAT-ADD-RUNNING-TOTAL-01", chapter: "tuk_tuk_journey", name: "ටුක්-ටුක් සමුච්චිත එකතුව" },
	{ id: "G5-MAT-ADD-CONTEXT-01", chapter: "market_delivery_planner", name: "වෙළඳපොළ ඇණවුම් කරත්තයට පටවමු" },
	{ id: "G5-MAT-ADD-TABLE-TOTAL-01", chapter: "festival_data_detective", name: "උත්සව වගුවේ අදාළ කොටු එකතු කරමු" },
	{ id: "G5-MAT-ADD-TABLE-DIFFERENCE-01", chapter: "festival_data_detective", name: "උත්සව එකතු දෙකක වෙනස සොයමු" },
	{ id: "G5-MAT-ADD-TABLE-MAX-01", chapter: "festival_data_detective", name: "වැඩිම පේළි එකතුව සොයමු" },
] as const;

const ROOT = "/curriculum/game/G5-AREA-MAT-02";

export const ADDITION_CHAPTERS: Array<{ id: AdditionChapter; title: string; asset: string; difficulty: string }> = [
	{ id: "fruit_catch", title: "ඉක්මන් එකතු උයන", asset: `${ROOT}/addition-skill-badge.png`, difficulty: "පහසු" },
	{ id: "tuk_tuk_journey", title: "එකතු කිරීමේ මාර්ගය", asset: `${ROOT}/tuk-tuk.png`, difficulty: "පහසු" },
	{ id: "carrying_crane", title: "ගෙනයාමේ දොඹකරය", asset: `${ROOT}/carrying-crane.png`, difficulty: "මධ්‍යම" },
	{ id: "market_delivery_planner", title: "වෙළඳපොළ බෙදාහැරීම් සැලසුම", asset: `${ROOT}/delivery-handcart.png`, difficulty: "මධ්‍යම" },
	{ id: "festival_data_detective", title: "ජීවමාන වගු රහස් පරීක්ෂක", asset: `${ROOT}/school-building-token-b.png`, difficulty: "අභියෝගාත්මක" },
];

export const ADDITION_ASSET_ROOT = ROOT;
