import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readPattern } from "../bubbleRules";
import { JellyfishParty } from "../JellyfishParty";
import { NimoBubbleTrouble } from "../NimoBubbleTrouble";
import { TikiSteps } from "../TikiSteps";

const scene = vi.hoisted(() => ({
	showJunction: vi.fn(),
	drive: vi.fn(),
	celebrate: vi.fn(),
	puzzled: vi.fn(),
	destroy: vi.fn(),
}));
vi.mock("../bubbleRushScene", async (original) => ({
	...(await original<typeof import("../bubbleRushScene")>()),
	// The submarine passes each ring at once, as if the animation had finished.
	mountBubbleRush: vi.fn(
		async (_host: HTMLElement, options: { onPassed(): void }) => {
			scene.drive.mockImplementation(() => options.onPassed());
			return scene;
		},
	),
}));
vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const RACE = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-PAT-RATIO-5-01:B:aaa@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "pattern",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "number-pattern-item-v1",
		chapter: "bubble_rush",
		operation: "multiply",
		visible_terms: [8, 40, null, null],
		missing_indices: [2, 3],
		term_count: 4,
	},
};
const AFTER = {
	...RACE,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-PAT-RATIO-5-01:A:bbb@v1",
	measurement_role: "unsupported_after",
	game: { ...RACE.game, visible_terms: [4, 20, null, null] },
};
const JELLY_ROUND = {
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
		skill_id: "G5-MAT-PAT-RATIO-5-01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "patterns",
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
			revision_id: "G5-MAT-PAT-RATIO-5-01:S:ccc@v1",
			skill_id: "G5-MAT-PAT-RATIO-5-01",
			prompt_si: "pattern",
			game: { ...RACE.game, visible_terms: [7, 35, null, null] },
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

describe("Nimo's Bubble Trouble", () => {
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

	it("races a pattern, trains in Jelly's shells after a muddle and returns to a fresh race", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0.99);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: RACE,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: JELLY_ROUND,
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
				<NimoBubbleTrouble
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "රේස් එකට යමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-03",
				atomic_skill_id: "G5-MAT-PAT-RATIO-5-01",
			}),
			expect.any(String),
		);
		expect(
			[...host.querySelectorAll(".bubble-trail li")].map(
				(li) => li.textContent,
			),
		).toEqual(["8", "40", "?", "?"]);
		expect(scene.showJunction).toHaveBeenLastCalledWith(
			["+2", "−2", "×2", "×5"],
			"rule",
		);
		expect(byText(host, "අවසන් රේඛාවට!").disabled).toBe(true);

		await tap(byLabel(host, "රීතිය ×5"));
		expect(scene.drive).toHaveBeenLastCalledWith(
			3,
			["200", "80", "72", "42", "38"],
			"number",
		);
		await tap(byLabel(host, "අංකය 200"));
		await tap(byLabel(host, "අංකය 1000"));
		// 1000 is the biggest ring, so the top lane.
		expect(scene.drive).toHaveBeenLastCalledWith(0, [], "finish");
		expect(
			[...host.querySelectorAll(".bubble-trail li")].map(
				(li) => li.textContent,
			),
		).toEqual(["8", "40", "200", "1000"]);
		await tap(byText(host, "අවසන් රේඛාවට!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "constant_ratio_pattern",
			multiplier: 5,
			completed_terms: [200, 1000],
		});
		// The Number Patterns flow rejects any other summary field.
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"attempt_count",
			"correction_count",
			"first_action_ms",
			"move_count",
		]);
		expect(scene.puzzled).toHaveBeenCalled();

		await act(async () => vi.advanceTimersByTime(2000));
		await tap(byText(host, "යමු!"));
		expect(
			host.querySelector("[data-training-place='jellyfish-party']"),
		).not.toBeNull();
		// A wrong shell: the jellyfish giggle and swim back.
		await tap(byLabel(host, "× 2 මැජික් කටුව"));
		expect(host.querySelector(".jelly-result[data-wrong]")).not.toBeNull();
		await act(async () => vi.advanceTimersByTime(1200));
		await tap(byLabel(host, "× 5 මැජික් කටුව"));
		await act(async () => vi.advanceTimersByTime(1200));
		expect(host.querySelector("[data-found]")?.getAttribute("data-shell")).toBe(
			"5",
		);
		await tap(byLabel(host, "× 5 මැජික් කටුව"));
		await tap(byLabel(host, "× 5 මැජික් කටුව"));
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					kind: "constant_ratio_pattern",
					multiplier: 5,
					completed_terms: [175, 875],
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "රේස් එකට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(api.open).toHaveBeenCalledTimes(1);
		expect(host.querySelector(".bubble-scroll")?.textContent).toContain(
			"අලුත් රේස් එකක්",
		);
		expect(
			[...host.querySelectorAll(".bubble-trail li")].map(
				(li) => li.textContent,
			),
		).toEqual(["4", "20", "?", "?"]);
	});
});

