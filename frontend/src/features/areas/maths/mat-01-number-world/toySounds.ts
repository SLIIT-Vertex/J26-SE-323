import {
	createGameAudio,
	noteFrequency,
	playTone,
} from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every sound of Nimo's Wacky Toybox, with its number of variation files. */
export const toySounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-01/audio",
	{
		tap: 1,
		pick: 2,
		place: 3,
		boing: 3,
		back: 1,
		puzzled: 1,
		swish: 3,
		sparkle: 1,
		whoosh: 1,
		hmm: 1,
		"jingle-parade": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);

/**
 * The bead toy's note: each rod has its own starting note and every bead on it sounds one step
 * higher, so filling a rod plays a little rising scale.
 */
export function beadNote(rod: number, beads: number): void {
	playTone(noteFrequency(rod + beads), { duration: 0.32, volume: 0.9 });
}

/** A short happy melody when a number is built on the bead toy. */
export function beadMelody(): void {
	[0, 2, 4, 7, 9, 7].forEach((step, at) => {
		playTone(noteFrequency(step + 7), {
			delay: at * 0.12,
			duration: 0.25,
			volume: 0.8,
		});
	});
}
