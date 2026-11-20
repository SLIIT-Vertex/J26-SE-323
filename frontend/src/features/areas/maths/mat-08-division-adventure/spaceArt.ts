/**
 * Art for Nimo's Galactic Sleepover. A file is used only when `ready` is true; until then the games
 * draw a placeholder shape in its place. Paths starting with "/" are shared art (Nimo); `kit/` holds
 * the open-licence (CC0) pieces: the UFOs, the helmeted alien passengers, the glass dome of the
 * sleeping pods, and the shuttle, station and star that carry bundles of 10 and 100.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const SPACE_ART_ROOT = "/curriculum/game/G5-AREA-MAT-08";

export const SPACE_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The space station: the boarding deck, and the backdrop of both help games. */
	bgSpace: { file: "bg-space.webp", ready: true },
	dome: { file: "kit/dome.png", ready: true },
	/** A bundle of 10 aliens rides a shuttle; a bundle of 100 a station; star bundles are stars. */
	shuttle: { file: "kit/shuttle.png", ready: true },
	station: { file: "kit/station.png", ready: true },
	starBundle: { file: "kit/star-bundle.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type SpaceArtKey = keyof typeof SPACE_ART;

export function spaceArtUrl(key: SpaceArtKey): string {
	const file: string = SPACE_ART[key].file;
	return file.startsWith("/") ? file : `${SPACE_ART_ROOT}/${file}`;
}

export function spaceArtReady(key: SpaceArtKey): boolean {
	return SPACE_ART[key].ready;
}

/** The UFO colours, in order; each has a saucer and a helmeted alien. */
export const COLOURS = ["pink", "blue", "green", "yellow", "beige"] as const;
export type Colour = (typeof COLOURS)[number];
export const colourAt = (index: number): Colour =>
	COLOURS[index % COLOURS.length] ?? "pink";
export const ufoUrl = (colour: Colour) =>
	`${SPACE_ART_ROOT}/kit/ufo-${colour}.png`;
export const alienUrl = (colour: Colour) =>
	`${SPACE_ART_ROOT}/kit/alien-${colour}.png`;
