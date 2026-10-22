/**
 * What each English game's `renderer_variant` shows. The server keeps the meaning out of the
 * payload (targets are opaque tokens), so the board draws a picture a child can recognise without
 * printing the word that would give the answer away. Indexes follow the backend content modules.
 */

export const OBJECT_PICTURES: Record<number, string> = {
	0: "🪑", // Chair
	1: "✏️", // Pencil
	2: "📏", // Ruler
	3: "🛏️", // Bed
	4: "🥄", // Spoon
	5: "🪥", // Toothbrush
	6: "🧹", // Broom
	7: "🍽️", // Plate
	8: "📕", // Text Book
	9: "📒", // Work Book
	10: "🍱", // Lunch box
	11: "📔", // Record Book
	12: "✏️🔪", // Pencil Sharpener
	13: "📎", // Stapler Machine
};

export const FOOD_PICTURES: Record<number, string> = {
	0: "🥚",
	1: "🍞",
	2: "🐟",
	3: "🥥",
	11: "🍠",
	12: "🍵",
	13: "🥛",
	14: "💧",
	15: "🧃",
	16: "🍌",
	17: "🍍",
	18: "🥭",
	19: "🍉",
	20: "🫒",
	21: "🥔",
	22: "🥬",
	23: "🍅",
	24: "🥕",
	25: "🥒",
	26: "🍛", // Rice and Curry
	27: "🍨", // Ice Cream
	31: "🌿", // Curry Leaves
};

export const STALL_PICTURES: Record<number, string> = {
	0: "🍞🥚🐟",
	1: "🍠🥔",
	2: "🥛🧃",
	3: "🍌🥭",
	4: "🥬🥕",
};

export const GARMENT_PICTURES: Record<number, string> = {
	0: "👟",
	1: "🧦",
	2: "👗",
	3: "🩳",
	4: "👕",
	5: "👖",
	6: "🟫", // Sarong: drawn as a wrapped cloth
	7: "🥻",
	8: "👚",
	9: "👗",
};

export const WATER_PICTURES: Record<number, string> = {
	0: "🛁", // Bathe
	1: "🍲", // Cook
	2: "🧼", // Wash
	3: "🥤", // Drink
	4: "🌱🚿", // Water the plants
};

export const VEHICLE_PICTURES: Record<number, string> = {
	0: "🚆",
	1: "🚲",
	2: "🚁",
	3: "✈️",
	4: "🚌",
	5: "🚗",
};

export const FLOWER_PICTURES: Record<number, string> = {
	0: "🌼", // Marigold
	1: "🌺", // Shoe flower
	2: "🌹",
	3: "🌻",
	4: "🤍🌸", // Jasmine
};

export const WORKER_PICTURES: Record<number, string> = {
	0: "🧑‍🌾",
	1: "🐟🧑",
	2: "🧑‍🏫",
	3: "🧑‍⚕️",
	4: "🧑‍🔧⚡",
	5: "🧱🧑‍🏭",
	6: "🪚🧑‍🔧",
};

export const WORKPLACE_PICTURES: Record<number, string> = {
	0: "🌾",
	1: "🐟🏪",
	2: "🏫",
	3: "🏥",
	4: "🏢",
	5: "🛠️",
};

export const EARTH_SKY_PICTURES: Record<number, string> = {
	0: "🌌",
	1: "☀️",
	2: "🌙",
	3: "⭐",
	4: "🌈",
	5: "☁️",
	6: "🌧️",
	7: "🏞️",
	8: "💧💧",
	9: "🌊🏠",
	10: "🌊",
	11: "🏖️",
	12: "💦⛰️",
	13: "🪣",
	14: "🦆💧",
};

export const PLACE_PICTURES: Record<number, string> = {
	0: "🔬",
	1: "👩‍🏫☕",
	2: "📚",
	3: "💻",
	4: "🧑‍🎓",
	5: "🍽️🥪",
	6: "🗄️",
	7: "⚽",
	8: "🚪",
	9: "🪟",
	10: "🏠",
	11: "🧱",
	12: "🍳",
	13: "🛋️",
	14: "🛁",
	15: "🛏️",
	16: "📦",
};

export const INFORMATION_PICTURES: Record<number, string> = {
	0: "📰",
	1: "☎️",
};

export const EXHIBIT_PICTURES: Record<number, string> = {
	0: "🪵",
	1: "🗿",
	2: "🏯",
	3: "🪑👑",
	4: "👑",
};

export const ANIMAL_PICTURES: Record<number, string> = {
	0: "🐕",
	1: "🐘",
	2: "🐇",
	3: "🦚",
	4: "🦋",
	5: "🐄",
	6: "🐒",
	7: "🦉",
};

/** Classroom situations (Classroom Language): the moment, not the words said in it. */
export const SITUATION_PICTURES: Record<number, string> = {
	0: "🌅🧑‍🏫",
	1: "🎂",
	2: "🏆",
	3: "🤕",
	4: "🚪✊",
	5: "🎁",
};

/** Classroom commands the character can act out (Classroom Language). */
export const COMMAND_ACTIONS: Record<number, { emoji: string; label: string }> =
	{
		0: { emoji: "🙌", label: "Raise both hands" },
		1: { emoji: "🙇", label: "Put hands down" },
		2: { emoji: "🏃", label: "Run" },
		3: { emoji: "🤸", label: "Jump" },
		4: { emoji: "🏁", label: "Start" },
		5: { emoji: "👏", label: "Clap" },
		6: { emoji: "👀", label: "Look at the teacher" },
		7: { emoji: "🧍🧍🧍", label: "Stand in a line" },
		8: { emoji: "⭕", label: "Stand in a circle" },
		9: { emoji: "🚫🚪", label: "Stay inside" },
		10: { emoji: "🎒", label: "Get your things ready" },
	};

export function picture(
	table: Record<number, string>,
	variant: unknown,
): string {
	return table[Number(variant)] ?? "❔";
}

/** Pictures for word cards, by English word, for boards whose words name things. */
const WORDS: Record<string, string> = {
	temple: "🛕",
	kovil: "🛕",
	church: "⛪",
	mosque: "🕌",
	crib: "🌟",
	kolam: "🎨",
	"christmas tree": "🎄",
	"vesak lantern": "🏮",
	"blue waterlily": "🪷",
	volleyball: "🏐",
	"jungle fowl": "🐓",
	"'na' tree": "🌳",
	"national tree": "🌳",
	"national bird": "🐦",
	"national flower": "🌸",
	"national game": "🏅",
	places: "📍",
	"cultural & festival objects": "🎉",
	dog: "🐕",
	elephant: "🐘",
	rabbit: "🐇",
	peacock: "🦚",
	butterfly: "🦋",
	cow: "🐄",
	monkey: "🐒",
	owl: "🦉",
	parrot: "🦜",
	ant: "🐜",
	cat: "🐈",
	animals: "🐾",
	birds: "🐦",
	insects: "🐞",
	mango: "🥭",
	egg: "🥚",
	tea: "🍵",
	cabbage: "🥬",
	"sweet potatoes": "🍠",
	bread: "🍞",
	fish: "🐟",
	milk: "🥛",
	water: "💧",
	banana: "🍌",
	pineapple: "🍍",
	carrot: "🥕",
	tomato: "🍅",
	potato: "🥔",
	coconut: "🥥",
	watermelon: "🍉",
	cucumber: "🥒",
	"fruit juice": "🧃",
};

export function wordPicture(text: unknown): string | undefined {
	return WORDS[
		String(text ?? "")
			.trim()
			.toLowerCase()
	];
}
