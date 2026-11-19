/**
 * Art for Nimo's Silly Movie Studio. A file is used only when `ready` is true; until then the games
 * draw a placeholder shape in its place. Paths starting with "/" are shared art (Nimo); `kit/` holds
 * the open-licence (CC0) pieces: icons, pawns, the scene-card panel and ribbon, the sun and moon
 * puppets, clouds, the growing tree and sparkles.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const STUDIO_ART_ROOT = "/curriculum/game/G5-AREA-MAT-07";

export const STUDIO_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	nimoDirector: { file: NIMO.director, ready: true },
	/** The studio lot: the scene card, and the backdrop of both help games. */
	bgStudio: { file: "bg-studio.webp", ready: true },
	sunPuppet: { file: "kit/sun-puppet.png", ready: true },
	moonPuppet: { file: "kit/moon-puppet.png", ready: true },
	cloud1: { file: "kit/cloud1.png", ready: true },
	cloud3: { file: "kit/cloud3.png", ready: true },
	sapling: { file: "kit/sapling.png", ready: true },
	tree: { file: "kit/tree.png", ready: true },
	pawnBlue: { file: "kit/pawn-blue.png", ready: true },
	pawnRed: { file: "kit/pawn-red.png", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type StudioArtKey = keyof typeof STUDIO_ART;

export function studioArtUrl(key: StudioArtKey): string {
	const file: string = STUDIO_ART[key].file;
	return file.startsWith("/") ? file : `${STUDIO_ART_ROOT}/${file}`;
}

export function studioArtReady(key: StudioArtKey): boolean {
	return STUDIO_ART[key].ready;
}

/** The white icons, tinted with a CSS mask. */
export const ICONS = {
	forward: `${STUDIO_ART_ROOT}/kit/icon-fastForward.png`,
	rewind: `${STUDIO_ART_ROOT}/kit/icon-rewind.png`,
	again: `${STUDIO_ART_ROOT}/kit/icon-return.png`,
	film: `${STUDIO_ART_ROOT}/kit/icon-movie.png`,
	clapper: `${STUDIO_ART_ROOT}/kit/icon-video.png`,
	trophy: `${STUDIO_ART_ROOT}/kit/icon-trophy.png`,
} as const;

/** What each scene films: a small picture on the scene's film frame (the same scene, the same one). */
export const SCENES = ["🦖", "🐔", "🐘", "🌙", "🎈", "🚀"] as const;
export const PANEL = `${STUDIO_ART_ROOT}/kit/panel.png`;
export const RIBBON = `${STUDIO_ART_ROOT}/kit/ribbon.png`;
