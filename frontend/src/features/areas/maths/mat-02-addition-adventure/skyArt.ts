/**
 * Art for Nimo's Sky Adventure. A file listed here is loaded only when `ready` is true; until
 * then the scenes draw a placeholder shape in its place, so missing art never breaks a game.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const SKY_ART_ROOT = "/curriculum/game/G5-AREA-MAT-02";

export const SKY_ART = {
	bgSkyCity: { file: "bg-sky-city.webp", ready: true },
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	nimoPlane: { file: NIMO.plane, ready: true },
	bgNumberFactory: { file: "bg-number-factory.webp", ready: true },
	bgCrystalSky: { file: "bg-crystal-sky.webp", ready: true },
	airshipRed: { file: "airship-red.webp", ready: true },
	airshipBlue: { file: "airship-blue.webp", ready: true },
	airshipOrange: { file: "airship-orange.webp", ready: true },
	crate: { file: "crate.webp", ready: true },
	warehouseLocked: { file: "warehouse-locked.webp", ready: true },
	warehouseOpen: { file: "warehouse-open.webp", ready: true },
	crystal: { file: "crystal.webp", ready: true },
	energyGate: { file: "energy-gate.webp", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type SkyArtKey = keyof typeof SKY_ART;

/** Public URL of an art file, for HTML and CSS outside the Phaser scenes. */
export function artUrl(key: SkyArtKey): string {
	const file: string = SKY_ART[key].file;
	// Shared art (Nimo) is listed by its full path.
	return file.startsWith("/") ? file : `${SKY_ART_ROOT}/${file}`;
}

/** The art the city scene draws. */
export const SKY_CITY_ART: SkyArtKey[] = [
	"bgSkyCity",
	"nimoIdle",
	"nimoCheer",
	"nimoThink",
	"airshipRed",
	"airshipBlue",
	"airshipOrange",
	"crate",
	"warehouseLocked",
	"warehouseOpen",
];

export function readyArt(
	keys: readonly SkyArtKey[],
): Array<[SkyArtKey, string]> {
	return (
		Object.entries(SKY_ART) as Array<
			[SkyArtKey, { file: string; ready: boolean }]
		>
	)
		.filter(([key, art]) => art.ready && keys.includes(key))
		.map(([key]) => [key, artUrl(key)]);
}
