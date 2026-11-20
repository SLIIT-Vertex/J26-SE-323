import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NimoWaterDay } from "../NimoWaterDay";
import { WaterBalloons } from "../WaterBalloons";
import {
	ARITHMETIC_SKILL_ID,
	arithmeticResponse,
	fillResponse,
	missionOrder,
	readTask,
	solvedWorking,
} from "../waterRules";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const RACE = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-CAPACITY-ARITHMETIC-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "ටැංකි දෙකේ වතුර 8 l 250 mlයි, 4 l 750 mlයි. වතුර පාරට මුළු වතුර කීයද?",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "capacity-adventure-item-v1",
		chapter: "boat_race",
		response_kind: "capacity_arithmetic",
		operation: "add",
		left_litres: 8,
		left_millilitres: 250,
		right_litres: 4,
		right_millilitres: 750,
	},
};
const AFTER = {
	...RACE,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-CAPACITY-ARITHMETIC-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
};
const FOUNTAIN_ROUND = {
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
		skill_id: ARITHMETIC_SKILL_ID,
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "capacity",
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
			revision_id: "fountain-1",
			skill_id: ARITHMETIC_SKILL_ID,
			prompt_si: "fountain",
			game: {
				...RACE.game,
				operation: "subtract",
				left_litres: 3,
				left_millilitres: 200,
				right_litres: 1,
				right_millilitres: 450,
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

const key = (host: HTMLElement, digit: number) => {
	const element = [
		...host.querySelectorAll<HTMLButtonElement>(".keypad-key"),
	].find((button) => button.textContent === String(digit));
	if (!element) throw new Error(`missing key ${digit}`);
	return element;
};

async function tap(element: HTMLElement, times = 1) {
	for (let step = 0; step < times; step++)
		await act(async () => element.click());
}

async function typeNumber(host: HTMLElement, value: number) {
	for (const digit of String(value)) await tap(key(host, Number(digit)));
}

describe("water rules", () => {
	it("picks a random race kind that differs from the last one", () => {
		expect(missionOrder(null, () => 0)[0]).toBe(ARITHMETIC_SKILL_ID);
		expect(missionOrder(ARITHMETIC_SKILL_ID, () => 0)[0]).not.toBe(
			ARITHMETIC_SKILL_ID,
		);
	});

	it("writes 14 l 600 ml − 5 l 750 ml with a litre opened", () => {
		const task = readTask({
			response_kind: "capacity_arithmetic",
			operation: "subtract",
			left_litres: 14,
			left_millilitres: 600,
			right_litres: 5,
			right_millilitres: 750,
		});
		const working = solvedWorking(task);
		expect(working).toEqual({
			operation: "subtract",
			exchanged: true,
			ml: 850,
			litres: 8,
		});
		expect(arithmeticResponse(task, working)).toMatchObject({
			millilitre_subtotal_or_adjustment: 1600,
			working_steps: [
				"borrow:1",
				"adjust:14->13:600->1600",
				"ml:1600-750=850",
				"litres:13-5=8",
			],
		});
	});

	it("writes the jugs poured into the channel", () => {
		const task = readTask({
			response_kind: "capacity_delivery",
			requested_total_ml: 2250,
			mission_id: "delivery-2250",
		});
		expect(fillResponse(task, [1000, 1000, 250])).toMatchObject({
			delivered_total_ml: 2250,
			working_steps: [
				"portion:1000",
				"portion:1000",
				"portion:250",
				"total:2250",
				"convert:2250=2:250",
			],
			remaining_or_overflow_ml: 0,
			contextual_answer: "delivered:2250",
		});
	});
});

describe("Nimo's Water-Play Day", () => {
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

	it("fills the channel from two tanks, then takes water away at the fountain after a muddle", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: RACE,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: FOUNTAIN_ROUND,
				server_score: {
					correct: false,
					presentation_id: RACE.presentation_id,
					item_revision_id: RACE.revision_id,
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
				<NimoWaterDay
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byStart(host, "තරගෙට යමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-11",
				atomic_skill_id: ARITHMETIC_SKILL_ID,
			}),
			expect.any(String),
		);
		expect(host.querySelector(".race-send")).toBeNull();
		await tap(byLabel(host, "8 l 250 ml ටැංකියේ කරාම අරින්න"));
		await tap(byLabel(host, "4 l 750 ml ටැංකියේ කරාම අරින්න"));
		// A muddle: 1000 ml written as millilitres, never carried over as a litre.
		await tap(byLabel(host, "මිලිලීටර්"));
		await typeNumber(host, 1000);
		await tap(byLabel(host, "ලීටර්"));
		await typeNumber(host, 12);
		await tap(byStart(host, "🚤"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "capacity_arithmetic",
			millilitre_subtotal_or_adjustment: 1000,
			exchange_used: false,
			result_litres: 12,
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
			host.querySelector("[data-training-place='dancing-fountain']"),
		).not.toBeNull();
		// 3 l 200 ml − 1 l 450 ml: too few millilitres, so a litre is opened first.
		await tap(byStart(host, "450 ml ගමු"));
		expect(host.querySelector(".nimo-says-bubble")?.textContent).toContain(
			"මදිද",
		);
		await tap(byStart(host, "🔁"));
		await tap(byStart(host, "450 ml ගමු"));
		await tap(byStart(host, "1 l ගමු"));
		expect(host.querySelector(".fountain[data-done]")).not.toBeNull();
		await tap(byStart(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					exchange_used: true,
					millilitre_subtotal_or_adjustment: 1200,
					result_litres: 1,
					result_millilitres: 750,
				}),
			}),
			expect.any(String),
		);
		await tap(byStart(host, "තරගෙට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(host.querySelector(".nimo-says-bubble")?.textContent).toContain(
			"අලුත් තරගයක්",
		);
	});
});

describe("The water balloons", () => {
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

	it("fills a balloon with 1 l from two 500 ml jugs", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "capacity_composition",
			target_ml: 1000,
			available_portions_ml: [100, 200, 250, 500, 1000],
		});
		await act(async () =>
			root.render(
				<WaterBalloons
					task={task}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		await tap(byLabel(host, "500 ml වත් කරන්න"));
		expect(onResponse).toHaveBeenLastCalledWith(null);
		await tap(byLabel(host, "500 ml වත් කරන්න"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "capacity_composition",
			target_ml: 1000,
			selected_portions_ml: [500, 500],
			portion_counts: { "500": 2 },
			constructed_total_ml: 1000,
			overflow_ml: 0,
		});
	});

	it("pours to the 600 ml mark and reads it", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "vessel_reading",
			capacity_ml: 600,
			start_level_ml: 400,
			tick_interval_ml: 100,
		});
		await act(async () =>
			root.render(
				<WaterBalloons
					task={task}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		await tap(byStart(host, "💧"), 2);
		await tap(byLabel(host, "600 ml ඉර"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "vessel_reading",
			capacity_ml: 600,
			selected_tick_ml: 600,
			liquid_level_ml: 600,
			adjustment_actions: [500, 600],
		});
	});
});
