export const BLOOM_SKILL = {
	id: "G5-ENG-FLOWER-VOCAB-01",
	name: "Bloom Builder Garden",
	description: "Match flower names by inspecting petals, centres, and clusters.",
	icon: "🌱",
} as const;

export const BLOOM_STAGES = {
	seed_packet_match: { name: "Seed Packet Match", icon: "🌰", level: "Easy" },
	garden_bed_relay: { name: "Garden Bed Relay", icon: "🪴", level: "Medium" },
	petal_pattern_detective: { name: "Petal Pattern Detective", icon: "🔎", level: "Challenge" },
} as const;
