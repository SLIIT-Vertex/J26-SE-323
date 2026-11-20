import { createGameAudio } from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Galactic Sleepover, with its number of variation files. */
export const spaceSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-08/audio",
	{
		tap: 1,
		tick: 2,
		beam: 3,
		split: 1,
		launch: 1,
		boing: 3,
		snore: 1,
		back: 1,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		"jingle-launch": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);
