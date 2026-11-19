import {
	createGameAudio,
	noteFrequency,
	playTone,
} from "../../../mobile-learning-flow/landscape/gameAudio";

/** Every recorded sound of Nimo's Midnight Monster Café, with its number of variation files. */
export const cafeSounds = createGameAudio(
	"/curriculum/game/G5-AREA-MAT-04/audio",
	{
		tap: 1,
		pick: 2,
		digit: 2,
		chomp: 3,
		unwrap: 2,
		burst: 1,
		shelf: 3,
		boing: 2,
		back: 1,
		puzzled: 1,
		hmm: 1,
		sparkle: 1,
		"jingle-order": 1,
		"jingle-victory": 1,
		"jingle-train": 1,
		"jingle-return": 1,
		"jingle-rest": 1,
	},
);

/** A bite that climbs a note each time, so a run of snacks sounds like a little tune. */
export function biteNote(count: number): void {
	playTone(noteFrequency(count % 12), { duration: 0.18, volume: 0.6 });
}

/** A pack bursting open into ten: a quick rising sparkle. */
export function burstSparkle(): void {
	for (let step = 0; step < 5; step++)
		playTone(noteFrequency(7 + step * 2), {
			delay: step * 0.05,
			duration: 0.14,
			volume: 0.5,
		});
}
