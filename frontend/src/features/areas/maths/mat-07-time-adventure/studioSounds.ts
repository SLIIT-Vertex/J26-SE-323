import {
	createGameAudio,
	noteFrequency,
	playTone,
} from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Silly Movie Studio, with its number of variation files. */
export const studioSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-07/audio",
	{
		tap: 1,
		tick: 3,
		clap: 1,
		reel: 2,
		forward: 2,
		rewind: 2,
		pick: 2,
		swap: 1,
		back: 1,
		boing: 2,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		"jingle-scene": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);

/** The hour chime: one soft bell when 60 minutes become an hour. */
export function hourChime(): void {
	playTone(noteFrequency(12), { duration: 0.6, volume: 0.7 });
	playTone(noteFrequency(7), { delay: 0.12, duration: 0.6, volume: 0.5 });
}
