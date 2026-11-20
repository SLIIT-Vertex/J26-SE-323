import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AlienBedtime } from "../AlienBedtime";
import { NimoSpaceSleepover } from "../NimoSpaceSleepover";
import { readTask } from "../spaceRules";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const BOARDING = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-DIV-WRITTEN-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "පුංචි යානා 4ට අමුත්තන් 124ක් සමානව බෙදමු!",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "division-adventure-item-v1",
		chapter: "ufo_boarding",
		response_kind: "written_division",
		dividend: 124,
		divisor: 4,
		has_remainder: false,
		dividend_digit_count: 3,
		step_count: 2,
	},
};
const AFTER = {
	...BOARDING,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-DIV-WRITTEN-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
	game: { ...BOARDING.game, dividend: 84, divisor: 2, dividend_digit_count: 2 },
};
const SPLITTER_ROUND = {
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
		skill_id: "G5-MAT-DIV-WRITTEN-01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "division",
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
			revision_id: "splitter-1",
			skill_id: "G5-MAT-DIV-WRITTEN-01",
			prompt_si: "split",
			game: { ...BOARDING.game, dividend: 124, divisor: 4 },
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

const byStart = (host: HTMLElement, text: string) => {
	const element = [...host.querySelectorAll("button")].find((button) =>
		button.textContent?.trim().startsWith(text),
	);
	if (!element) throw new Error(`missing ${text}`);
	return element;
};

async function tap(element: HTMLElement) {
	await act(async () => element.click());
}

describe("Nimo's Galactic Sleepover", () => {
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

	it("boards UFOs place by place, splits stars after a muddle and returns to a fresh boarding", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: BOARDING,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: SPLITTER_ROUND,
				server_score: {
					correct: false,
					presentation_id: BOARDING.presentation_id,
					item_revision_id: BOARDING.revision_id,
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
				<NimoSpaceSleepover
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "යානා පුරවමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-08",
				atomic_skill_id: "G5-MAT-DIV-WRITTEN-01",
			}),
			expect.any(String),
		);
		expect(host.querySelectorAll(".boarding-deck .ufo-slot")).toHaveLength(4);
		// A muddle: 3 in each from the tens only (30), forgetting the ones.
		for (let step = 0; step < 3; step++)
			await tap(byLabel(host, "දහය වැඩි කරන්න"));
		expect(host.querySelector(".boarding-each")?.textContent).toBe("= 30");
		await tap(byText(host, "🚀 පුරවලා ඉගිලවමු!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "written_division",
			quotient_digits: [3, 0],
			final_quotient: 30,
			final_remainder: 4,
		});
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
			host.querySelector("[data-training-place='star-splitter']"),
		).not.toBeNull();
		// One 100-bundle can't go in 4 UFOs: dealing nudges, splitting turns it into ten 10s.
		await tap(byStart(host, "⭐"));
		expect(host.querySelector(".space-message")?.textContent).toContain("කඩමු");
		await tap(byStart(host, "✂️"));
		for (let round = 0; round < 3; round++) await tap(byStart(host, "⭐"));
		await tap(byStart(host, "✂️"));
		await tap(byStart(host, "⭐"));
		expect(host.querySelector(".star-splitter[data-done]")).not.toBeNull();
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					final_quotient: 31,
					final_remainder: 0,
					quotient_digits: [3, 1],
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "යානා ළඟට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(api.open).toHaveBeenCalledTimes(1);
		expect(host.querySelector(".space-scroll")?.textContent).toContain(
			"අලුත් ගමනක්",
		);
	});
});

describe("Bouncy Alien Bedtime", () => {
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

	it("shares 9 babies into 2 pods and tucks the extra one in with Nimo", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "equal_sharing",
			dividend: 9,
			divisor: 2,
		});
		await act(async () =>
			root.render(
				<AlienBedtime
					task={task}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		for (let round = 0; round < 4; round++)
			await tap(byText(host, "හැම ඇඳකටම 1 බැගින්"));
		expect(onResponse).toHaveBeenLastCalledWith(null);
		await tap(byStart(host, "💤"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "equal_sharing",
			dividend: 9,
			divisor: 2,
			group_quantities: [4, 4],
			quotient: 4,
			remainder: 1,
		});
	});
});
