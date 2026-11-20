/**
 * Art for Nimo's Water-Play Day. A file is used only when `ready` is true; until then the games draw
 * a placeholder shape in its place. Paths starting with "/" are shared art (Nimo); `kit/` holds the
 * open-licence (CC0) pieces: toy sailboats, fish, rocks and seaweed, pipes (empty and full), a water
 * splash, wooden panels and keys, and a sparkle.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const WATER_ART_ROOT = "/curriculum/game/G5-AREA-MAT-11";

export const WATER_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The home garden: the boat race, the fountain and the balloons all happen here. */
	bgGarden: { file: "bg-garden.webp", ready: true },
	/** The empty stone racing channel the water fills. */
	channel: { file: "race-channel.webp", ready: true },
	/** A big see-through water tank with a tap. */
	tank: { file: "water-tank.webp", ready: true },
	/** An empty measuring jug; its marks and amount are written by the game. */
	jug: { file: "measuring-jug.webp", ready: true },
	/** A 1 l bottle that fills when 1000 ml are poured in. */
	bottle: { file: "litre-bottle.webp", ready: true },
	fountainCalm: { file: "fountain-calm.webp", ready: true },
	fountainDancing: { file: "fountain-dancing.webp", ready: true },
	balloon: { file: "water-balloon.webp", ready: true },
	boatRed: { file: "kit/boat-red.png", ready: true },
	boatBlue: { file: "kit/boat-blue.png", ready: true },
	boatYellow: { file: "kit/boat-yellow.png", ready: true },
	fishOrange: { file: "kit/fish-orange.png", ready: true },
	fishPink: { file: "kit/fish-pink.png", ready: true },
	rock: { file: "kit/rock.png", ready: true },
	seaweed: { file: "kit/seaweed.png", ready: true },
	pipeEmpty: { file: "kit/pipe-empty.png", ready: true },
	pipeFull: { file: "kit/pipe-full.png", ready: true },
	splash: { file: "kit/splash.png", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type WaterArtKey = keyof typeof WATER_ART;

export function waterArtUrl(key: WaterArtKey): string {
	const file: string = WATER_ART[key].file;
	return file.startsWith("/") ? file : `${WATER_ART_ROOT}/${file}`;
}

export function waterArtReady(key: WaterArtKey): boolean {
	return WATER_ART[key].ready;
}
