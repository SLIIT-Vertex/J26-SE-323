import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NimoVillageWalk } from "../NimoVillageWalk";
import { TikkiGarden } from "../TikkiGarden";
import { readTask } from "../villageRules";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const ROAD = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-LENGTH-ADD-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "ගෙදර සිට කඩේට 3 km 650 m, කඩේ සිට පොළට 2 km 475 m.",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "distance-adventure-item-v1",
		chapter: "market_road",
		response_kind: "distance_arithmetic",
		operation: "add",
		left_kilometres: 3,
		left_metres: 650,
		right_kilometres: 2,
		right_metres: 475,
	},
};
const AFTER = {
	...ROAD,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-LENGTH-ADD-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
	game: {
		...ROAD.game,
		left_metres: 725,
		right_kilometres: 1,
		right_metres: 390,
	},
};
const TOY_ROUND = {
	scaffold_id: "s1",
	revision_id: "support-1",
	scaffold_type: "step_by_step_guidance",
	title_si: "",
	body_si: [],
	visual_alt_text_si: null,
	maximum_steps: 3,
	game_manifest: {
		schema_version: "support-round-v1",
		activity_id: "a1",
		revision_id: "support-manifest-1",
		deterministic_seed: 1,
		skill_id: "G5-MAT-LENGTH-SUBTRACT-01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "distance",
		parallel_example_id: "p1",
		parallel_example_version: "v1",
		parallel_values: [],
		required_actions: 1,
		round_number: 1,
		stage_index: 0,
		stage_count: 1,
		stage_kind: "target",
		cues_si: [],
		lesson: null,
		activity: {
			presentation_id: "00000000-0000-4000-8000-0000000000c1",
			revision_id: "toy-1",
			skill_id: "G5-MAT-LENGTH-SUBTRACT-01",
			prompt_si: "toy",
			game: {
				...ROAD.game,
				operation: "subtract",
				left_kilometres: 21,
				left_metres: 410,
				right_kilometres: 8,
				right_metres: 500,
			},
			returns_to_failed_item: true,
		},
		worked_example: null,
	},
};

function byLabel(host: HTMLElement, label: string) {
	const element = host.querySelector<HTMLButtonElement>(
		`[aria-label="${label}"]`,
	);
	if (!element) throw new Error(`missing ${label}`);
	return element;
}

const byStart = (host: HTMLElement, text: string) => {
	const element = [...host.querySelectorAll("button")].find((button) =>
		button.textContent?.trim().startsWith(text),
	);
	if (!element) throw new Error(`missing ${text}`);
	return element;
};

async function tap(element: HTMLElement, times = 1) {
	for (let step = 0; step < times; step++)
		await act(async () => element.click());
}

