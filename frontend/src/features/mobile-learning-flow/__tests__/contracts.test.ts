import { describe, expect, it } from "vitest";
import { parseChildEpisodeResponse } from "../api/runtime";

const safe = {
	episode_id: "00000000-0000-4000-8000-000000000001",
	status: "completed",
	manifest: null,
	support: null,
	reward: { points: 1, reason: "episode_complete" },
};

describe("child contract", () => {
	it("accepts the strict child-safe response", () =>
		expect(parseChildEpisodeResponse(safe)).toEqual(safe));
	it.each([
		"correct_option_id",
		"raw_independence_gain",
		"policy_update_status",
		"probabilities",
		"exclusion_reasons",
	])("rejects private field %s", (field) => {
		expect(() =>
			parseChildEpisodeResponse({ ...safe, [field]: "forbidden" }),
		).toThrow("RESEARCH_FIELD_EXPOSURE");
	});

	it("rejects an unsupported item while assistance is active", () => {
		expect(() =>
			parseChildEpisodeResponse({
				...safe,
				manifest: {
					presentation_id: "presentation",
					revision_id: "revision@v1",
					measurement_role: "unsupported_after",
					assistance_state: "active",
					prompt_si: "ප්‍රශ්නය",
					accessibility_label_si: "ප්‍රශ්නය කියවන්න",
					options: [
						{ option_id: "A", text_si: "1" },
						{ option_id: "B", text_si: "2" },
					],
					content_version: "v1",
				},
			}),
		).toThrow("UNSUPPORTED_ASSISTANCE_ACTIVE");
	});

	it("rejects an incompatible or malformed game manifest", () => {
		expect(() =>
			parseChildEpisodeResponse({
				...safe,
				support: {
					scaffold_id: "visual",
					revision_id: "scaffold@v1",
					scaffold_type: "visual_guidance",
					title_si: "උදව්",
					body_si: ["පියවර"],
					visual_alt_text_si: "දෘශ්‍ය විස්තරය",
					maximum_steps: 1,
					game_manifest: {
						schema_version: "half-set-manifest-v0",
						activity_id: "half",
						revision_id: "scaffold@v1",
						deterministic_seed: 31,
						total_objects: 5,
						group_count: 3,
						object_label_si: "ද්‍රව්‍යය",
						instruction_si: "කාණ්ඩ කරන්න",
					},
				},
			}),
		).toThrow("STALE_OR_INCOMPATIBLE_MANIFEST");
	});
});
