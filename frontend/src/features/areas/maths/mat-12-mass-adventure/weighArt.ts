/**
 * Art for Nimo's Parcel Day. A file is used only when `ready` is true; until then the games draw a
 * placeholder shape in its place. Paths starting with "/" are shared art (Nimo); `kit/` holds the
 * open-licence (CC0) pieces: wooden panels and keys, a sparkle, and the star and confetti bursts
 * when a box pops open.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const WEIGH_ART_ROOT = "/curriculum/game/G5-AREA-MAT-12";

export const WEIGH_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	/** The village delivery yard (the parcel cart). */
	bgYard: { file: "bg-yard.webp", ready: true },
	/** The cosy weighing room (the balance and the five scales). */
	bgRoom: { file: "bg-room.webp", ready: true },
	cart: { file: "parcel-cart.webp", ready: true },
	box: { file: "mystery-box.webp", ready: true },
	/** Photos of the real scales (the platform one also weighs the cart's boxes). */
	platformScale: { file: "scale-platform.webp", ready: true },
	balancePhoto: { file: "scale-balance.webp", ready: true },
	balanceStand: { file: "balance-stand.webp", ready: true },
	balanceBeam: { file: "balance-beam.webp", ready: true },
	balancePan: { file: "balance-pan.webp", ready: true },
	springScale: { file: "scale-spring.webp", ready: true },
	dialScale: { file: "scale-dial.webp", ready: true },
	digitalScale: { file: "scale-digital.webp", ready: true },
	sparkle: { file: "kit/sparkle.png", ready: true },
	starBurst: { file: "kit/star-burst.png", ready: true },
	confetti: { file: "kit/confetti.png", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type WeighArtKey = keyof typeof WEIGH_ART;

export function weighArtUrl(key: WeighArtKey): string {
	const file: string = WEIGH_ART[key].file;
	return file.startsWith("/") ? file : `${WEIGH_ART_ROOT}/${file}`;
}

export function weighArtReady(key: WeighArtKey): boolean {
	return WEIGH_ART[key].ready;
}

/** The surprise toys that pop out of a delivered box (drawn large). */
export const SURPRISES = ["🦆", "🤖", "🧸", "🪀", "🚂", "🪁"] as const;
