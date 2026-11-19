import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NimoMovieStudio } from "../NimoMovieStudio";
import { PuppetShow } from "../PuppetShow";
import { readTask } from "../studioRules";

vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const SCENE = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-TIME-ELAPSED-01:unsupported_before:1@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "මේ දර්ශනයට කොච්චර වෙලාවක් ගියාද?",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		schema_version: "time-adventure-item-v1",
		chapter: "movie_mayhem",
		response_kind: "elapsed_time",
		start_hour: 6,
		start_minute: 20,
		end_hour: 7,
		end_minute: 10,
	},
};
const AFTER = {
	...SCENE,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-TIME-ELAPSED-01:unsupported_after:1@v1",
	measurement_role: "unsupported_after",
	game: {
		...SCENE.game,
		start_hour: 8,
		start_minute: 10,
		end_hour: 9,
		end_minute: 0,
	},
};
const EDIT_ROUND = {
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
		skill_id: "G5-MAT-TIME-ELAPSED-01",
		scaffold_type: "step_by_step_guidance",
		english_tag_key: "STEP_BY_STEP_GUIDANCE",
		renderer_id: "time",
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
			revision_id: "edit-1",
			skill_id: "G5-MAT-TIME-ELAPSED-01",
			prompt_si: "edit",
			game: {
				...SCENE.game,
				start_hour: 9,
				start_minute: 40,
				end_hour: 10,
				end_minute: 15,
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

function byText(host: HTMLElement, text: string) {
	const element = [...host.querySelectorAll("button")].find(
		(button) => button.textContent?.trim() === text,
	);
	if (!element) throw new Error(`missing ${text}`);
	return element;
}

async function tap(element: HTMLElement) {
	await act(async () => element.click());
}

describe("Nimo's Silly Movie Studio", () => {
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

	it("films a scene, rewinds in the editing room after a muddle and returns to a fresh scene", async () => {
		vi.spyOn(Math, "random").mockReturnValue(0);
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: SCENE,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: EDIT_ROUND,
				server_score: {
					correct: false,
					presentation_id: SCENE.presentation_id,
					item_revision_id: SCENE.revision_id,
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
				<NimoMovieStudio
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "රූගත කරමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-07",
				atomic_skill_id: "G5-MAT-TIME-ELAPSED-01",
			}),
			expect.any(String),
		);
		// 06:20 → 07:10 built as 1 hour (a base-100 slip), not 50 minutes.
		await tap(byText(host, "+ පැය 1 රීලය"));
		expect(host.querySelector(".filmstrip-total")?.textContent).toBe("පැය 1");
		await tap(byText(host, "🎬 රූගත කරමු!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "elapsed_time",
			hours: 1,
			minutes: 0,
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
			host.querySelector("[data-training-place='fast-forward']"),
		).not.toBeNull();
		// 09:40 forward in 5-minute steps: past 09:55 the clock rolls to 10:00 with the hour chime.
		for (let step = 0; step < 4; step++)
			await tap(byLabel(host, "මි. 5 ඉස්සරහට"));
		expect(host.querySelector(".ff-digital strong")?.textContent).toBe("10:00");
		expect(host.querySelector(".studio-message")?.textContent).toContain(
			"මිනිත්තු 60 = පැය 1",
		);
		for (let step = 0; step < 3; step++)
			await tap(byLabel(host, "මි. 5 ඉස්සරහට"));
		expect(host.querySelector(".ff-digital strong")?.textContent).toBe("10:15");
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					kind: "elapsed_time",
					hours: 0,
					minutes: 35,
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "සෙට් එකට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		expect(api.open).toHaveBeenCalledTimes(1);
		expect(host.querySelector(".studio-scroll")?.textContent).toContain(
			"අලුත් දර්ශනයක්",
		);
	});
});

describe("Tick-Tock Puppet Show", () => {
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

	it("sets 1:30 and afternoon, and the board shows 13:30", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "time_conversion",
			source_hour: 1,
			source_minute: 30,
			period: "pm",
		});
		await act(async () =>
			root.render(
				<PuppetShow task={task} evidence={evidence} onResponse={onResponse} />,
			),
		);
		await tap(byLabel(host, "පැය කටුව ඉස්සරහට"));
		for (let step = 0; step < 6; step++)
			await tap(byLabel(host, "මිනිත්තු කටුව ඉස්සරහට"));
		expect(onResponse).toHaveBeenLastCalledWith(null);
		await tap(byText(host, "🌙 ප.ව. (දවල්/රෑ)"));
		expect(host.querySelector(".puppet-reading")?.textContent).toBe("13:30");
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "time_conversion",
			hour24: 13,
			minute: 30,
		});
	});

	it("matches unit cards and answers with the partner of each card", async () => {
		const onResponse = vi.fn();
		const task = readTask({
			response_kind: "time_unit_match",
			left_options: [
				[60, "minutes"],
				[7, "days"],
			],
			right_options: [
				[1, "weeks"],
				[1, "hours"],
			],
		});
		await act(async () =>
			root.render(
				<PuppetShow task={task} evidence={evidence} onResponse={onResponse} />,
			),
		);
		await tap(byText(host, "මිනිත්තු 60"));
		await tap(byText(host, "පැය 1"));
		await tap(byText(host, "දින 7"));
		await tap(byText(host, "සති 1"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "time_unit_match",
			matches: [1, 0],
		});
	});
});
