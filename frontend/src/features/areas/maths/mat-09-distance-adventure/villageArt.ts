/**
 * Art for Nimo's Village Walk. A file is used only when `ready` is true; until then the games draw
 * a placeholder shape in its place. Paths starting with "/" are shared art (Nimo); `kit/` holds the
 * open-licence (CC0) pieces: grass blocks, the finish flag, the garden fence, the toy car, leaves,
 * a sparkle, the compass, the place markers and the parchment of the distance board.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const VILLAGE_ART_ROOT = "/curriculum/game/G5-AREA-MAT-09";

export const VILLAGE_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The village map: home, the little shop and the market (the mission). */
	bgVillage: { file: "bg-village.webp", ready: true },
	/** The playhouse floor where the toy road is built. */
	bgToyroom: { file: "bg-toyroom.webp", ready: true },
	/** The home garden where Tikki measures. */
	bgGarden: { file: "bg-garden.webp", ready: true },
	/** Road pieces dragged onto the map: a straight one and a bending one. */
	roadStraight: { file: "road-straight.webp", ready: true },
	roadBend: { file: "road-bend.webp", ready: true },
	/** Tikki the snail, who loves measuring. */
	tikkiIdle: { file: "tikki-idle.webp", ready: true },
	tikkiHappy: { file: "tikki-happy.webp", ready: true },
	tikkiThink: { file: "tikki-think.webp", ready: true },
	grassLeft: { file: "kit/grass-left.png", ready: true },
	grassRight: { file: "kit/grass-right.png", ready: true },
	flag: { file: "kit/flag-red.png", ready: true },
	fence: { file: "kit/fence.png", ready: true },
	toyCar: { file: "kit/toy-car.png", ready: true },
	leafGreen: { file: "kit/leaf-green.png", ready: true },
	leafGold: { file: "kit/leaf-gold.png", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
	compass: { file: "kit/compass.png", ready: true },
	placeNode: { file: "kit/place-node.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type VillageArtKey = keyof typeof VILLAGE_ART;

export function villageArtUrl(key: VillageArtKey): string {
	const file: string = VILLAGE_ART[key].file;
	return file.startsWith("/") ? file : `${VILLAGE_ART_ROOT}/${file}`;
}

export function villageArtReady(key: VillageArtKey): boolean {
	return VILLAGE_ART[key].ready;
}

export const PARCHMENT_URL = `${VILLAGE_ART_ROOT}/kit/parchment.jpg`;
