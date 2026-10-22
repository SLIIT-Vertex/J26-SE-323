import { describe, expect, it, vi } from "vitest";
import type { DraftMissionRecord, DraftTemplateId } from "../api/generated";
import {
	createDraftMissionCatalogClient,
	createLearningFlowClient,
} from "../api/learningFlowClient";
import { ContractError } from "../api/runtime";

const baseUrl = "http://example.test/api/v1";

function mission(index: number): DraftMissionRecord {
	const templateId: DraftTemplateId = "market_mission";
	return {
		area_id: `G5-AREA-MAT-${String(index + 1).padStart(2, "0")}`,
		cited_node_id: "G5-MAT-C01",
		template_id: templateId,
		outcome_slots: [
			{
				node_id: "G5-MAT-C01-L01-O01",
				parent_area_id: "G5-AREA-MAT-01",
				trace_competency_id: "G5-MAT-C01",
				supplied_area_match: true,
				confidence: "medium",
				draft_item: true,
				item_text: "traced sentence",
			},
		],
		draft_item_slots: [],
		held_slots: [
			{
				node_id: "G5-ENV-C01-L00-O01",
				parent_area_id: "G5-AREA-ENV-01",
				confidence: "low",
				held: true,
				draft_item: false,
				traced_text: "traced string",
				child_question: null,
			},
		],
	};
}

function catalog(extra: Record<string, unknown> = {}) {
	return {
		package_version: "grade5-draft-mission-catalog-v1",
		missions: Array.from({ length: 54 }, (_, index) => mission(index)),
		...extra,
	};
}

function clash(): Response {
	return jsonResponse(
		{ detail: { code: "PROBE_ALREADY_RESERVED_OR_EXPOSED" } },
		409,
	);
}

function opened(): Response {
	return jsonResponse({
		episode_id: "episode",
		status: "before_presented",
		manifest: null,
		support: null,
		reward: null,
	});
}

function openBody(learner: string) {
	return {
		learner_id: learner,
		session_id: "session",
		grade: 5 as const,
		medium: "si" as const,
		condition: "baseline" as const,
		environment: "development" as const,
		allow_draft: true as const,
		area_id: "G5-AREA-MAT-01",
		atomic_skill_id: "G5-MAT-NUM-POSITION-01",
	};
}

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { "Content-Type": "application/json" },
	});
}

describe("draft mission catalog client", () => {
	it("lists and fetches from the learning API", async () => {
		const request = vi.fn(async (input: RequestInfo | URL) => {
			const url = String(input);
			if (url.endsWith("/draft-missions")) {
				return jsonResponse(catalog());
			}
			return jsonResponse(mission(4));
		});
		const client = createDraftMissionCatalogClient({
			baseUrl,
			request,
		});

		const listed = await client.listDraftMissions();
		const fetched = await client.fetchDraftMission("G5-AREA-MAT-05");

		expect(listed.missions).toHaveLength(54);
		expect(fetched.area_id).toBe("G5-AREA-MAT-05");
		expect(fetched.held_slots[0]?.child_question).toBeNull();
		expect(request).toHaveBeenNthCalledWith(
			1,
			`${baseUrl}/learning-flow/draft-missions`,
			{
				method: "GET",
				headers: {
					"X-Dev-Principal": "NOT_FOR_PRODUCTION",
					"X-Dev-Role": "researcher",
				},
			},
		);
		expect(request).toHaveBeenNthCalledWith(
			2,
			`${baseUrl}/learning-flow/draft-missions/G5-AREA-MAT-05`,
			{
				method: "GET",
				headers: {
					"X-Dev-Principal": "NOT_FOR_PRODUCTION",
					"X-Dev-Role": "researcher",
				},
			},
		);
	});

	it.each([
		"correct_option_id",
		"accepted_response",
		"answer_key",
		"server_answer_keys",
	])("rejects a catalog payload containing %s", async (field) => {
		const request = vi.fn(async () =>
			jsonResponse(catalog({ [field]: "hidden" })),
		);
		const client = createDraftMissionCatalogClient({
			baseUrl,
			request,
		});

		await expect(client.listDraftMissions()).rejects.toBeInstanceOf(
			ContractError,
		);
		await expect(client.listDraftMissions()).rejects.toMatchObject({
			code: "ANSWER_KEY_EXPOSURE",
		});
	});

	it("rejects an answer key nested on one mission", async () => {
		const request = vi.fn(async () =>
			jsonResponse({ ...mission(0), correct_option_id: "A" }),
		);
		const client = createDraftMissionCatalogClient({
			baseUrl,
			request,
		});

		await expect(
			client.fetchDraftMission("G5-AREA-MAT-01"),
		).rejects.toMatchObject({
			code: "ANSWER_KEY_EXPOSURE",
		});
	});
});

