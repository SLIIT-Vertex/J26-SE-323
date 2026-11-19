import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NimoSkyAdventure } from "../NimoSkyAdventure";

const scene = vi.hoisted(() => ({
	loadCrate: vi.fn(),
	pose: vi.fn(),
	celebrate: vi.fn(),
	stayLocked: vi.fn(),
	destroy: vi.fn(),
}));
const factory = vi.hoisted(() => ({
	show: vi.fn(),
	refuse: vi.fn(),
	destroy: vi.fn(),
}));
const orientation = vi.hoisted(() => vi.fn(async () => true));

vi.mock("../skyCityScene", () => ({ mountSkyCity: vi.fn(async () => scene) }));
vi.mock("../factoryScene", () => ({
	mountFactory: vi.fn(async () => factory),
}));
vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: orientation,
}));

const BEFORE = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-C06-L01-O03:B:aaa@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "382 + 728 + 298",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		chapter: "sky_city",
		addends: [382, 728, 298],
		addend_count: 3,
	},
};
const AFTER = {
	...BEFORE,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-C06-L01-O03:A:bbb@v1",
	measurement_role: "unsupported_after",
	game: {
		chapter: "sky_city",
		addends: [295, 510, 282],
		addend_count: 3,
	},
};
const SUPPORT = {
	scaffold_id: "scaffold-1",
	revision_id: "support-1",
	scaffold_type: "prerequisite_repair",
	title_si: "මූලික කුසලතාව",
	body_si: [],
	visual_alt_text_si: null,
	maximum_steps: 3,
	game_manifest: {
		schema_version: "support-round-v1",
		activity_id: "activity-1",
		revision_id: "support-manifest-1",
		deterministic_seed: 1,
		skill_id: "G5-MAT-C06-L01-O01",
		scaffold_type: "prerequisite_repair",
		english_tag_key: "PREREQUISITE_REPAIR",
		renderer_id: "addition",
		parallel_example_id: "p1",
		parallel_example_version: "v1",
		parallel_values: [],
		required_actions: 1,
		round_number: 1,
		stage_index: 0,
		stage_count: 2,
		stage_kind: "practice",
		cues_si: ["එකක තීරුවෙන් පටන් ගනිමු."],
		lesson: null,
		activity: {
			presentation_id: "00000000-0000-4000-8000-0000000000c1",
			revision_id: "G5-MAT-C06-L01-O01:S:ccc@v1",
			skill_id: "G5-MAT-C06-L01-O01",
			prompt_si: "458 + 379",
			game: { chapter: "number_factory", addends: [458, 379] },
			returns_to_failed_item: false,
		},
		worked_example: null,
	},
};

function buttonByText(host: HTMLElement, text: string) {
	const button = [...host.querySelectorAll("button")].find(
		(item) => item.textContent?.trim() === text,
	);
	if (!button) throw new Error(`missing button ${text}`);
	return button;
}

function click(element: Element | null | undefined, times = 1) {
	if (!element) throw new Error("missing element");
	for (let at = 0; at < times; at++) (element as HTMLElement).click();
}

