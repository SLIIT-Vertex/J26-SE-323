import { createGameAudio } from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Shopping Day, with its number of variation files. */
export const shopSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-10/audio",
	{
		tap: 1,
		key: 2,
		pick: 1,
		basket: 2,
		coin: 2,
		drop: 2,
		note: 2,
		exchange: 1,
		wobble: 2,
		spit: 1,
		back: 1,
		boing: 1,
		pay: 1,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		"jingle-paid": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);
