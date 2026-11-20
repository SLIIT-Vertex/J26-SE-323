import { createGameAudio } from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Water-Play Day, with its number of variation files. */
export const waterSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-11/audio",
	{
		tap: 1,
		key: 2,
		pick: 1,
		pour: 3,
		glass: 2,
		"tap-open": 1,
		bloop: 2,
		exchange: 1,
		splash: 1,
		whoosh: 1,
		wobble: 1,
		back: 1,
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
