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
