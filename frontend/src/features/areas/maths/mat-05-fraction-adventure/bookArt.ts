/**
 * Art for Nimo's Magic Picture Book. A file is used only when `ready` is true; until then the games
 * draw a placeholder shape in its place, so missing art never breaks a game. Paths starting with
 * "/" are shared art (Nimo); `kit/` holds the open-licence pieces (sticker friends, splats,
 * sparkles, paper texture, the sticker star).
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const BOOK_ART_ROOT = "/curriculum/game/G5-AREA-MAT-05";

export const BOOK_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The picture-book room: the comic page, and the backdrop of both help games. */
	bgBook: { file: "bg-book.webp", ready: true },
	nimoPainter: { file: "nimo-painter.webp", ready: true },
	pipi: { file: "pipi.webp", ready: true },
	flowerBlank: { file: "flower-blank.webp", ready: true },
	flowerPainted: { file: "flower-painted.webp", ready: true },
	envelope: { file: "envelope.webp", ready: true },
	butterfly: { file: "paper-butterfly.webp", ready: true },
	friend1: { file: "kit/friend-1.webp", ready: true },
	friend2: { file: "kit/friend-2.webp", ready: true },
	friend3: { file: "kit/friend-3.webp", ready: true },
	friend4: { file: "kit/friend-4.webp", ready: true },
	star: { file: "kit/sticker-star.svg", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
	magic: { file: "kit/magic.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type BookArtKey = keyof typeof BOOK_ART;

export function bookArtUrl(key: BookArtKey): string {
	const file: string = BOOK_ART[key].file;
	return file.startsWith("/") ? file : `${BOOK_ART_ROOT}/${file}`;
}

export function bookArtReady(key: BookArtKey): boolean {
	return BOOK_ART[key].ready;
}

export const FRIENDS: BookArtKey[] = [
	"friend1",
	"friend2",
	"friend3",
	"friend4",
];

/** The three paint splats (white, tinted by the chosen paint). */
export const SPLATS = [1, 2, 3].map(
	(index) => `${BOOK_ART_ROOT}/kit/splat-${index}.png`,
);

/** The paint pots: the brush paints with the chosen colour. */
export const PAINTS = ["#ff6fae", "#ffc23d", "#4fa7ff", "#a66cf0"] as const;
