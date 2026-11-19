/**
 * Art for Nimo's Wacky Sports Carnival. A file is used only when `ready` is true; until then the
 * games draw a placeholder shape in its place, so missing art never breaks a game. Paths starting
 * with "/" are shared art (Nimo); `kit/` holds open-licence (CC0) effects (dust, sparkles).
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const CARNIVAL_ART_ROOT = "/curriculum/game/G5-AREA-MAT-06";

export const CARNIVAL_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The carnival race track: the race, and the backdrop of both help games. */
	bgCarnival: { file: "bg-carnival.webp", ready: true },
	nimoKart: { file: "nimo-kart.webp", ready: true },
	rivalBanana: { file: "rival-banana.webp", ready: true },
	rivalTurtle: { file: "rival-turtle.webp", ready: true },
	pinUp: { file: "pin-up.webp", ready: true },
	pinDown: { file: "pin-down.webp", ready: true },
	dust: { file: "kit/dust.png", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type CarnivalArtKey = keyof typeof CARNIVAL_ART;

export function carnivalArtUrl(key: CarnivalArtKey): string {
	const file: string = CARNIVAL_ART[key].file;
	return file.startsWith("/") ? file : `${CARNIVAL_ART_ROOT}/${file}`;
}

export function carnivalArtReady(key: CarnivalArtKey): boolean {
	return CARNIVAL_ART[key].ready;
}

/** The stadium crowd: one waving animal per seat block. */
export const SPECTATORS = [
	"🐼",
	"🐰",
	"🦊",
	"🐻",
	"🐨",
	"🐯",
	"🐸",
	"🐵",
] as const;