describe("Picking a race", () => {
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
		vi.restoreAllMocks();
		vi.clearAllMocks();
	});

	it("moves on to another pattern when every fresh race of the first is used up", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0.99);
		const usedUp = Object.assign(new Error("used up"), {
			code: "PROBE_ALREADY_RESERVED_OR_EXPOSED",
		});
		const open = vi.fn().mockRejectedValueOnce(usedUp).mockResolvedValueOnce({
			episode_id: "e1",
			status: "active",
			manifest: RACE,
		});
		const onFailure = vi.fn();
		await act(async () => {
			root.render(
				<NimoBubbleTrouble
					api={{ open } as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={onFailure}
				/>,
			);
		});
		await tap(byText(host, "රේස් එකට යමු!"));
		const skills = open.mock.calls.map(
			([request]) => (request as { atomic_skill_id: string }).atomic_skill_id,
		);
		expect(skills).toEqual(["G5-MAT-PAT-RATIO-5-01", "G5-MAT-PAT-DIFF-ASC-01"]);
		expect(onFailure).not.toHaveBeenCalled();
		expect(host.querySelector("[data-bubble-phase='mission']")).not.toBeNull();
	});
});

describe("Help games", () => {
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

	it("lets Tiki wobble on a wrong shell and answers with the hops the child chose", async () => {
		const onResponse = vi.fn();
		const board = readPattern({
			operation: "add",
			visible_terms: [1, 3, 5, 7, null, null],
			missing_indices: [4, 5],
		});
		await act(async () =>
			root.render(
				<TikiSteps
					board={board}
					hint
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelector(".tiki-call")?.textContent).toBe("දෙක බැගින් පනිමු!");
		expect(host.querySelector(".tiki-choice[data-ghost]")?.textContent).toBe(
			"9",
		);
		await tap(byLabel(host, "14 ට පනින්න"));
		expect(host.querySelector(".tiki-steps[data-wobble]")).not.toBeNull();
		expect(onResponse).toHaveBeenLastCalledWith(null);
		await act(async () => vi.advanceTimersByTime(1000));
		await tap(byLabel(host, "9 ට පනින්න"));
		await tap(byLabel(host, "11 ට පනින්න"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "constant_difference_pattern",
			operation: "add",
			difference: 2,
			completed_terms: [9, 11],
		});
	});

	it("shows finished boards as worked examples that cannot be touched", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<TikiSteps
					board={readPattern({
						operation: "subtract",
						visible_terms: [30, 28, 26, 24, null, null],
					})}
					demo
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(
			[...host.querySelectorAll(".tiki-shell b")].map(
				(shell) => shell.textContent,
			),
		).toEqual(["30", "28", "26", "24", "22", "20"]);
		expect(host.querySelector("button")).toBeNull();
		expect(onResponse).toHaveBeenLastCalledWith(null);

		await act(async () =>
			root.render(
				<JellyfishParty
					board={readPattern({
						operation: "multiply",
						visible_terms: [5, 10, 20, null, null],
					})}
					demo
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(
			[...host.querySelectorAll(".pattern-strip li")].map(
				(li) => li.textContent,
			),
		).toEqual(["5", "10", "20", "40", "80"]);
		expect(
			[...host.querySelectorAll("button")].every((button) => button.disabled),
		).toBe(true);
		expect(host.querySelector(".jelly-total")?.textContent).toBe("80");
		expect(onResponse).toHaveBeenLastCalledWith(null);
	});
});
