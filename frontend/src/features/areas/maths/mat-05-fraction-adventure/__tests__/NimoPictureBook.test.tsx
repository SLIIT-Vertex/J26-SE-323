import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readPage } from "../bookRules";
import { FoldPop } from "../FoldPop";
import { NimoPictureBook } from "../NimoPictureBook";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const GARDEN = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-FRC-QUARTER-TABLE-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "table",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "fraction-adventure-item-v1",
		chapter: "color_splash_comic",
		response_kind: "fraction_quantity_table",
		denominator: 4,
		total: 8,
	},
};
const AFTER = {
	...GARDEN,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-FRC-QUARTER-TABLE-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
	game: { ...GARDEN.game, total: 12 },
};
const STICKER_ROUND = {
	scaffold_id: "s1",
	revision_id: "support-1",
	scaffold_type: "prerequisite_repair",
	title_si: "",
	body_si: [],
	visual_alt_text_si: null,
	maximum_steps: 3,
	game_manifest: {
		schema_version: "support-round-v1",
		activity_id: "a1",
		revision_id: "support-manifest-1",
		deterministic_seed: 1,
		skill_id: "G5-MAT-C03-L01-O02",
		scaffold_type: "prerequisite_repair",
		english_tag_key: "PREREQUISITE_REPAIR",
		renderer_id: "fractions",
		parallel_example_id: "p1",
		parallel_example_version: "v1",
		parallel_values: [],
		required_actions: 1,
		round_number: 1,
		stage_index: 0,
		stage_count: 1,
		stage_kind: "practice",
		cues_si: [],
		lesson: null,
		activity: {
			presentation_id: "00000000-0000-4000-8000-0000000000c1",
			revision_id: "G5-MAT-C03-L01-O02:unsupported_before:simpler:1@v1",
			skill_id: "G5-MAT-C03-L01-O02",
			prompt_si: "share",
			game: {
				schema_version: "fraction-adventure-item-v1",
				chapter: "sticker_party",
				response_kind: "equal_grouping",
				denominator: 4,
				total: 8,
			},
			returns_to_failed_item: false,
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

describe("Nimo's Magic Picture Book", () => {
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

	it("paints the quarter garden, shares stickers after a muddle and returns to a fresh page", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: GARDEN,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: STICKER_ROUND,
				server_score: {
					correct: false,
					presentation_id: GARDEN.presentation_id,
					item_revision_id: GARDEN.revision_id,
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
				<NimoPictureBook
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "පොත අරිමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-05",
				atomic_skill_id: "G5-MAT-FRC-QUARTER-TABLE-01",
			}),
			expect.any(String),
		);
		expect(host.querySelectorAll(".comic-flower")).toHaveLength(8);
		expect(byText(host, "චිත්‍රය අවසන්!").disabled).toBe(true);

		// 1/4, 2/4 and 3/4 of 8 flowers, painting 2, 4 and 5 (the last one muddled).
		for (const [count, last] of [
			[2, false],
			[4, false],
			[5, true],
		] as const) {
			for (let flower = 1; flower <= count; flower++)
				await tap(byLabel(host, `${flower} වන මල`));
			if (!last) await tap(byText(host, "ඊළඟ පිටුව ▶"));
		}
		await tap(byText(host, "චිත්‍රය අවසන්!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "fraction_quantity_table",
			total: 8,
			quarter_values: [2, 4, 5],
		});
		// The Fractions flow rejects any other summary field.
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"attempt_count",
			"correction_count",
			"first_action_ms",
			"move_count",
		]);

		await act(async () => vi.advanceTimersByTime(2000));
		await tap(byText(host, "යමු!"));
		expect(
			host.querySelector("[data-training-place='sticker-party']"),
		).not.toBeNull();
		// Two rounds of dealing: one sticker to each envelope, then one more each.
		for (const already of [0, 1])
			for (const envelope of [1, 2, 3, 4])
				await tap(
					byLabel(host, `${envelope} වන ලියුම් කවරයට ස්ටිකරයක් දාන්න (දැන් ${already})`),
				);
		expect(host.querySelector(".sticker-party[data-happy]")).not.toBeNull();
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					kind: "equal_grouping",
					denominator: 4,
					assignments: [0, 0, 1, 1, 2, 2, 3, 3],
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "පිටුවට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(api.open).toHaveBeenCalledTimes(1);
		expect(host.querySelector(".comic-ask")?.textContent).toContain("අලුත් පිටුවක්");
		expect(host.querySelectorAll(".comic-flower")).toHaveLength(12);
	});
});

describe("Fold & Pop", () => {
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

	it("folds a sheet into quarters before it can be painted, then pops the butterfly", async () => {
		const onResponse = vi.fn();
		const page = readPage({
			response_kind: "fraction_shading",
			representation: "rectangle",
			denominator: 4,
			requested_numerator: 1,
		});
		await act(async () =>
			root.render(
				<FoldPop page={page} evidence={evidence} onResponse={onResponse} />,
			),
		);
		expect(host.querySelector(".book-sheet")?.getAttribute("data-parts")).toBe(
			"1",
		);
		await tap(byText(host, "දෙකට නමමු!"));
		await act(async () => vi.advanceTimersByTime(500));
		expect(host.querySelector(".book-sheet")?.getAttribute("data-parts")).toBe(
			"2",
		);
		await tap(byText(host, "ආයෙත් දෙකට නමමු!"));
		await act(async () => vi.advanceTimersByTime(500));
		expect(host.querySelectorAll(".book-sheet-hit")).toHaveLength(4);
		await tap(byLabel(host, "3 වන කොටස"));
		expect(host.querySelector(".fold-butterfly")).not.toBeNull();
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "fraction_shading",
			representation: "rectangle",
			denominator: 4,
			shaded_indices: [2],
		});
	});
});
