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

	it("accepts exact-question Money Adventure support", () => {
		const response = parseChildEpisodeResponse({
			...safe,
			support: {
				scaffold_id: "money-worked-example",
				revision_id: "money-worked-example@v1",
				scaffold_type: "worked_parallel_example",
				title_si: "මෙම ප්‍රශ්නය පියවරෙන් බලමු",
				body_si: ["මුලින් සත තීරුව ගණනය කරන්න."],
				visual_alt_text_si: "රුපියල් සහ සත තීරු දෙකක්",
				maximum_steps: 4,
				game_manifest: {
					schema_version: "money-adventure-support-v1",
					activity_id: "money-add-carry",
					revision_id: "money-worked-example@v1",
					deterministic_seed: 31,
					skill_id: "MAT-MON-ADD",
					scaffold_type: "worked_parallel_example",
					renderer_id: "money-working-table",
					parallel_example_id: "exact-money-add-carry",
					parallel_example_version: "v1",
					parallel_values: [16575, 24250],
					required_actions: 4,
					focus_step_index: 1,
					focus_column: "cents",
					worked_example: {
						mode: "exact_failed_activity",
						prompt_si: "රු. 165.75 + රු. 242.50 සොයන්න.",
						game: {
							schema_version: "money-adventure-item-v1",
							chapter: "money_calculation",
							response_kind: "money_arithmetic",
							operation: "add",
							left_amount_in_cents: 16575,
							right_amount_in_cents: 24250,
						},
						correct_response: {
							kind: "money_arithmetic",
							operation: "add",
							left_amount_in_cents: 16575,
							right_amount_in_cents: 24250,
							cent_subtotal_or_adjustment: 125,
							carried_or_borrowed_rupees: 1,
							exchange_used: true,
							working_steps: [
								"cents:75+50=125",
								"carry:1",
								"cents-result:25",
								"rupees:165+242+1=408",
							],
							result_in_cents: 40825,
							result_rupees: 408,
							result_cents: 25,
						},
						steps_si: ["සත එකතු කරන්න.", "සත 100 හුවමාරු කරන්න."],
					},
				},
			},
		});

		expect(response.support?.game_manifest).toMatchObject({
			schema_version: "money-adventure-support-v1",
			worked_example: {
				game: {
					response_kind: "money_arithmetic",
					operation: "add",
				},
			},
		});
	});

	it("accepts exact-question Capacity Adventure support", () => {
		const response = parseChildEpisodeResponse({
			...safe,
			support: {
				scaffold_id: "capacity-worked-example",
				revision_id: "capacity-worked-example@v1",
				scaffold_type: "worked_parallel_example",
				title_si: "මෙම ගැටලුව පියවරෙන් බලමු",
				body_si: ["ml තීරුව පළමුව විසඳන්න."],
				visual_alt_text_si: "ලීටර් සහ මිලිලීටර් තීරු",
				maximum_steps: 4,
				game_manifest: {
					schema_version: "capacity-adventure-support-v1",
					activity_id: "litre_machine",
					revision_id: "capacity-worked-example@v1",
					deterministic_seed: 41,
					skill_id: "G5-MAT-CAPACITY-ARITHMETIC-01",
					scaffold_type: "worked_parallel_example",
					renderer_id: "capacity-working-table",
					parallel_example_id: "exact-capacity-add",
					parallel_example_version: "v1",
					parallel_values: [8250, 4750],
					required_actions: 4,
					focus_column: "millilitres",
					worked_example: {
						mode: "exact_failed_activity",
						prompt_si: "8 l 250 ml සහ 4 l 750 ml එකතු කරන්න.",
						game: { schema_version: "capacity-adventure-item-v1", chapter: "litre_machine", response_kind: "capacity_arithmetic", operation: "add", left_litres: 8, left_millilitres: 250, right_litres: 4, right_millilitres: 750 },
						correct_response: { kind: "capacity_arithmetic", operation: "add", left_litres: 8, left_millilitres: 250, right_litres: 4, right_millilitres: 750, millilitre_subtotal_or_adjustment: 1000, carried_or_borrowed_litres: 1, exchange_used: true, working_steps: ["ml:250+750=1000", "carry:1", "ml-result:0", "litres:8+4+1=13"], result_litres: 13, result_millilitres: 0 },
						steps_si: ["ml එකතු කරන්න.", "1000 ml මාරු කරන්න."],
					},
				},
			},
		});
		expect(response.support?.game_manifest).toMatchObject({ schema_version: "capacity-adventure-support-v1", worked_example: { game: { response_kind: "capacity_arithmetic" } } });
	});

	it("accepts answer-safe Mass Adventure manifests and exact worked support", () => {
		const response = parseChildEpisodeResponse({
			...safe,
			manifest: { presentation_id: "mass-presentation", revision_id: "mass-item@v1", measurement_role: "unsupported_before", assistance_state: "none", prompt_si: "තරාදිය තෝරන්න.", accessibility_label_si: "තරාදිය තෝරන්න.", options: [], content_version: "v1", game: { schema_version: "mass-adventure-item-v1", chapter: "weighing_station", response_kind: "mass_instrument", object_id: "small-parcel", instrument_types: ["two_pan_balance", "spring_balance"] } },
			support: {
				scaffold_id: "mass-worked-example", revision_id: "mass-worked-example@v1", scaffold_type: "worked_parallel_example", title_si: "මෙම ගැටලුව පියවරෙන් බලමු", body_si: ["g තීරුව පළමුව විසඳන්න."], visual_alt_text_si: "කිලෝග්‍රෑම් සහ ග්‍රෑම් තීරු", maximum_steps: 4,
				game_manifest: {
					schema_version: "mass-adventure-support-v1", activity_id: "kilogram_machine", revision_id: "mass-worked-example@v1", deterministic_seed: 51, skill_id: "G5-MAT-MASS-ARITHMETIC-01", scaffold_type: "worked_parallel_example", renderer_id: "mass-working-table", parallel_example_id: "exact-mass-add", parallel_example_version: "v1", parallel_values: [8250, 7750], required_actions: 4, focus_column: "grams",
					worked_example: { mode: "exact_failed_activity", prompt_si: "8 kg 250 g සහ 7 kg 750 g එකතු කරන්න.", game: { schema_version: "mass-adventure-item-v1", chapter: "kilogram_machine", response_kind: "mass_arithmetic", operation: "add", left_kilograms: 8, left_grams: 250, right_kilograms: 7, right_grams: 750 }, correct_response: { kind: "mass_arithmetic", operation: "add", left_kilograms: 8, left_grams: 250, right_kilograms: 7, right_grams: 750, gram_subtotal_or_adjustment: 1000, carried_or_borrowed_kilograms: 1, exchange_used: true, working_steps: ["g:250+750=1000", "carry:1", "g-result:0", "kg:8+7+1=16"], result_kilograms: 16, result_grams: 0 }, steps_si: ["g එකතු කරන්න.", "1000 g මාරු කරන්න."] },
				},
			},
		});
		expect(response.manifest?.game).not.toHaveProperty("correct_instrument_type");
		expect(response.support?.game_manifest).toMatchObject({ schema_version: "mass-adventure-support-v1", focus_column: "grams", worked_example: { game: { response_kind: "mass_arithmetic" } } });
	});
});