describe("Nimo's Sky Adventure", () => {
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

	it("plays the city mission, trains after a closed door and returns to a fresh mission", async () => {
		const api = {
			open: vi.fn(async () => ({
				episode_id: "episode-1",
				status: "active",
				manifest: BEFORE,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "episode-1",
				status: "support_active",
				support: SUPPORT,
				server_score: {
					correct: false,
					presentation_id: BEFORE.presentation_id,
					item_revision_id: BEFORE.revision_id,
				},
			})),
			answerSupported: vi.fn(async () => ({
				episode_id: "episode-1",
				status: "support_active",
				support_round: {
					withdrawal_allowed: true,
					support_revision_id: "support-1",
					manifest_revision_id: "support-manifest-1",
				},
			})),
			completeSupport: vi.fn(),
			withdrawSupport: vi.fn(async () => ({
				episode_id: "episode-1",
				status: "withdrawn",
			})),
			presentAfter: vi.fn(async () => ({
				episode_id: "episode-1",
				status: "active",
				manifest: AFTER,
			})),
			answerAfter: vi.fn(),
		};
		const onFailure = vi.fn();
		await act(async () => {
			root.render(
				<NimoSkyAdventure
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={onFailure}
				/>,
			);
		});
		expect(orientation).toHaveBeenCalledWith("landscape");

		await act(async () => click(buttonByText(host, "යමු!")));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-02",
				atomic_skill_id: "G5-MAT-C06-L01-O03",
			}),
			expect.any(String),
		);
		expect(host.querySelector(".sky-lock-panel")).toBeNull();

		// Load the three crates from the delivery board; the lock appears with the sum hidden.
		const crates = [
			...host.querySelectorAll<HTMLButtonElement>(".sky-board button"),
		];
		expect(crates.map((crate) => crate.textContent)).toEqual([
			"A382",
			"B728",
			"C298",
		]);
		await act(async () => {
			for (const crate of crates) crate.click();
		});
		expect(scene.loadCrate).toHaveBeenCalledTimes(3);
		expect(host.querySelector(".sky-equation")?.textContent).toBe(
			"382 + 728 + 298 = ?",
		);
		expect(host.textContent).not.toContain("1408");

		// 1 4 0 8, with carries into the thousands (1), hundreds (2) and tens (1).
		const ups = [
			...host.querySelectorAll<HTMLButtonElement>(
				".sky-lock-panel .carry-wheel-step",
			),
		].filter((_, at) => at % 2 === 0);
		const sparks = [
			...host.querySelectorAll<HTMLButtonElement>(
				".sky-lock-panel button.carry-spark",
			),
		];
		await act(async () => {
			click(ups[0], 2);
			click(ups[1], 5);
			click(ups[2], 1);
			click(ups[3], 9);
			click(sparks[0], 1);
			click(sparks[1], 2);
			click(sparks[2], 1);
		});
		await act(async () => click(buttonByText(host, "දොර අරින්න")));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toEqual({
			kind: "regroup_carry",
			total: 1408,
			carry_count: 3,
			aligned: true,
			presentation_id: BEFORE.presentation_id,
			item_revision_id: BEFORE.revision_id,
			interaction_version: "constructed-response-v1",
		});
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"alignment_valid",
			"attempt_count",
			"carry_actions",
			"column_actions",
			"correction_count",
			"first_action_ms",
			"move_count",
		]);
		expect(scene.stayLocked).toHaveBeenCalled();

		// The door stays shut, then Nimo goes to train.
		await act(async () => vi.advanceTimersByTime(2000));
		await act(async () => click(buttonByText(host, "පුහුණුවට යමු")));
		expect(
			host.querySelector("[data-training-place='number-factory']"),
		).not.toBeNull();
		expect(host.querySelector(".support-round-tag")?.textContent).toBe(
			"Prerequisite repair",
		);
		// The Number Factory: feed both numbers, bundle the full places, read the bins.
		const byLabel = (label: string) =>
			host.querySelector<HTMLButtonElement>(
				`.sky-training [aria-label="${label}"]`,
			);
		expect(byLabel("458 යන්ත්‍රයට දාන්න")).not.toBeNull();
		expect(buttonByText(host, "බලමු!").disabled).toBe(true);
		await act(async () => {
			click(byLabel("458 යන්ත්‍රයට දාන්න"));
			click(byLabel("379 යන්ත්‍රයට දාන්න"));
		});
		expect(factory.show).toHaveBeenLastCalledWith([17, 12, 7], {
			type: "feed",
		});
		await act(async () => {
			click(byLabel("එක 10ක් දහය 1කට බඳින්න"));
			click(byLabel("දහය 10ක් සිය 1කට බඳින්න"));
			click(byLabel("දහය 10ක් සිය 1කට බඳින්න"));
		});
		expect(factory.show).toHaveBeenLastCalledWith([7, 3, 8], {
			type: "bundle",
			from: 1,
		});
		expect(factory.refuse).toHaveBeenCalledWith(1);
		await act(async () => {
			click(byLabel("සිය ඉලක්කම වැඩි කරන්න"), 9);
			click(byLabel("දහය ඉලක්කම වැඩි කරන්න"), 4);
			click(byLabel("එක ඉලක්කම වැඩි කරන්න"), 8);
		});
		await act(async () => click(buttonByText(host, "බලමු!")));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"episode-1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					kind: "regroup_carry",
					total: 837,
				}),
			}),
			expect.any(String),
		);

		// Training ends: the help is removed before the fresh city mission.
		expect(host.querySelector(".sky-training")).toBeNull();
		await act(async () => click(buttonByText(host, "නගරයට යමු")));
		expect(api.withdrawSupport).toHaveBeenCalledWith(
			"episode-1",
			expect.objectContaining({
				all_support_removed: true,
				answer_revealing_state_cleared: true,
				input_handlers_cleared: true,
			}),
			expect.any(String),
		);
		expect(api.presentAfter).toHaveBeenCalled();
		expect(host.querySelector(".sky-scroll")?.textContent).toContain(
			"නිමෝ ආපසු ආවා",
		);
		expect(
			[...host.querySelectorAll(".sky-board button")].map(
				(crate) => crate.textContent,
			),
		).toEqual(["A295", "B510", "C282"]);
		expect(onFailure).not.toHaveBeenCalled();
	});

	it("turns the phone back to portrait when the child leaves", async () => {
		const onBack = vi.fn();
		await act(async () => {
			root.render(
				<NimoSkyAdventure
					api={{} as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="baseline"
					reducedMotion
					onBack={onBack}
					onFailure={() => undefined}
				/>,
			);
		});
		const back = host.querySelector<HTMLButtonElement>(
			".landscape-game-stage .landscape-back-button",
		);
		await act(async () => click(back));
		expect(onBack).toHaveBeenCalled();
		await act(async () => root.render(<div />));
		expect(orientation).toHaveBeenLastCalledWith("portrait");
	});
});
