/**
 * Art for Nimo's Bubble Trouble. A file is used only when `ready` is true; until then the games
 * draw a placeholder shape in its place, so missing art never breaks a game. Paths starting with
 * "/" are shared art (Nimo); the rest live in this area's folder.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const BUBBLE_ART_ROOT = "/curriculum/game/G5-AREA-MAT-03";

export const BUBBLE_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The reef: the race course, and the backdrop of both help games. */
	bgReefRace: { file: "bg-reef-race.webp", ready: true },
	nimoSub: { file: "nimo-sub.webp", ready: true },
	octopus: { file: "octopus.webp", ready: true },
	jellyfish: { file: "jellyfish.webp", ready: true },
	magicShell: { file: "magic-shell.webp", ready: true },
	stepShell: { file: "step-shell.webp", ready: true },
	tikiIdle: { file: "tiki-idle.webp", ready: true },
	tikiJump: { file: "tiki-jump.webp", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type BubbleArtKey = keyof typeof BUBBLE_ART;

export function bubbleArtUrl(key: BubbleArtKey): string {
	const file: string = BUBBLE_ART[key].file;
	return file.startsWith("/") ? file : `${BUBBLE_ART_ROOT}/${file}`;
}

export function bubbleArtReady(key: BubbleArtKey): boolean {
	return BUBBLE_ART[key].ready;
}

/** The art the Bubble Rush scene draws. */
export const RUSH_ART: BubbleArtKey[] = ["bgReefRace", "nimoSub", "octopus"];

export function readyBubbleArt(
	keys: readonly BubbleArtKey[],
): Array<[BubbleArtKey, string]> {
	return keys.filter(bubbleArtReady).map((key) => [key, bubbleArtUrl(key)]);
}
