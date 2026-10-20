import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { AdaptiveSupportActivity } from "../AdaptiveSupportActivity";
import type {
	AdditionAdventureSupportManifest,
	NumberWorldSupportManifest,
} from "../api/generated";

const chapters = [
	["number-world-support-v1", "place_value_harbour"],
	["number-world-support-v1", "firefly_abacus"],
	["number-world-support-v1", "kite_workshop"],
	["number-world-support-v1", "river_route_rally"],
	["addition-adventure-support-v1", "fruit_catch"],
	["addition-adventure-support-v1", "tuk_tuk_journey"],
	["addition-adventure-support-v1", "carrying_crane"],
	["addition-adventure-support-v1", "market_delivery_planner"],
	["addition-adventure-support-v1", "festival_data_detective"],
] as const;
const types = [
	"visual_guidance",
	"worked_parallel_example",
	"step_by_step_guidance",
] as const;

describe("adaptive support delivery matrix", () => {
	for (const [schema, chapter] of chapters) {
		for (const type of types) {
			it(`${chapter} visibly completes ${type}`, async () => {
				const host = document.createElement("div");
				document.body.append(host);
				const root = createRoot(host);
				const isNumberWorld = schema === "number-world-support-v1";
				const required =
					isNumberWorld || type === "step_by_step_guidance" ? 3 : 1;
				const manifest = {
					schema_version: schema,
					activity_id: chapter,
					revision_id: `${chapter}:support@v1`,
					deterministic_seed: 31,
					skill_id: "test-skill",
					scaffold_type: type,
					renderer_id: `${chapter}:${type}`,
					parallel_example_id: `${chapter}:parallel-v1`,
					parallel_example_version: "v1",
					parallel_values: [3, 4, 7],
					required_actions: required,
					worked_example: isNumberWorld
						? {
								mode: "exact_failed_activity",
								prompt_si: "52,014 හි 2 ඉලක්කමේ ස්ථානය කුමක්ද?",
								game: {
									schema_version: "number-world-item-v1",
									chapter,
									skill_id: "G5-MAT-NUM-POSITION-01",
									number: 52014,
									digit: 2,
									place: 3,
								},
								correct_response: { kind: "drag_to_slot", selected_place: 3 },
								steps_si: ["ඉලක්කම සොයමු.", "ස්ථානය ගණන් කරමු.", "පිළිතුර බලමු."],
							}
						: {
								mode: "exact_failed_activity",
								prompt_si: "කාණ්ඩ දෙක එකතු කරන්න.",
								game: {
									schema_version: "addition-adventure-item-v1",
									chapter,
									skill_id: "G5-MAT-ADD-MENTAL-01",
									addends: [3, 4],
									start: 82,
									stops: [27, 12],
									table: [[382, 728, 298]],
									row_labels: ["ජනවාරි"],
									column_labels: ["වම්බටු", "බණ්ඩක්කා", "මිරිස්"],
								},
								correct_response:
									type === "visual_guidance"
										? null
										: {
												kind: "combine_quantities",
												combined: true,
												total: 7,
											},
								steps_si: ["කාණ්ඩ බලමු.", "එකට ගෙන එමු.", "මුළු ගණන බලමු."],
							},
				} as NumberWorldSupportManifest | AdditionAdventureSupportManifest;
				const progress = vi.fn();
				await act(async () =>
					root.render(
						<AdaptiveSupportActivity
							manifest={manifest}
							onProgress={progress}
						/>,
					),
				);
				expect(
					host.querySelector(`[data-support-renderer="${chapter}:${type}"]`),
				).not.toBeNull();
				if (isNumberWorld) {
					expect(host.textContent).toContain("52,014 හි 2 ඉලක්කමේ ස්ථානය කුමක්ද?");
					expect(host.textContent).not.toContain("නිවැරදි ස්ථානය:");
				}
				if (!isNumberWorld)
					expect(host.textContent).toContain("කාණ්ඩ දෙක එකතු කරන්න.");
				const button = host.querySelector("button");
				if (!button) throw new Error("support action missing");
				for (let index = 0; index < required; index += 1) {
					await act(async () => button.click());
				}
				expect(progress).toHaveBeenLastCalledWith(required, true);
				if (isNumberWorld && type === "visual_guidance") {
					expect(host.textContent).not.toContain("නිවැරදි ස්ථානය:");
					expect(
						host.querySelector(".worked-number .is-target"),
					).not.toBeNull();
				} else if (isNumberWorld) {
					expect(host.textContent).toContain("නිවැරදි ස්ථානය: දහස්");
				}
				await act(async () => root.unmount());
				host.remove();
			});
		}
	}

	it("shows carrying in aligned named columns with carries above their destination", async () => {
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);
		const manifest: AdditionAdventureSupportManifest = {
			schema_version: "addition-adventure-support-v1",
			activity_id: "carrying_crane",
			revision_id: "carry-support@v1",
			deterministic_seed: 9,
			skill_id: "G5-MAT-C06-L01-O01",
			scaffold_type: "worked_parallel_example",
			renderer_id: "carrying_crane:worked_parallel_example",
			parallel_example_id: "carry:exact-v1",
			parallel_example_version: "v1",
			parallel_values: [],
			required_actions: 3,
			worked_example: {
				mode: "exact_failed_activity",
				prompt_si: "5951 + 7371 නිවැරදිව එකතු කරන්න.",
				game: {
					schema_version: "addition-adventure-item-v1",
					chapter: "carrying_crane",
					skill_id: "G5-MAT-C06-L01-O01",
					addends: [5951, 7371],
				},
				correct_response: {
					kind: "regroup_carry",
					total: 13322,
					carry_count: 2,
					aligned: true,
				},
				steps_si: ["එකක තීරුව බලමු.", "ගෙනයාම තබමු.", "එකතුව ලියමු."],
			},
		};

		await act(async () =>
			root.render(
				<AdaptiveSupportActivity
					manifest={manifest}
					onProgress={() => undefined}
				/>,
			),
		);
		const button = host.querySelector<HTMLButtonElement>(
			".scaffold-practice > button",
		);
		if (!button) throw new Error("support action missing");
		for (let index = 0; index < 3; index += 1)
			await act(async () => button.click());

		expect(host.textContent).toContain("දස දහස්");
		expect(host.textContent).toContain("ගෙනයාම");
		expect(host.textContent).toContain("5,951 + 7,371 = 13,322");
		expect(host.querySelectorAll(".worked-sum-row td")).toHaveLength(5);

		await act(async () => root.unmount());
		host.remove();
	});

	it("chains each running total into the next addition step", async () => {
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);
		const manifest: AdditionAdventureSupportManifest = {
			schema_version: "addition-adventure-support-v1",
			activity_id: "tuk_tuk_journey",
			revision_id: "route-support@v1",
			deterministic_seed: 10,
			skill_id: "G5-MAT-ADD-RUNNING-TOTAL-01",
			scaffold_type: "worked_parallel_example",
			renderer_id: "tuk_tuk_journey:worked_parallel_example",
			parallel_example_id: "route:exact-v1",
			parallel_example_version: "v1",
			parallel_values: [],
			required_actions: 3,
			worked_example: {
				mode: "exact_failed_activity",
				prompt_si: "102 සිට එකතු කිරීමේ මාර්ගය ගොඩනඟන්න.",
				game: {
					schema_version: "addition-adventure-item-v1",
					chapter: "tuk_tuk_journey",
					skill_id: "G5-MAT-ADD-RUNNING-TOTAL-01",
					start: 102,
					stops: [29, 14, 22],
				},
				correct_response: {
					kind: "route_progression",
					totals: [131, 145, 167],
				},
				steps_si: ["ආරම්භය බලමු.", "පිළිතුර ඉදිරියට ගෙන යමු.", "මාර්ගය සම්පූර්ණ කරමු."],
			},
		};

		await act(async () =>
			root.render(
				<AdaptiveSupportActivity
					manifest={manifest}
					onProgress={() => undefined}
				/>,
			),
		);
		const button = host.querySelector<HTMLButtonElement>(
			".scaffold-practice > button",
		);
		if (!button) throw new Error("support action missing");
		await act(async () => button.click());
		expect(host.textContent).toContain("102 + 29 = 131");
		await act(async () => button.click());
		expect(host.textContent).toContain("131 + 14 = 145");
		await act(async () => button.click());
		expect(
			host.querySelectorAll(".worked-addition-route .is-complete"),
		).toHaveLength(3);
		expect(host.textContent).toContain("145");
		expect(host.textContent).toContain("167");

		await act(async () => root.unmount());
		host.remove();
	});
});
