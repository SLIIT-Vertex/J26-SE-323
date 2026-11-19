import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../orientation", () => ({ lockOrientation: vi.fn(async () => true) }));

type Started = { url: string; rate: number; volume: number; at: number };

/** A fake Web Audio engine that records every sound started. */
function installFakeAudio() {
	const started: Started[] = [];
	class FakeContext {
		state = "running";
		currentTime = 10;
		destination = {};
		resume = vi.fn(async () => undefined);
		decodeAudioData = vi.fn(async (data: ArrayBuffer) => ({
			url: new TextDecoder().decode(data),
		}));
		createGain() {
			return { gain: { value: 1 }, connect: (target: unknown) => target };
		}
		createBufferSource() {
			const source = {
				buffer: null as { url: string } | null,
				playbackRate: { value: 1 },
				gain: 1,
				connect: (gain: { gain: { value: number } }) => {
					source.gain = gain.gain.value;
					return gain;
				},
				start: (at: number) =>
					started.push({
						url: source.buffer?.url ?? "",
						rate: source.playbackRate.value,
						volume: source.gain,
						at,
					}),
			};
			return source;
		}
	}
	vi.stubGlobal("AudioContext", FakeContext);
	vi.stubGlobal(
		"fetch",
		vi.fn(async (url: string) => ({
			ok: true,
			arrayBuffer: async () => new TextEncoder().encode(url).buffer,
		})),
	);
	return started;
}

async function freshModule() {
	vi.resetModules();
	return import("../gameAudio");
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("game audio", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		localStorage.clear();
	});

	it("plays a random variation with a small pitch wobble, or an exact pitch when steady", async () => {
		const started = installFakeAudio();
		const { createGameAudio } = await freshModule();
		const audio = createGameAudio("/sounds", { crate: 3, jingle: 1 });
		audio.play("crate", { volume: 0.5, delay: 0.25 });
		audio.play("jingle", { steady: true, rate: 1.3 });
		await flush();
		await flush();
		const crate = started.find((row) => row.url.startsWith("/sounds/crate-"));
		expect(crate?.url).toMatch(/^\/sounds\/crate-[123]\.m4a$/);
		expect(crate?.volume).toBe(0.5);
		expect(crate?.at).toBe(10.25);
		expect(crate?.rate).toBeGreaterThanOrEqual(0.96);
		expect(crate?.rate).toBeLessThanOrEqual(1.04);
		const jingle = started.find((row) => row.url === "/sounds/jingle.m4a");
		expect(jingle?.rate).toBeCloseTo(1.3);
	});

	it("stays silent while muted and remembers the choice", async () => {
		const started = installFakeAudio();
		const audio = await freshModule();
		audio.setGameSoundMuted(true);
		expect(localStorage.getItem("mindbridge.game-sound-muted")).toBe("1");
		audio.createGameAudio("/sounds", { tap: 1 }).play("tap");
		await flush();
		expect(started).toHaveLength(0);
		const reloaded = await freshModule();
		expect(reloaded.isGameSoundMuted()).toBe(true);
	});

	it("does nothing without Web Audio", async () => {
		vi.stubGlobal("AudioContext", undefined);
		const { createGameAudio } = await freshModule();
		expect(() =>
			createGameAudio("/sounds", { tap: 1 }).play("tap"),
		).not.toThrow();
	});

	it("lets the child switch the sound off and on from the game stage", async () => {
		installFakeAudio();
		vi.resetModules();
		const { LandscapeGameStage } = await import("../LandscapeGameStage");
		const audio = await import("../gameAudio");
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<LandscapeGameStage label="game" onBack={() => undefined}>
					<p>board</p>
				</LandscapeGameStage>,
			),
		);
		const button = host.querySelector<HTMLButtonElement>(
			".landscape-sound-button",
		);
		expect(button?.getAttribute("aria-label")).toBe("ශබ්දය නවත්වන්න");
		await act(async () => button?.click());
		expect(audio.isGameSoundMuted()).toBe(true);
		expect(button?.getAttribute("aria-pressed")).toBe("true");
		expect(button?.getAttribute("aria-label")).toBe("ශබ්දය දාන්න");
		await act(async () => button?.click());
		expect(audio.isGameSoundMuted()).toBe(false);
		await act(async () => root.unmount());
		host.remove();
	});
});
