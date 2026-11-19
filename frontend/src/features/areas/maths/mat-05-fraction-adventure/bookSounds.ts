import {
	createGameAudio,
	noteFrequency,
	playTone,
} from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Magic Picture Book, with its number of variation files. */
export const bookSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-05/audio",
	{
		tap: 1,
		paint: 3,
		page: 3,
		book: 1,
		fold: 2,
		pick: 2,
		drop: 2,
		back: 1,
		boing: 2,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		magic: 1,
		"jingle-comic": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);

/** A flower opening: a note that climbs with each painted flower. */
export function bloomNote(count: number): void {
	playTone(noteFrequency(count % 14), { duration: 0.22, volume: 0.6 });
}
