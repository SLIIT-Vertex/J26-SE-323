import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BowlingBuddies } from "../BowlingBuddies";
import { readTask } from "../carnivalRules";
import { NimoSportsCarnival } from "../NimoSportsCarnival";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const RACE = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "race-before",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "වට 3ක මුළු ලකුණු ගණන හොයමු!",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "multiplication-adventure-item-v1",
		chapter: "turbo_race",
		response_kind: "written_multiplication",
		multiplicand: 214,
		multiplier: 3,
		places: ["hundreds", "tens", "ones"],
		blank_count: 3,
		place_shift: false,
	},
};
const AFTER = {
	...RACE,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "race-after",
	measurement_role: "unsupported_after",
	game: { ...RACE.game, multiplicand: 231 },
};
const STADIUM_ROUND = {
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
		skill_id: "G5-MAT-MUL-BY-2-3-01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "multiplication",
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
			revision_id: "stadium-1",
			skill_id: "G5-MAT-MUL-BY-2-3-01",
			prompt_si: "stadium",
			game: { ...RACE.game, multiplicand: 128 },
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

/** Turn the wheels from all zeros to `digits` (▲ taps). */
async function setWheels(
	host: HTMLElement,
	places: string[],
	digits: number[],
) {
	for (const [at, digit] of digits.entries())
		for (let step = 0; step < digit; step++)
			await tap(byLabel(host, `${places[at]} තැන වැඩි කරන්න`));
}

describe("Nimo's Wacky Sports Carnival", () => {
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

	it("races, trains in the stadium after a muddled score and returns to a fresh race", async () => {
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
				support: STADIUM_ROUND,
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
				<NimoSportsCarnival
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion={false}
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "රේස් එකට යමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-06",
				atomic_skill_id: "G5-MAT-MUL-BY-2-3-01",
			}),
			expect.any(String),
		);
		// The race: three laps, each stamped with its own points and never a running total.
		expect(host.querySelectorAll(".race-stamps li")).toHaveLength(3);
		await tap(byText(host, "ටර්බෝ! 🚀"));
		for (let lap = 0; lap < 3; lap++)
			await act(async () => vi.advanceTimersByTime(1200));
		expect(host.querySelectorAll(".race-stamps li[data-done]")).toHaveLength(3);
		expect(host.textContent).not.toContain("642");
		expect(byText(host, "ලකුණු පුවරුවට!").disabled).toBe(true);

		// A muddled total: 632 instead of 642.
		await setWheels(host, ["සිය", "දහය", "එක"], [6, 3, 2]);
		await tap(byText(host, "ලකුණු පුවරුවට!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "written_multiplication",
			multiplicand: 214,
			multiplier: 3,
			result_digits: [6, 3, 2],
			product: 632,
		});
		// The Multiplication flow rejects any other summary field.
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"attempt_count",
			"first_action_ms",
		]);

		await act(async () => vi.advanceTimersByTime(2000));
		await tap(byText(host, "යමු!"));
		expect(
			host.querySelector("[data-training-place='dancing-stadium']"),
		).not.toBeNull();
		for (const block of ["සිය බ්ලොක් 100", "දහය බ්ලොක් 20", "එක බ්ලොක් 8"])
			await tap(byLabel(host, `${block} පේළිවලට දාන්න`));
		expect(
			[...host.querySelectorAll(".stadium-sum")].map((sum) => sum.textContent),
		).toEqual(["100 × 3 = 300", "20 × 3 = 60", "8 × 3 = 24"]);
		await setWheels(host, ["සිය", "දහය", "එක"], [3, 8, 4]);
		expect(host.querySelector(".stadium[data-wave]")).not.toBeNull();
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					result_digits: [3, 8, 4],
					product: 384,
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "රේස් එකට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(api.open).toHaveBeenCalledTimes(1);
		expect(host.querySelector(".race-stamps")).not.toBeNull();
	});
});

describe("Bowling Buddies", () => {
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

	it("sets up equal lanes, rolls 3 → 6 → 9 → 12 and answers with what the lanes make", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "multiplication_fact",
			multiplicand: 3,
			multiplier: 4,
		});
		await act(async () =>
			root.render(
				<BowlingBuddies
					task={task}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelector(".carnival-message")?.textContent).toBe(
			"එක පේළියකට කූරු 3ක් දාමු!",
		);
		for (let lane = 1; lane <= 4; lane++)
			await tap(byLabel(host, `${lane} වන පේළියට කූරු 3ක් දාන්න`));
		await tap(byText(host, "බෝලය ගහමු! 🎳"));
		for (let lane = 0; lane < 4; lane++)
			await act(async () => vi.advanceTimersByTime(800));
		expect(host.querySelector(".bowling-sum")?.textContent).toBe(
			"3 + 3 + 3 + 3 = 12",
		);
		expect(host.querySelector(".bowling-times")?.textContent).toBe(
			"4 × 3 = 12",
		);
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "multiplication_fact",
			multiplicand: 3,
			multiplier: 4,
			product: 12,
		});
	});
});