describe("Nimo's Village Walk", () => {
	let host: HTMLDivElement;
	let root: Root;

	beforeEach(() => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
		vi.useRealTimers();
		vi.restoreAllMocks();
		vi.clearAllMocks();
	});

	it("builds the market road, sums it metres first, then mends a toy road after a muddle", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: ROAD,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: TOY_ROUND,
				server_score: {
					correct: false,
					presentation_id: ROAD.presentation_id,
					item_revision_id: ROAD.revision_id,
				},
			})),
			answerSupported: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support_round: {
					withdrawal_allowed: true,
					support_revision_id: "support-1",
					manifest_revision_id: "support-manifest-1",
				},
			})),
			completeSupport: vi.fn(),
			withdrawSupport: vi.fn(async () => ({
				episode_id: "e1",
				status: "withdrawn",
			})),
			presentAfter: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: AFTER,
			})),
			answerAfter: vi.fn(),
		};
		await act(async () => {
			root.render(
				<NimoVillageWalk
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byStart(host, "පොළට යමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-09",
				atomic_skill_id: "G5-MAT-LENGTH-ADD-01",
			}),
			expect.any(String),
		);
		expect(host.querySelector(".market-walk")).toBeNull();
		await tap(byLabel(host, "පාර කෑල්ල 3 km 650 m"));
		await tap(byLabel(host, "පාර කෑල්ල 2 km 475 m"));
		expect(host.querySelectorAll(".road-slot[data-filled]")).toHaveLength(2);
		// A muddle: the metres are added (1125) but the kilometre is never carried.
		await tap(byLabel(host, "m 1 වැඩි කරන්න"));
		await tap(byLabel(host, "m 2 වැඩි කරන්න"));
		await tap(byLabel(host, "m 3 වැඩි කරන්න"), 2);
		await tap(byLabel(host, "m 4 වැඩි කරන්න"), 5);
		await tap(byLabel(host, "km 2 වැඩි කරන්න"), 5);
		await tap(byStart(host, "🚶"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "distance_arithmetic",
			metre_subtotal_or_adjustment: 1125,
			exchange_or_regrouping_used: false,
			result_kilometres: 5,
			result_metres: 1125,
		});
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"attempt_count",
			"correction_count",
			"first_action_ms",
			"move_count",
		]);

		await act(async () => vi.advanceTimersByTime(2000));
		await tap(byStart(host, "යමු!"));
		expect(
			host.querySelector("[data-training-place='toy-road']"),
		).not.toBeNull();
		// 21 km 410 m − 8 km 500 m: the 100 m blocks run short, so a kilometre is opened.
		await tap(byLabel(host, "අයින් කරන්න 1 km (8)"));
		for (let step = 0; step < 7; step++)
			await tap(byLabel(host, `අයින් කරන්න 1 km (${7 - step})`));
		for (let step = 0; step < 4; step++)
			await tap(byLabel(host, `අයින් කරන්න 100 m (${5 - step})`));
		await tap(byLabel(host, "අයින් කරන්න 100 m (1)"));
		expect(host.querySelector(".village-message")?.textContent).toContain(
			"මීටර් මදිද",
		);
		await tap(byStart(host, "🔁"));
		await tap(byLabel(host, "අයින් කරන්න 100 m (1)"));
		expect(host.querySelector(".toy-road[data-done]")).not.toBeNull();
		expect(host.querySelector(".toy-total")?.textContent).toBe("= 12 km 910 m");
		await tap(byStart(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					exchange_or_regrouping_used: true,
					result_kilometres: 12,
					result_metres: 910,
				}),
			}),
			expect.any(String),
		);
		await tap(byStart(host, "පොළ පාරට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(host.querySelector(".village-scroll")?.textContent).toContain(
			"අලුත් ගමනක්",
		);
	});
});

describe("Tikki's garden", () => {
	let host: HTMLDivElement;
	let root: Root;

	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
	});

	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
		vi.clearAllMocks();
	});

	it("builds 2200 m from 100 m pieces and swaps ten of them for 1 km", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "distance_conversion",
			source_value: 2200,
		});
		await act(async () =>
			root.render(
				<TikkiGarden task={task} evidence={evidence} onResponse={onResponse} />,
			),
		);
		await tap(byLabel(host, "1 km කෑල්ලක් එකතු කරන්න"));
		await tap(byLabel(host, "100 m කෑල්ලක් එකතු කරන්න"), 11);
		expect(onResponse).toHaveBeenLastCalledWith(null);
		await tap(byStart(host, "🔁"));
		await tap(byLabel(host, "100 m කෑල්ලක් එකතු කරන්න"), 1);
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "distance_conversion",
			source_value: 2200,
			source_unit: "m",
			kilometres: 2,
			metres: 200,
			total_metres: 2200,
			formal_metres: "200",
		});
	});

	it("measures 100 cm with the tape and 1000 m to Tikki's flag", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<TikkiGarden
					task={readTask({ response_kind: "unit_relationship" })}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		await tap(byStart(host, "පටිය ඇදමු"), 10);
		expect(host.querySelector(".tape-reading")?.textContent).toBe("100 cm");
		await tap(byStart(host, "✓"));
		await tap(byStart(host, "➕ 100 m"), 10);
		await tap(byStart(host, "✓"));
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				conversion_factor: 1000,
				placements: ["1 km", "1000 m", "1 m", "100 cm"],
			}),
		);
	});
});
