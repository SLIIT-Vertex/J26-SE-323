/**
 * Art for Nimo's Shopping Day. A file is used only when `ready` is true; until then the games draw
 * a placeholder shape in its place. Paths starting with "/" are shared art (Nimo); `kit/` holds the
 * open-licence (CC0) pieces: blank coins, wooden panels and keys, the shop's pots and teapots,
 * Nimo's wallet and a sparkle.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const SHOP_ART_ROOT = "/curriculum/game/G5-AREA-MAT-10";

export const SHOP_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The grocery shop: the shopping trip and the cash-box counter. */
	bgShop: { file: "bg-shop.webp", ready: true },
	/** The play shop where the coin box stands. */
	bgPlayshop: { file: "bg-playshop.webp", ready: true },
	sackRice: { file: "sack-rice.webp", ready: true },
	sackDhal: { file: "sack-dhal.webp", ready: true },
	sackSugar: { file: "sack-sugar.webp", ready: true },
	basket: { file: "basket.webp", ready: true },
	cashboxIdle: { file: "cashbox-idle.webp", ready: true },
	cashboxHappy: { file: "cashbox-happy.webp", ready: true },
	/** Play notes that look like the real ones (colour, bird and scene); the value is written in code. */
	note20: { file: "note-20.webp", ready: true },
	note50: { file: "note-50.webp", ready: true },
	note100: { file: "note-100.webp", ready: true },
	note500: { file: "note-500.webp", ready: true },
	note1000: { file: "note-1000.webp", ready: true },
	note5000: { file: "note-5000.webp", ready: true },
	itemTeapot: { file: "kit/item-teapot.png", ready: true },
	itemPot: { file: "kit/item-pot.png", ready: true },
	itemFlask: { file: "kit/item-flask.png", ready: true },
	itemBowl: { file: "kit/item-bowl.png", ready: true },
	wallet: { file: "kit/wallet.png", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type ShopArtKey = keyof typeof SHOP_ART;

export function shopArtUrl(key: ShopArtKey): string {
	const file: string = SHOP_ART[key].file;
	return file.startsWith("/") ? file : `${SHOP_ART_ROOT}/${file}`;
}

export function shopArtReady(key: ShopArtKey): boolean {
	return SHOP_ART[key].ready;
}

export const kitUrl = (name: string) => `${SHOP_ART_ROOT}/kit/${name}.png`;

/** The sack of each grocery product. */
export const SACKS: Record<string, ShopArtKey> = {
	"rice-1kg": "sackRice",
	"dhal-1kg": "sackDhal",
	"sugar-1kg": "sackSugar",
};

/** The picture of each note. */
export const NOTES: Record<string, ShopArtKey> = {
	"note-20": "note20",
	"note-50": "note50",
	"note-100": "note100",
	"note-500": "note500",
	"note-1000": "note1000",
	"note-5000": "note5000",
};

/** The shop items of a two-price sum (adding) and of the one thing bought (subtracting). */
export const ITEMS: ShopArtKey[] = [
	"itemTeapot",
	"itemPot",
	"itemFlask",
	"itemBowl",
];
