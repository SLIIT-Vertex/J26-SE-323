import { useSyncExternalStore } from "react";

/**
 * Sound effects for full-screen games. Sounds are decoded once with Web Audio so they start
 * instantly and can overlap. A sound may have variations (NAME-1.m4a, NAME-2.m4a, ...) picked at
 * random, with a slight pitch wobble so repeated sounds do not feel mechanical. Without Web Audio
 * (tests, very old browsers) every call is a silent no-op.
 */

const MUTE_KEY = "mindbridge.game-sound-muted";

let context: AudioContext | null | undefined;
let muted = readMuted();
const listeners = new Set<() => void>();
const buffers = new Map<string, Promise<AudioBuffer | null>>();

function readMuted(): boolean {
	try {
		return globalThis.localStorage?.getItem(MUTE_KEY) === "1";
	} catch {
		return false;
	}
}

function audioContext(): AudioContext | null {
	if (context !== undefined) return context;
	const Context =
		globalThis.AudioContext ??
		(globalThis as { webkitAudioContext?: typeof AudioContext })
			.webkitAudioContext;
	context = Context ? new Context() : null;
	return context;
}

function load(url: string): Promise<AudioBuffer | null> {
	const ready = audioContext();
	if (!ready) return Promise.resolve(null);
	let buffer = buffers.get(url);
	if (!buffer) {
		buffer = fetch(url)
			.then((response) =>
				response.ok ? response.arrayBuffer() : Promise.reject(),
			)
			.then((data) => ready.decodeAudioData(data))
			.catch(() => null);
		buffers.set(url, buffer);
	}
	return buffer;
}

export function isGameSoundMuted(): boolean {
	return muted;
}

export function setGameSoundMuted(next: boolean): void {
	muted = next;
	try {
		globalThis.localStorage?.setItem(MUTE_KEY, next ? "1" : "0");
	} catch {
		// Private browsing: the choice lasts until the app closes.
	}
	for (const listener of listeners) listener();
}

export function useGameSoundMuted(): boolean {
	return useSyncExternalStore(
		(listener) => {
			listeners.add(listener);
			return () => listeners.delete(listener);
		},
		isGameSoundMuted,
		isGameSoundMuted,
	);
}

/**
 * A short, soft musical note made in the browser (a toy xylophone). `frequency` is in hertz;
 * `noteFrequency(n)` gives the n-th note of a happy major scale starting at middle C.
 */
export function playTone(
	frequency: number,
	options: {
		duration?: number;
		delay?: number;
		volume?: number;
		/** Slide to this frequency over the note (a bubble blip, a slide whistle). */
		glideTo?: number;
	} = {},
): void {
	if (muted) return;
	const ready = audioContext();
	if (!ready) return;
	if (ready.state === "suspended") void ready.resume();
	const start = ready.currentTime + (options.delay ?? 0);
	const duration = options.duration ?? 0.35;
	const peak = 0.25 * (options.volume ?? 1);
	const gain = ready.createGain();
	gain.gain.setValueAtTime(0.0001, start);
	gain.gain.exponentialRampToValueAtTime(peak, start + 0.01);
	gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
	gain.connect(ready.destination);
	// A sine plus a quiet octave above gives a wooden, bell-like toy sound.
	for (const [multiple, level] of [
		[1, 1],
		[2, 0.3],
	] as const) {
		const oscillator = ready.createOscillator();
		oscillator.type = "sine";
		oscillator.frequency.setValueAtTime(frequency * multiple, start);
		if (options.glideTo)
			oscillator.frequency.exponentialRampToValueAtTime(
				options.glideTo * multiple,
				start + duration,
			);
		const partial = ready.createGain();
		partial.gain.value = level;
		oscillator.connect(partial).connect(gain);
		oscillator.start(start);
		oscillator.stop(start + duration + 0.05);
	}
}

const MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11];

/** The n-th note (0, 1, 2 …) of the C major scale from middle C, in hertz. */
export function noteFrequency(step: number): number {
	const octave = Math.floor(step / MAJOR_SCALE.length);
	const semitone = 12 * octave + (MAJOR_SCALE[((step % 7) + 7) % 7] ?? 0);
	return 261.63 * 2 ** (semitone / 12);
}

export type PlayOptions = {
	/** 0–1, default 1. */
	volume?: number;
	/** Seconds from now. */
	delay?: number;
	/** Keep the exact pitch (jingles); other sounds wobble slightly. */
	steady?: boolean;
	/** Playback speed and pitch, default 1 (e.g. 1.2 for a higher note). */
	rate?: number;
};

export type GameAudio<Name extends string> = {
	play(name: Name, options?: PlayOptions): void;
	preload(): void;
};

/** `sounds` maps each name to its number of variation files (1 = a single NAME.m4a). */
export function createGameAudio<Name extends string>(
	root: string,
	sounds: Record<Name, number>,
): GameAudio<Name> {
	const urls = (name: Name): string[] => {
		const count = sounds[name];
		return count > 1
			? Array.from(
					{ length: count },
					(_, at) => `${root}/${name}-${at + 1}.m4a`,
				)
			: [`${root}/${name}.m4a`];
	};
	return {
		preload() {
			for (const name of Object.keys(sounds) as Name[]) {
				for (const url of urls(name)) void load(url);
			}
		},
		play(name, options = {}) {
			if (muted) return;
			const ready = audioContext();
			if (!ready) return;
			if (ready.state === "suspended") void ready.resume();
			const choices = urls(name);
			const url =
				choices[Math.floor(Math.random() * choices.length)] ?? choices[0];
			if (!url) return;
			void load(url).then((buffer) => {
				if (!buffer || muted) return;
				const source = ready.createBufferSource();
				source.buffer = buffer;
				const wobble = options.steady ? 1 : 0.96 + Math.random() * 0.08;
				source.playbackRate.value = (options.rate ?? 1) * wobble;
				const gain = ready.createGain();
				gain.gain.value = options.volume ?? 1;
				source.connect(gain).connect(ready.destination);
				source.start(ready.currentTime + (options.delay ?? 0));
			});
		},
	};
}