describe("development learner recovery", () => {
	it("resolves a compatible learner before opening an episode", async () => {
		const compatible = "00000000-0000-4000-8000-000000000799";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([{ id: compatible, grade: 5, preferred_language: "si" }]),
			)
			.mockResolvedValueOnce(
				jsonResponse({
					episode_id: "episode",
					status: "before_presented",
					manifest: null,
					support: null,
					reward: null,
				}),
			);
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: "00000000-0000-4000-8000-000000000721",
			request,
		});

		await client.open(
			{
				learner_id: "00000000-0000-4000-8000-000000000721",
				session_id: "session",
				grade: 5,
				medium: "si",
				condition: "baseline",
				environment: "development",
				allow_draft: true as const,
			},
			"open-key",
		);

		const open = request.mock.calls[1];
		if (!open) throw new Error("learning-flow open missing");
		const openInit = open[1];
		if (!openInit) throw new Error("learning-flow open options missing");
		expect(String(open[0])).toBe(
			`${baseUrl}/development/learning-flow/episodes`,
		);
		expect((openInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			compatible,
		);
		expect(JSON.parse(String(openInit.body))).toMatchObject({
			learner_id: compatible,
		});
		expect(request).toHaveBeenCalledTimes(2);
	});

	it("keeps the configured learner when several compatible profiles exist", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([
					{
						id: "00000000-0000-4000-8000-000000000722",
						grade: 5,
						preferred_language: "si",
					},
					{ id: configured, grade: 5, preferred_language: "si" },
				]),
			)
			.mockResolvedValueOnce(
				jsonResponse({
					episode_id: "episode",
					status: "before_presented",
					manifest: null,
					support: null,
					reward: null,
				}),
			);
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: configured,
			request,
		});

		await client.open(
			{
				learner_id: configured,
				session_id: "session",
				grade: 5,
				medium: "si",
				condition: "baseline",
				environment: "development",
				allow_draft: true as const,
			},
			"open-key",
		);

		const openInit = request.mock.calls[1]?.[1];
		if (!openInit) throw new Error("learning-flow open options missing");
		expect((openInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			configured,
		);
	});

	it("falls back to a fresh development learner only after repeated probe clashes", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const fresh = "00000000-0000-4000-8000-000000000799";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([{ id: configured, grade: 5, preferred_language: "si" }]),
			)
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(
				jsonResponse({ id: fresh, grade: 5, preferred_language: "si" }, 201),
			)
			.mockResolvedValueOnce(
				jsonResponse({
					episode_id: "episode",
					status: "before_presented",
					manifest: null,
					support: null,
					reward: null,
				}),
			);
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: configured,
			request,
		});

		await client.open(
			{
				learner_id: configured,
				session_id: "session",
				grade: 5,
				medium: "si",
				condition: "baseline",
				environment: "development",
				allow_draft: true as const,
			},
			"open-key",
		);

		const retryInit = request.mock.calls[8]?.[1];
		if (!retryInit) throw new Error("learning-flow retry options missing");
		expect((retryInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			fresh,
		);
		expect(JSON.parse(String(retryInit.body))).toMatchObject({
			learner_id: fresh,
		});
	});

	it("returns to the configured learner for the next game after a fallback", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const fresh = "00000000-0000-4000-8000-000000000799";
		const listed = () =>
			jsonResponse([{ id: configured, grade: 5, preferred_language: "si" }]);
		const request = vi.fn().mockResolvedValueOnce(listed());
		for (let call = 0; call < 6; call += 1) request.mockResolvedValueOnce(clash());
		request
			.mockResolvedValueOnce(
				jsonResponse({ id: fresh, grade: 5, preferred_language: "si" }, 201),
			)
			.mockResolvedValueOnce(opened())
			.mockResolvedValueOnce(listed())
			.mockResolvedValueOnce(opened());
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: configured,
			request,
		});

		await client.open(openBody(configured), "first-game");
		await client.open(
			{
				...openBody(configured),
				area_id: "G5-AREA-ENG-01",
				atomic_skill_id: "G5-ENG-BEH-POSTURE-01",
			},
			"second-game",
		);

		const secondInit = request.mock.calls.at(-1)?.[1];
		if (!secondInit) throw new Error("second open options missing");
		expect((secondInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			configured,
		);
		expect(JSON.parse(String(secondInit.body)).learner_id).toBe(configured);
	});

	it("keeps the configured learner on a skill it has already played", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([
					{ id: configured, grade: 5, preferred_language: "si" },
					{
						id: "00000000-0000-4000-8000-000000000722",
						grade: 5,
						preferred_language: "si",
					},
				]),
			)
			.mockResolvedValueOnce(opened());
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: configured,
			request,
		});

		await client.open(openBody(configured), "open-key");

		expect(request).toHaveBeenCalledTimes(2);
		const openInit = request.mock.calls[1]?.[1];
		if (!openInit) throw new Error("learning-flow open options missing");
		expect((openInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			configured,
		);
	});

	it("retries a probe clash with a new session for the same learner", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([{ id: configured, grade: 5, preferred_language: "si" }]),
			)
			.mockResolvedValueOnce(clash())
			.mockResolvedValueOnce(opened());
		const client = createLearningFlowClient({
			baseUrl,
			learnerId: configured,
			request,
		});

		await client.open(openBody(configured), "open-key");

		const [first, retry] = request.mock.calls.slice(1).map(([, init]) => init);
		if (!first || !retry) throw new Error("open calls missing");
		const retryBody = JSON.parse(String(retry.body));
		expect(retryBody.learner_id).toBe(configured);
		expect(retryBody.session_id).not.toBe(
			JSON.parse(String(first.body)).session_id,
		);
		expect((retry.headers as Record<string, string>)["Idempotency-Key"]).toBe(
			"open-key:session-1",
		);
	});
});

it("saves the entered profile name for the configured learner", async () => {
	const learnerId = "00000000-0000-4000-8000-000000000721";
	const request = vi
		.fn()
		.mockResolvedValueOnce(
			jsonResponse([{ id: learnerId, grade: 5, preferred_language: "si" }]),
		)
		.mockResolvedValueOnce(jsonResponse({}));
	const client = createLearningFlowClient({ baseUrl, learnerId, request });
	await client.saveProfile("  Test Learner  ");
	expect(request.mock.calls[1]?.[0]).toBe(`${baseUrl}/learners/${learnerId}`);
	expect(request.mock.calls[1]?.[1]?.method).toBe("PATCH");
	expect(JSON.parse(String(request.mock.calls[1]?.[1]?.body))).toEqual({
		display_name: "Test Learner",
	});
});
