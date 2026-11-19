import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readOrder } from "../cafeRules";
import { FluffballFeast } from "../FluffballFeast";
import { NimoMonsterCafe } from "../NimoMonsterCafe";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const ORDER = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-C07-L01-O01:B:aaa@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "රාක්ෂයෝ කෑවට පස්සේ කෑම කීයක් ඉතිරිද?",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "subtraction-adventure-item-v1",
		chapter: "monster_orders",
		places: ["hundreds", "tens", "ones"],
		place_labels_si: ["සිය", "දහය", "එක"],
		width: 3,
		blank_count: 3,
		minuend: 685,
		subtrahend: 339,
	},
};
const AFTER = {
	...ORDER,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-C07-L01-O01:A:bbb@v1",
	measurement_role: "unsupported_after",
	game: { ...ORDER.game, minuend: 742, subtrahend: 418 },
};
const SWAP_ROUND = {
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
		skill_id: "G5-MAT-C07-L01-O01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "subtraction",
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
			revision_id: "G5-MAT-C07-L01-O01:S:ccc@v1",
			skill_id: "G5-MAT-C07-L01-O01",
			prompt_si: "order",
			game: { ...ORDER.game, minuend: 563, subtrahend: 227 },
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

function byText(host: HTMLElement, text: string) {
	const element = [...host.querySelectorAll("button")].find(
		(button) => button.textContent?.trim() === text,
	);
	if (!element) throw new Error(`missing ${text}`);
	return element;
}

/** One tap, then let the screen update, as a child's finger would. */
async function tap(element: HTMLElement) {
	await act(async () => element.click());
}

describe("Nimo's Midnight Monster Café", () => {
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

	it("serves an order, practises in the snack swap after a muddle and returns to a fresh order", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: ORDER,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: SWAP_ROUND,
				server_score: {
					correct: false,
					presentation_id: ORDER.presentation_id,
					item_revision_id: ORDER.revision_id,
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
				<NimoMonsterCafe
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "කැෆේ එක අරිමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-04",
				atomic_skill_id: "G5-MAT-C07-L01-O01",
			}),
			expect.any(String),
		);
		expect(byText(host, "රාක්කයට යවමු!").disabled).toBe(true);

		// Open a ten-pack for the ones (crossing out 8 → 7, 5 → 15), then fill from the ones.
		await tap(byLabel(host, "දහය තීරුවෙන් පැකට්ටුවක් විවෘත කරන්න"));
		expect(
			[...host.querySelectorAll(".cafe-board-digit[data-changed] small")].map(
				(digit) => digit.textContent,
			),
		).toEqual(["7", "15"]);
		for (const digit of ["6", "4", "3"]) await tap(byText(host, digit));
		await tap(byText(host, "රාක්කයට යවමු!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "column_subtraction",
			result_digits: [3, 4, 6],
			exchanges: [{ from_place: "tens", to_place: "ones" }],
		});
		// The Subtraction flow rejects any other summary field.
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"attempt_count",
			"first_action_ms",
		]);

		await act(async () => vi.advanceTimersByTime(2000));
		await tap(byText(host, "යමු!"));
		expect(
			host.querySelector("[data-training-place='snack-swap']"),
		).not.toBeNull();
		// Too few singles: the tray says so until a ten-pack is opened.
		await tap(byLabel(host, "එක තැටියෙන් 7 ක් දෙන්න"));
		expect(host.querySelector(".snack-message")?.textContent).toContain(
			"දහයේ පැකට්ටුවක් විවෘත කරමු",
		);
		await tap(byLabel(host, "දහය එකක් විවෘත කරන්න"));
		await tap(byLabel(host, "එක තැටියෙන් 7 ක් දෙන්න"));
		await tap(byLabel(host, "දහය තැටියෙන් 2 ක් දෙන්න"));
		await tap(byLabel(host, "සිය තැටියෙන් 2 ක් දෙන්න"));
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					kind: "column_subtraction",
					result_digits: [3, 3, 6],
					exchanges: [{ from_place: "tens", to_place: "ones" }],
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "කවුන්ටරයට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(api.open).toHaveBeenCalledTimes(1);
		expect(host.querySelector(".cafe-scroll")?.textContent).toContain(
			"අලුත් ඇණවුමක්",
		);
	});
});

describe("Feed the Fluffballs", () => {
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
		vi.clearAllMocks();
	});

	it("feeds column by column, brings a pack when the plate is short, and answers with what is left", async () => {
		const onResponse = vi.fn();
		const order = readOrder({
			places: ["tens", "ones"],
			width: 2,
			relationship: "difference_between",
			quantities: [
				{ source: "first", label_si: "ගූගූ", value: 19 },
				{ source: "second", label_si: "බුබු", value: 45 },
			],
		});
		await act(async () =>
			root.render(
				<FluffballFeast
					order={order}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		// The smaller order cannot go on top in a help game.
		await tap(byText(host, "ගූගූ19"));
		expect(host.querySelector(".snack-message")?.textContent).toContain("පොඩියි");
		await tap(byText(host, "බුබු45"));
		expect(host.querySelector(".fluff-eaten")?.textContent).toBe("කෑවා 0 / 9");
		await tap(byText(host, "දහය එකක් ගෙනෙමු ➜"));
		expect(host.querySelector(".fluff-left strong")?.textContent).toBe("15");
		for (let bite = 0; bite < 9; bite++) await tap(byLabel(host, "කෑමක් දෙන්න"));
		expect(host.querySelector(".fluff-left strong")?.textContent).toBe("6");
		await act(async () => vi.advanceTimersByTime(1000));
		await tap(byLabel(host, "කෑමක් දෙන්න"));
		await act(async () => vi.advanceTimersByTime(1000));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "difference_story",
			relationship: "difference_between",
			minuend_source: "second",
			subtrahend_source: "first",
			result_digits: [2, 6],
			result: 26,
		});
	});
});
