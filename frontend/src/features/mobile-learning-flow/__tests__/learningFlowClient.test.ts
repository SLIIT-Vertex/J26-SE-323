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
		missions: Array.from({ length: 55 }, (_, index) => mission(index)),
		...extra,
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

		expect(listed.missions).toHaveLength(55);
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
				jsonResponse([
					{ id: compatible, grade: 5, preferred_language: "si" },
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
				allow_draft: true,
			},
			"open-key",
		);

		const open = request.mock.calls[1];
		if (!open) throw new Error("learning-flow open missing");
		const openInit = open[1];
		if (!openInit) throw new Error("learning-flow open options missing");
		expect(String(open[0])).toBe(`${baseUrl}/development/learning-flow/episodes`);
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
				allow_draft: true,
			},
			"open-key",
		);

		const openInit = request.mock.calls[1]?.[1];
		if (!openInit) throw new Error("learning-flow open options missing");
		expect((openInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			configured,
		);
	});

	it("recovers from an already exposed probe with a fresh development learner", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const fresh = "00000000-0000-4000-8000-000000000799";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([
					{ id: configured, grade: 5, preferred_language: "si" },
				]),
			)
			.mockResolvedValueOnce(
				jsonResponse(
					{ detail: { code: "PROBE_ALREADY_RESERVED_OR_EXPOSED" } },
					409,
				),
			)
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
				allow_draft: true,
			},
			"open-key",
		);

		const retryInit = request.mock.calls[3]?.[1];
		if (!retryInit) throw new Error("learning-flow retry options missing");
		expect((retryInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			fresh,
		);
		expect(JSON.parse(String(retryInit.body))).toMatchObject({
			learner_id: fresh,
		});
	});

	it("avoids an episode conflict by selecting a learner with an unused skill probe", async () => {
		const configured = "00000000-0000-4000-8000-000000000721";
		const available = "00000000-0000-4000-8000-000000000722";
		const request = vi
			.fn()
			.mockResolvedValueOnce(
				jsonResponse([
					{ id: configured, grade: 5, preferred_language: "si" },
					{ id: available, grade: 5, preferred_language: "si" },
				]),
			)
			.mockResolvedValueOnce(jsonResponse({ available: false }))
			.mockResolvedValueOnce(jsonResponse({ available: true }))
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
				allow_draft: true,
				area_id: "G5-AREA-MAT-01",
				atomic_skill_id: "G5-MAT-NUM-POSITION-01",
			},
			"open-key",
		);

		const openCalls = request.mock.calls.filter(([input]) =>
			String(input).endsWith("/development/learning-flow/episodes"),
		);
		expect(openCalls).toHaveLength(1);
		const openInit = openCalls[0]?.[1];
		if (!openInit) throw new Error("learning-flow open options missing");
		expect((openInit.headers as Record<string, string>)["X-Learner-Id"]).toBe(
			available,
		);
	});
});
