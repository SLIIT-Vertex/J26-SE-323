import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoinBox } from "../CoinBox";
import { NimoShopDay } from "../NimoShopDay";
import {
	arithmeticResponse,
	missionOrder,
	readTask,
	SHOP_SKILL_ID,
	solvedWorking,
} from "../shopRules";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const PRODUCTS = [
	{ product_id: "rice-1kg", name_si: "හාල් 1 kg", unit_price_in_cents: 16500 },
	{ product_id: "dhal-1kg", name_si: "පරිප්පු 1 kg", unit_price_in_cents: 26000 },
	{ product_id: "sugar-1kg", name_si: "සීනි 1 kg", unit_price_in_cents: 24200 },
];
const TRIP = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-MONEY-SHOP-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "හාල් 2 kgක්, පරිප්පු 1 kgක් ගමු! මුළු ගණන කීයද?",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "money-adventure-item-v1",
		chapter: "grocery_shop",
		response_kind: "shopping_calculation",
		problem_id: "shop-total",
		products: PRODUCTS,
		selected_products: ["rice-1kg", "dhal-1kg"],
		quantities: [2, 1],
		amount_paid_in_cents: 59000,
		requires_change: false,
		line_count: 2,
	},
};
const AFTER = {
	...TRIP,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-MONEY-SHOP-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
};
const CASH_ROUND = {
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
		skill_id: "G5-MAT-MONEY-ADD-01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "money",
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
			revision_id: "cash-1",
			skill_id: "G5-MAT-MONEY-ADD-01",
			prompt_si: "cash",
			game: {
				schema_version: "money-adventure-item-v1",
				chapter: "grocery_shop",
				response_kind: "money_arithmetic",
				operation: "add",
				left_amount_in_cents: 16575,
				right_amount_in_cents: 24250,
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

describe("shop rules", () => {
	it("picks a random shopping kind that differs from the last one", () => {
		expect(missionOrder(null, () => 0)[0]).toBe(SHOP_SKILL_ID);
		expect(missionOrder(SHOP_SKILL_ID, () => 0)[0]).not.toBe(SHOP_SKILL_ID);
	});

	it("writes the cents-first working with a borrowed rupee", () => {
		const task = readTask({
			response_kind: "money_arithmetic",
			operation: "subtract",
			left_amount_in_cents: 50000,
			right_amount_in_cents: 16575,
		});
		const working = solvedWorking(task);
		expect(working).toEqual({
			operation: "subtract",
			exchanged: true,
			cents: 25,
			rupees: 334,
		});
		expect(arithmeticResponse(task, working)).toMatchObject({
			cent_subtotal_or_adjustment: 100,
			carried_or_borrowed_rupees: 1,
			result_in_cents: 33425,
			working_steps: [
				"borrow:1",
				"adjust:500->499:0->100",
				"cents:100-75=25",
				"rupees:499-165=334",
			],
		});
	});
});

describe("Nimo's Shopping Day", () => {
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

	it("fills the basket, writes the bill, then adds cents at the cash box after a muddle", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: TRIP,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: CASH_ROUND,
				server_score: {
					correct: false,
					presentation_id: TRIP.presentation_id,
					item_revision_id: TRIP.revision_id,
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
				<NimoShopDay
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byStart(host, "කඩේට යමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-10",
				atomic_skill_id: SHOP_SKILL_ID,
			}),
			expect.any(String),
		);
		expect(host.querySelector(".shop-pay")).toBeNull();
		await tap(byLabel(host, "හාල් කූඩෙට"), 2);
		await tap(byLabel(host, "පරිප්පු කූඩෙට"));
		// A muddle: the rice line is one kilo's price, not two.
		await tap(byLabel(host, "හාල් ගණන"));
		await typeNumber(host, 165);
		await tap(byLabel(host, "පරිප්පු ගණන"));
		await typeNumber(host, 260);
		await tap(byLabel(host, "මුළු ගණන"));
		await typeNumber(host, 425);
		await tap(byStart(host, "💰"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "shopping_calculation",
			selected_products: ["rice-1kg", "dhal-1kg"],
			quantities: [2, 1],
			line_totals_in_cents: [16500, 26000],
			total_in_cents: 42500,
			change_in_cents: 0,
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
			host.querySelector("[data-training-place='cash-box']"),
		).not.toBeNull();
		await tap(byStart(host, "💰 රු. 165.75"));
		await tap(byStart(host, "💰 රු. 242.50"));
		expect(host.querySelector(".cash-drawer-cents[data-full]")).not.toBeNull();
		await tap(byStart(host, "🔁"));
		expect(host.querySelector(".cash-box[data-done]")).not.toBeNull();
		await tap(byStart(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					exchange_used: true,
					cent_subtotal_or_adjustment: 125,
					result_in_cents: 40825,
				}),
			}),
			expect.any(String),
		);
		await tap(byStart(host, "කඩේට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(host.querySelector(".nimo-says-bubble")?.textContent).toContain(
			"අලුත් ලැයිස්තුවක්",
		);
	});
});

describe("The coin box", () => {
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

	it("makes Rs. 18 from 10, 5, 2 and 1", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "amount_construction",
			target_in_cents: 1800,
		});
		await act(async () =>
			root.render(
				<CoinBox task={task} evidence={evidence} onResponse={onResponse} />,
			),
		);
		for (const value of [10, 5, 2]) await tap(byLabel(host, `රු. ${value} දාමු`));
		expect(onResponse).toHaveBeenLastCalledWith(null);
		await tap(byLabel(host, "රු. 1 දාමු"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "amount_construction",
			target_in_cents: 1800,
			selected_denominations: ["coin-10", "coin-5", "coin-2", "coin-1"],
			denomination_counts: {
				"coin-1": 1,
				"coin-10": 1,
				"coin-2": 1,
				"coin-5": 1,
			},
			constructed_total_in_cents: 1800,
		});
	});

	it("sorts coins and notes smallest first into their sides", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "currency_recognition",
			tokens: [{ denomination_id: "note-20" }, { denomination_id: "coin-5" }],
		});
		await act(async () =>
			root.render(
				<CoinBox task={task} evidence={evidence} onResponse={onResponse} />,
			),
		);
		await tap(byLabel(host, "රු. 5 තෝරන්න"));
		await tap(byLabel(host, "කාසි පැත්තට"));
		await tap(byLabel(host, "රු. 20 තෝරන්න"));
		await tap(byLabel(host, "නෝට්ටු පැත්තට"));
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "currency_recognition",
				placements: [
					{
						denomination_id: "coin-5",
						currency_type: "coin",
						value_in_cents: 500,
						ordered_position: 0,
					},
					{
						denomination_id: "note-20",
						currency_type: "note",
						value_in_cents: 2000,
						ordered_position: 1,
					},
				],
			}),
		);
	});
});
