/**
 * Art for Nimo's Wacky Toybox. A file is used only when `ready` is true; until then the games draw
 * a placeholder shape in its place, so missing art never breaks a game. Paths starting with "/"
 * are shared art (Nimo); the rest live in this area's folder.
 */

import { NIMO } from "../../../mobile-learning-flow/landscape/nimo";

export const TOY_ART_ROOT = "/curriculum/game/G5-AREA-MAT-01";

export const TOY_ART = {
	nimoIdle: { file: NIMO.idle, ready: true },
	nimoCheer: { file: NIMO.cheer, ready: true },
	nimoThink: { file: NIMO.think, ready: true },
	nimoDirector: { file: NIMO.director, ready: true },
	bgToyStage: { file: "bg-toy-stage.webp", ready: true },
	bgBeadWorkshop: { file: "bg-bead-workshop.webp", ready: true },
	bgCostumeShop: { file: "bg-costume-shop.webp", ready: true },
	toyRobot: { file: "toy-robot.webp", ready: true },
	toyDino: { file: "toy-dino.webp", ready: true },
	toyTrain: { file: "toy-train.webp", ready: true },
	toyTeddy: { file: "toy-teddy.webp", ready: true },
	abacusFrame: { file: "abacus-frame.png", ready: true },
	bead: { file: "bead.webp", ready: true },
	costumeCap: { file: "costume-cap.webp", ready: true },
	costumeSunhat: { file: "costume-sunhat.webp", ready: true },
	costumeCrown: { file: "costume-crown.webp", ready: true },
	costumeTophat: { file: "costume-tophat.webp", ready: true },
	costumeWizard: { file: "costume-wizard.webp", ready: true },
} as const satisfies Record<string, { file: string; ready: boolean }>;

export type ToyArtKey = keyof typeof TOY_ART;

export function toyArtUrl(key: ToyArtKey): string {
	const file: string = TOY_ART[key].file;
	return file.startsWith("/") ? file : `${TOY_ART_ROOT}/${file}`;
}

export function toyArtReady(key: ToyArtKey): boolean {
	return TOY_ART[key].ready;
}

/** The art the parade scene draws. */
export const PARADE_ART: ToyArtKey[] = [
	"bgToyStage",
	"nimoDirector",
	"nimoIdle",
	"nimoCheer",
	"nimoThink",
	"toyRobot",
	"toyDino",
	"toyTrain",
	"toyTeddy",
];

export function readyToyArt(
	keys: readonly ToyArtKey[],
): Array<[ToyArtKey, string]> {
	return keys.filter(toyArtReady).map((key) => [key, toyArtUrl(key)]);
}

/** The parade toy art in badge order (robot, dino, train, teddy). */
export const TOY_ART_KEYS: ToyArtKey[] = [
	"toyRobot",
	"toyDino",
	"toyTrain",
	"toyTeddy",
];

/** One costume per place, ones first: cap, sun hat, crown, top hat, wizard hat. */
export const COSTUME_ART_KEYS: ToyArtKey[] = [
	"costumeCap",
	"costumeSunhat",
	"costumeCrown",
	"costumeTophat",
	"costumeWizard",
];
