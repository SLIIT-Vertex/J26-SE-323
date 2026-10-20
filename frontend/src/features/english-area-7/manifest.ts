export const WARDROBE_SKILL = {
	id: "G5-ENG-CLOTHES-VOCAB-01",
	name: "Rainbow Wardrobe Quest",
	description: "Match clothes words through three colourful wardrobe challenges.",
	icon: "👚",
} as const;

export const WARDROBE_STAGES = {
	closet_flip: { name: "Closet Flip", icon: "🚪", level: "Easy" },
	laundry_line_relay: { name: "Laundry Line Relay", icon: "🧺", level: "Medium" },
	style_detective: { name: "Style Detective", icon: "🔎", level: "Challenge" },
} as const;
