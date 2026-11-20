import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BalanceScale } from "../BalanceScale";
import { NimoParcelDay } from "../NimoParcelDay";
import { WeighingRoom } from "../WeighingRoom";
import {
	ARITHMETIC_SKILL_ID,
	arithmeticResponse,
	loadResponse,
	missionOrder,
	readTask,
	solvedWorking,
} from "../weighRules";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const CART = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-MASS-ARITHMETIC-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "පෙට්ටි දෙකේ බර 8 kg 250 gයි, 7 kg 750 gයි. කරත්තේ මුළු බර කීයද?",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "mass-adventure-item-v1",
		chapter: "parcel_cart",
		response_kind: "mass_arithmetic",
		operation: "add",
		left_kilograms: 8,
		left_grams: 250,
		right_kilograms: 7,
		right_grams: 750,
	},
};
const AFTER = {
	...CART,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-MASS-ARITHMETIC-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
};
const BALANCE_ROUND = {
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
		renderer_id: "mass",
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
			revision_id: "balance-1",
			skill_id: ARITHMETIC_SKILL_ID,
			prompt_si: "balance",
			game: {
				...CART.game,
				operation: "subtract",
				left_kilograms: 21,
				left_grams: 231,
				right_kilograms: 8,
				right_grams: 510,
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

describe("weigh rules", () => {
	it("picks a random cart kind that differs from the last one", () => {
		expect(missionOrder(null, () => 0)[0]).toBe(ARITHMETIC_SKILL_ID);
		expect(missionOrder(ARITHMETIC_SKILL_ID, () => 0)[0]).not.toBe(
			ARITHMETIC_SKILL_ID,
		);
	});

	it("writes 8 kg 250 g + 7 kg 750 g = 16 kg with a carried kilogram", () => {
		const task = readTask(CART.game);
		expect(arithmeticResponse(task, solvedWorking(task))).toMatchObject({
			gram_subtotal_or_adjustment: 1000,
			carried_or_borrowed_kilograms: 1,
			result_kilograms: 16,
			result_grams: 0,
			working_steps: ["g:250+750=1000", "carry:1", "g-result:0", "kg:8+7+1=16"],
		});
	});

	it("loads two boxes and finds the room left in the cart", () => {
		const task = readTask({
			response_kind: "mass_market_mission",
			mission_id: "market-1750-2250",
			item_ids: ["produce-crate", "delivery-parcel"],
			item_masses_g: [1750, 2250],
			cart_capacity_g: 7000,
		});
		expect(
			loadResponse(
				task,
				solvedWorking({ kind: "add", left: 1750, right: 2250 }),
				3000,
			),
		).toMatchObject({
			total_mass_g: 4000,
			selected_standard_masses_g: [2000, 2000],
			working_steps: ["g:750+250=1000", "carry:1", "g-result:0", "kg:1+2+1=4"],
			remaining_capacity_g: 3000,
			contextual_answer: "load:4000:remaining:3000",
		});
	});
});

describe("Nimo's Parcel Day", () => {
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

	it("weighs and loads two boxes, then unloads at the balance after a muddle", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: CART,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: BALANCE_ROUND,
				server_score: {
					correct: false,
					presentation_id: CART.presentation_id,
					item_revision_id: CART.revision_id,
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
				<NimoParcelDay
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byStart(host, "පටවමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-12",
				atomic_skill_id: ARITHMETIC_SKILL_ID,
			}),
			expect.any(String),
		);
		expect(host.querySelector(".cart-send")).toBeNull();
		await tap(byLabel(host, "පෙට්ටිය 1 තරාදියට"));
		expect(host.querySelector(".cart-scale-screen")?.textContent).toBe(
			"8 kg 250 g",
		);
		await tap(byLabel(host, "පෙට්ටිය 1 කරත්තේට"));
		await tap(byLabel(host, "පෙට්ටිය 2 තරාදියට"));
		await tap(byLabel(host, "පෙට්ටිය 2 කරත්තේට"));
		// A muddle: 1000 g written as grams, never carried over as a kilogram.
		await tap(byLabel(host, "ග්‍රෑම්"));
		await typeNumber(host, 1000);
		await tap(byLabel(host, "කිලෝග්‍රෑම්"));
		await typeNumber(host, 15);
		await tap(byStart(host, "🛒"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "mass_arithmetic",
			gram_subtotal_or_adjustment: 1000,
			exchange_used: false,
			result_kilograms: 15,
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
			host.querySelector("[data-training-place='balance-scale']"),
		).not.toBeNull();
		// 21 kg 231 g − 8 kg 510 g: too few grams, so a kilogram is opened first.
		await tap(byStart(host, "510 g අයින් කරමු"));
		expect(host.querySelector(".nimo-says-bubble")?.textContent).toContain(
			"මදිද",
		);
		await tap(byStart(host, "🔁"));
		await tap(byStart(host, "510 g අයින් කරමු"));
		await tap(byStart(host, "8 kg අයින් කරමු"));
		expect(host.querySelector(".balance-game[data-done]")).not.toBeNull();
		await tap(byStart(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					exchange_used: true,
					gram_subtotal_or_adjustment: 1231,
					result_kilograms: 12,
					result_grams: 721,
				}),
			}),
			expect.any(String),
		);
		await tap(byStart(host, "කරත්තේ ළඟට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(host.querySelector(".nimo-says-bubble")?.textContent).toContain(
			"අලුත් ගමනක්",
		);
	});
});

describe("The help games", () => {
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

	it("balances a 1 kg box with five 200 g weights", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "mass_balance",
			target_mass_g: 1000,
		});
		await act(async () =>
			root.render(
				<BalanceScale
					task={task}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		await tap(byLabel(host, "200 g දාමු"), 5);
		expect(host.querySelector(".balance[data-level]")).not.toBeNull();
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "mass_balance",
			target_mass_g: 1000,
			selected_mass_denominations_g: [200, 200, 200, 200, 200],
			denomination_counts: { "200": 5 },
			selected_total_g: 1000,
			balance_difference_g: 0,
			balanced: true,
		});
	});

	it("hangs the bag on the spring scale's hook", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "mass_instrument",
			object_id: "hanging-bag",
			instrument_types: [
				"two_pan_balance",
				"spring_balance",
				"dial_scale",
				"digital_scale",
				"platform_scale",
			],
		});
		await act(async () =>
			root.render(
				<WeighingRoom
					task={task}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		await tap(byLabel(host, "කටු තරාදිය"));
		await tap(byStart(host, "🥣"));
		expect(host.querySelector(".weigh-room[data-done]")).toBeNull();
		await tap(byLabel(host, "දුනු තරාදිය"));
		await tap(byStart(host, "🪝"));
		expect(host.querySelector(".weigh-reading")?.textContent).toBe("500 g");
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "mass_instrument",
			object_id: "hanging-bag",
			instrument_type: "spring_balance",
			placement: "hook",
			interaction_trace: [
				"place:hanging-bag:dial_scale:tray",
				"place:hanging-bag:spring_balance:hook",
			],
		});
	});
});
