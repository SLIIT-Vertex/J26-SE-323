import { describe, expect, it, vi } from "vitest";
import type { DraftMissionRecord, DraftTemplateId } from "../api/generated";
import {
	createDraftMissionCatalogClient,
	LearningFlowApiError,
} from "../api/learningFlowClient";
import { ContractError } from "../api/runtime";

const baseUrl = "http://example.test/api/v1";

function mission(index: number): DraftMissionRecord {
	const templateId: DraftTemplateId = "market_mission";
	return {
		area_id: `G5-AREA-MAT-${String(index + 1).padStart(2, "0")}`,
		cited_node_id: "G5-MAT-C01",
		template_id: templateId,
		development_only: true,
		publication_status: "blocked",
		outcome_slots: [
			{
				node_id: "G5-MAT-C01-L01-O01",
				parent_area_id: "G5-AREA-MAT-01",
				trace_competency_id: "G5-MAT-C01",
				supplied_area_match: true,
				confidence: "medium",
				draft_item: true,
				publication_status: "blocked",
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
				publication_status: "blocked",
				traced_text: "traced string",
				child_question: null,
			},
		],
	};
}

function catalog(extra: Record<string, unknown> = {}) {
	return {
		package_version: "grade5-draft-mission-catalog-v1",
		development_only: true,
		publication_status: "blocked",
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
	it("does not request the catalog when the draft flag is off", async () => {
		const request = vi.fn();
		const client = createDraftMissionCatalogClient({
			baseUrl,
			allowDraft: false,
			request,
		});

		await expect(client.listDraftMissions()).rejects.toBeInstanceOf(
			LearningFlowApiError,
		);
		await expect(client.fetchDraftMission("G5-AREA-MAT-05")).rejects.toMatchObject(
			{ code: "DRAFT_CATALOG_BLOCKED" },
		);
		expect(request).not.toHaveBeenCalled();
	});

	it("lists and fetches only when the draft flag is on", async () => {
		const request = vi.fn(async (input: RequestInfo | URL) => {
			const url = String(input);
			if (url.endsWith("/draft-missions?allow_draft=true")) {
				return jsonResponse(catalog());
			}
			return jsonResponse(mission(4));
		});
		const client = createDraftMissionCatalogClient({
			baseUrl,
			allowDraft: true,
			request,
		});

		const listed = await client.listDraftMissions();
		const fetched = await client.fetchDraftMission("G5-AREA-MAT-05");

		expect(listed.missions).toHaveLength(55);
		expect(listed.publication_status).toBe("blocked");
		expect(fetched.area_id).toBe("G5-AREA-MAT-05");
		expect(fetched.held_slots[0]?.child_question).toBeNull();
		expect(request).toHaveBeenNthCalledWith(
			1,
			`${baseUrl}/development/learning-flow/draft-missions?allow_draft=true`,
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
			`${baseUrl}/development/learning-flow/draft-missions/G5-AREA-MAT-05?allow_draft=true`,
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
			allowDraft: true,
			request,
		});

		await expect(client.listDraftMissions()).rejects.toBeInstanceOf(ContractError);
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
			allowDraft: true,
			request,
		});

		await expect(client.fetchDraftMission("G5-AREA-MAT-01")).rejects.toMatchObject({
			code: "ANSWER_KEY_EXPOSURE",
		});
	});
});
