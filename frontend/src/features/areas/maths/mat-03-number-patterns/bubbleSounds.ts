import {
	createGameAudio,
	noteFrequency,
	playTone,
} from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Bubble Trouble, with its number of variation files. */
export const bubbleSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-03/audio",
	{
		tap: 1,
		pick: 2,
		swoosh: 3,
		pop: 3,
		splash: 1,
		boing: 2,
		puzzled: 1,
		sparkle: 1,
		magic: 1,
		hmm: 1,
		"jingle-race": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);

/** A bubble blip: a quick rising slide, higher for later bubbles. */
export function bubbleBlip(step = 0, delay = 0): void {
	const from = noteFrequency(step) * 0.75;
	playTone(from, { glideTo: from * 2.2, duration: 0.12, delay, volume: 0.7 });
}

/** A run of rising blips (a bubble trail, a clone burst). */
export function bubbleRun(count: number, from = 0): void {
	for (let index = 0; index < count; index++)
		bubbleBlip(from + index, index * 0.07);
}
