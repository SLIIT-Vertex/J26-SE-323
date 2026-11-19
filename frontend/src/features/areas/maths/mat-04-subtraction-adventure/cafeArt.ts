/**
 * Art for Nimo's Midnight Monster Café. A file is used only when `ready` is true; until then the
 * games draw a placeholder shape in its place, so missing art never breaks a game. Paths starting
 * with "/" are shared art (Nimo); the rest live in this area's folder.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";
import type { Place, Snack } from "./cafeRules";

export const CAFE_ART_ROOT = "/curriculum/game/G5-AREA-MAT-04";

export const CAFE_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The café: the order counter, and the backdrop of both help games. */
	bgCafe: { file: "bg-cafe.webp", ready: true },
	nimoChef: { file: "nimo-chef.webp", ready: true },
	monsterGreen: { file: "monster-green.webp", ready: true },
	monsterPink: { file: "monster-pink.webp", ready: true },
	monsterPurple: { file: "monster-purple.webp", ready: true },
	packet: { file: "packet-10.webp", ready: true },
	box: { file: "box-100.webp", ready: true },
	crate: { file: "crate-1000.webp", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

/** Small snacks are drawn as emoji: they read well at 40–110 px and need no art. */
export const CAFE_EMOJI = {
	cupcake: "🧁",
	cookie: "🍪",
	donut: "🍩",
	candy: "🍬",
} as const;

export type CafeArtKey = keyof typeof CAFE_ART | keyof typeof CAFE_EMOJI;
export type FileKey = keyof typeof CAFE_ART;

export function isCafeFile(key: CafeArtKey): key is FileKey {
	return key in CAFE_ART;
}

/** The emoji of a snack, or `null` for art that comes from a file. */
export function cafeEmoji(key: CafeArtKey): string | null {
	return isCafeFile(key) ? null : CAFE_EMOJI[key];
}

export function cafeArtUrl(key: FileKey): string {
	const file: string = CAFE_ART[key].file;
	return file.startsWith("/") ? file : `${CAFE_ART_ROOT}/${file}`;
}

export function cafeArtReady(key: CafeArtKey): boolean {
	return isCafeFile(key) && CAFE_ART[key].ready;
}

/** The three customers, in seat order, with their names. */
export const MONSTERS = [
	{ key: "monsterGreen", name: "ගූගූ", colour: "#8fd14f" },
	{ key: "monsterPink", name: "පිංකි", colour: "#ff8fc0" },
	{ key: "monsterPurple", name: "බුබු", colour: "#a98cf0" },
] as const satisfies ReadonlyArray<{
	key: CafeArtKey;
	name: string;
	colour: string;
}>;

/** The snack pack of each place: a single candy, a packet of 10, a box of 100, a crate of 1000. */
export const PACK_ART: Record<Place, CafeArtKey> = {
	ones: "candy",
	tens: "packet",
	hundreds: "box",
	thousands: "crate",
};

export const SNACK_ART: Record<Snack, CafeArtKey> = {
	cupcake: "cupcake",
	cookie: "cookie",
	donut: "donut",
};
