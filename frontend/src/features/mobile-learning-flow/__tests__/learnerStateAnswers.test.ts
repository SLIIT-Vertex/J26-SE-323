import { describe, expect, it, vi } from "vitest";
import type { VisualFeatureWindow } from "../api/generated";
import { createLearningFlowClient } from "../api/learningFlowClient";

const baseUrl = "http://example.test/api/v1";
const CONFIGURED = "00000000-0000-4000-8000-000000000721";
const CREATED = "00000000-0000-4000-8000-000000000799";
const EPISODE = {
	episode_id: "episode",
	status: "before_presented",
	manifest: null,
	support: null,
	reward: null,
};
const VISUAL: VisualFeatureWindow = {
	mean_eye_openness: 0.3,
	std_eye_openness: 0.05,
	mean_gaze_ratio: 0.5,
	std_gaze_ratio: 0.04,
	mean_pitch: 2,
	mean_yaw: -3,
	mean_roll: 1,
	mean_abs_pitch: 4,
	mean_abs_yaw: 5,
	mean_abs_roll: 2,
	face_visibility_ratio: 0.9,
};

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { "Content-Type": "application/json" },
	});
}

/** A small fake backend that records every request. */
function fakeServer({ probeTaken = false } = {}) {
	const learners = [{ id: CONFIGURED, grade: 5, preferred_language: "si" }];
	const consents = new Map<string, boolean>();
	let episodesOpened = 0;
	const calls: { url: string; method: string; learner?: string; body?: unknown }[] = [];
	const request = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = String(input).replace(baseUrl, "");
		const method = init?.method ?? "GET";
		const learner = (init?.headers as Record<string, string> | undefined)?.["X-Learner-Id"];
		const body = init?.body ? JSON.parse(String(init.body)) : undefined;
		calls.push({ url, method, learner, body });
		if (url === "/learners" && method === "GET") return json(learners);
		if (url === "/learners" && method === "POST") {
			learners.push({ id: CREATED, grade: 5, preferred_language: "si" });
			return json({ id: CREATED });
		}
		if (url.endsWith("/consents/learner-state-camera")) {
			if (method === "PUT") consents.set(String(learner), body.granted);
			const granted = consents.get(String(learner)) ?? false;
			return json({ granted, decided_at: granted ? "2026-10-20T09:00:00Z" : null });
		}
		if (url.endsWith("/episodes")) {
			episodesOpened += 1;
			if (probeTaken && episodesOpened === 1) {
				return json({ detail: { code: "PROBE_ALREADY_RESERVED_OR_EXPOSED" } }, 409);
			}
			return json(EPISODE);
		}
		return json(EPISODE);
	});
	return { request, calls, consents };
}

const OPEN = {
	learner_id: CONFIGURED,
	session_id: "session",
	grade: 5 as const,
	medium: "si" as const,
	condition: "baseline" as const,
	environment: "development" as const,
	allow_draft: true as const,
};

describe("learner-state evidence on adventure answers", () => {
	it("attaches one camera snapshot per answer and the app's learner-state session", async () => {
		const server = fakeServer();
		const visualFeatures = vi.fn(() => VISUAL);
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: CONFIGURED,
			request: server.request,
			visualFeatures,
			learnerStateSessionId: "app-session",
		});

		await client.answerBefore("episode", { option_id: "a" }, "key-1");
		await client.answerBefore("episode", { option_id: "a" }, "key-1");
		await client.answerAfter("episode", { option_id: "b" }, "key-2");

		const answers = server.calls.filter((call) => call.method === "POST");
		expect(answers.map((call) => call.body)).toEqual([
			{ option_id: "a", learner_state_session_id: "app-session", visual: VISUAL },
			{ option_id: "a", learner_state_session_id: "app-session", visual: VISUAL },
			{ option_id: "b", learner_state_session_id: "app-session", visual: VISUAL },
		]);
		// A retried request with the same key re-sends the first snapshot.
		expect(visualFeatures).toHaveBeenCalledTimes(2);
	});

	it("sends no camera values without a camera window", async () => {
		const server = fakeServer();
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: CONFIGURED,
			request: server.request,
			visualFeatures: () => null,
		});

		await client.answerBefore("episode", { option_id: "a" }, "key");

		const body = server.calls.find((call) => call.method === "POST")?.body;
		expect(body).toHaveProperty("learner_state_session_id");
		expect(body).not.toHaveProperty("visual");
	});

	it("reads and records the guardian's camera decision", async () => {
		const server = fakeServer();
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: CONFIGURED,
			request: server.request,
		});

		expect(await client.cameraConsent()).toBe(false);
		expect(await client.setCameraConsent(true)).toBe(true);
		expect(await client.cameraConsent()).toBe(true);
		expect(server.consents.get(CONFIGURED)).toBe(true);
	});

	it("re-records consent when development recovery switches the learner", async () => {
		const server = fakeServer({ probeTaken: true });
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: CONFIGURED,
			request: server.request,
		});

		await client.setCameraConsent(true);
		await client.open(OPEN, "open-key");

		expect(server.consents.get(CREATED)).toBe(true);
	});

	it("does not grant consent to a new learner when the guardian declined", async () => {
		const server = fakeServer({ probeTaken: true });
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: CONFIGURED,
			request: server.request,
		});

		await client.setCameraConsent(false);
		await client.open(OPEN, "open-key");

		expect(server.consents.has(CREATED)).toBe(false);
	});
});
