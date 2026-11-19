import {
	createGameAudio,
	noteFrequency,
	playTone,
} from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Wacky Sports Carnival, with its number of variation files. */
export const carnivalSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-06/audio",
	{
		tap: 1,
		tick: 2,
		pick: 2,
		lap: 2,
		zoom: 2,
		boost: 1,
		seat: 2,
		pins: 3,
		roll: 1,
		back: 1,
		boing: 2,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		"jingle-race": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);

/** A counting note that climbs with each group (3 → 6 → 9 → 12 sounds like a little scale). */
export function countNote(step: number): void {
	playTone(noteFrequency(step % 14), { duration: 0.2, volume: 0.6 });
}
