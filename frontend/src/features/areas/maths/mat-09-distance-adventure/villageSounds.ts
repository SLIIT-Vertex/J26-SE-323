import { createGameAudio } from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Village Walk, with its number of variation files. */
export const villageSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-09/audio",
	{
		tap: 1,
		tick: 2,
		place: 3,
		pick: 1,
		block: 2,
		remove: 1,
		exchange: 1,
		step: 3,
		tape: 1,
		snap: 1,
		car: 1,
		boing: 2,
		back: 1,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		"jingle-arrive": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);
