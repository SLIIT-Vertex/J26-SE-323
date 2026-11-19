import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BeadBuilder, BeadCompare } from "../BeadBounce";
import { CostumeShop } from "../CostumeShop";
import { NimoToybox } from "../NimoToybox";

const scene = vi.hoisted(() => ({
	setLine: vi.fn(),
	select: vi.fn(),
	march: vi.fn(),
	confused: vi.fn(),
	destroy: vi.fn(),
}));
vi.mock("../paradeScene", async (original) => ({
	...(await original<typeof import("../paradeScene")>()),
	mountParade: vi.fn(async () => scene),
}));
vi.mock("../../../../mobile-learning-flow/landscape/orientation", () => ({
	lockOrientation: vi.fn(async () => true),
}));

const evidence = { reset: vi.fn(), note: vi.fn(), summary: vi.fn() };

const PARADE = {
	presentation_id: "00000000-0000-4000-8000-0000000000b1",
	revision_id: "G5-MAT-NUM-ORDER-01:B:aaa@v1",
	measurement_role: "unsupported_before",
	assistance_state: "none",
	prompt_si: "order",
	accessibility_label_si: "",
	options: [],
	content_version: "v1",
	game: {
		chapter: "toy_parade",
		values: [3721, 3105, 3480, 3062],
		ascending: true,
	},
};
const AFTER = {
	...PARADE,
	presentation_id: "00000000-0000-4000-8000-0000000000a1",
	revision_id: "G5-MAT-NUM-ORDER-01:A:bbb@v1",
	measurement_role: "unsupported_after",
	game: {
		chapter: "toy_parade",
		values: [5210, 5902, 5011, 5600],
		ascending: false,
	},
};
const COSTUME_ROUND = {
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
		skill_id: "G5-MAT-NUM-POSITION-01",
		scaffold_type: "prerequisite_repair",
		english_tag_key: "PREREQUISITE_REPAIR",
		renderer_id: "numbers",
		parallel_example_id: "p1",
		parallel_example_version: "v1",
		parallel_values: [],
		required_actions: 1,
		round_number: 1,
		stage_index: 0,
		stage_count: 2,
		stage_kind: "practice",
		cues_si: [],
		lesson: null,
		activity: {
			presentation_id: "00000000-0000-4000-8000-0000000000c1",
			revision_id: "G5-MAT-NUM-POSITION-01:S:ccc@v1",
			skill_id: "G5-MAT-NUM-POSITION-01",
			prompt_si: "52 014 හි 2 ඉලක්කම තිබෙන්නේ කුමන ස්ථානයේද?",
			game: { chapter: "costume_shop", number: 52014, digit: 2 },
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

describe("Nimo's Wacky Toybox", () => {
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

	it("directs a parade, visits the costume shop after a muddle and returns to a fresh parade", async () => {
		const api = {
			open: vi.fn(async () => ({
				episode_id: "e1",
				status: "active",
				manifest: PARADE,
			})),
			answerBefore: vi.fn(async () => ({
				episode_id: "e1",
				status: "support_active",
				support: COSTUME_ROUND,
				server_score: {
					correct: false,
					presentation_id: PARADE.presentation_id,
					item_revision_id: PARADE.revision_id,
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
				<NimoToybox
					api={api as never}
					learnerId="00000000-0000-4000-8000-000000000001"
					condition="proposed"
					reducedMotion
					onBack={() => undefined}
					onFailure={() => undefined}
				/>,
			);
		});
		await tap(byText(host, "පෙළපාළියට යමු!"));
		expect(api.open).toHaveBeenCalledWith(
			expect.objectContaining({
				area_id: "G5-AREA-MAT-01",
				atomic_skill_id: "G5-MAT-NUM-ORDER-01",
			}),
			expect.any(String),
		);
		expect(host.querySelector(".toy-scroll")?.textContent).toContain(
			"කුඩාම අංකයේ සිට",
		);
		expect(byText(host, "පෙළපාළිය අරඹමු!").disabled).toBe(true);

		// Badge order is robot, dino, train, teddy; smallest first.
		for (const [toy, slot] of [
			["ටෙඩී 3 062", 1],
			["ඩයිනෝ 3 105", 2],
			["දුම්රිය 3 480", 3],
			["රොබෝ 3 721", 4],
		] as const) {
			await tap(byLabel(host, toy));
			await tap(byLabel(host, `${slot} වන තැන`));
		}
		expect(scene.setLine).toHaveBeenLastCalledWith([3, 1, 2, 0], 0);
		await tap(byText(host, "පෙළපාළිය අරඹමු!"));
		const [, body] = api.answerBefore.mock.calls[0] as unknown as [
			string,
			Record<string, unknown>,
		];
		expect(body.constructed_response).toMatchObject({
			kind: "number_order",
			order: [3062, 3105, 3480, 3721],
		});
		// The Numbers flow rejects any other summary field.
		expect(Object.keys(body.interaction_summary as object).sort()).toEqual([
			"active_time_ms",
			"attempt_count",
			"correction_count",
			"first_action_ms",
			"move_count",
		]);
		expect(scene.confused).toHaveBeenCalled();

		await act(async () => vi.advanceTimersByTime(2000));
		await tap(byText(host, "යමු!"));
		expect(
			host.querySelector("[data-training-place='costume-shop']"),
		).not.toBeNull();
		await tap(byText(host, "දහසස්ථානය"));
		expect(host.querySelector(".costume-card")?.textContent).toContain(
			"2 → 2 000",
		);
		await tap(byText(host, "බලමු!"));
		expect(api.answerSupported).toHaveBeenCalledWith(
			"e1",
			expect.objectContaining({
				constructed_response: expect.objectContaining({
					kind: "drag_to_slot",
					selected_place: 3,
				}),
			}),
			expect.any(String),
		);
		await tap(byText(host, "වේදිකාවට යමු"));
		expect(api.withdrawSupport).toHaveBeenCalled();
		const scroll = host.querySelector(".toy-scroll")?.textContent ?? "";
		expect(scroll).toContain("ලොකුම අංකයේ සිට");
		expect(scroll).toContain("නව සෙල්ලම් බඩු ආවා");
	});
});

describe("Backstage toys", () => {
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

	it("builds a number bead by bead and only answers after the child plays", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<BeadBuilder
					number={40205}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(onResponse).toHaveBeenLastCalledWith(null);
		for (let at = 0; at < 4; at++)
			await tap(byLabel(host, `දස දහස් දණ්ඩට බෝලයක් දාන්න (දැන් ${at})`));
		await tap(byLabel(host, "සිය දණ්ඩට බෝලයක් දාන්න (දැන් 0)"));
		await tap(byLabel(host, "සිය දණ්ඩට බෝලයක් දාන්න (දැන් 1)"));
		for (let at = 0; at < 6; at++)
			await tap(byLabel(host, `එක දණ්ඩට බෝලයක් දාන්න (දැන් ${at})`));
		await tap(byLabel(host, "එක දණ්ඩෙන් බෝලයක් ඉවත් කරන්න"));
		expect(host.querySelector(".bead-readout strong")?.textContent).toBe(
			"40 205",
		);
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "bead_placement",
			rods: [0, 4, 0, 2, 0, 5],
		});
	});

	it("shows faint target beads in a help stage and a finished toy as a worked example", async () => {
		await act(async () =>
			root.render(
				<BeadBuilder
					number={305}
					hint
					evidence={evidence}
					onResponse={vi.fn()}
				/>,
			),
		);
		expect(host.querySelectorAll(".bead[data-ghost]")).toHaveLength(8);
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<BeadBuilder
					key="demo"
					number={305}
					demo
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelector(".bead-readout strong")?.textContent).toBe("305");
		expect(
			[...host.querySelectorAll("button")].every((button) => button.disabled),
		).toBe(true);
		expect(onResponse).toHaveBeenLastCalledWith(null);
	});

	it("compares parade numbers on bead columns, then orders them", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<BeadCompare
					values={[3721, 3105, 3480]}
					ascending={false}
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelectorAll(".bead-compare-toy")).toHaveLength(3);
		expect(
			host.querySelector(".bead-compare-toy .mini-rod")?.childElementCount,
		).toBe(3);
		for (const [toy, slot] of [
			["රොබෝ 3 721", 1],
			["දුම්රිය 3 480", 2],
			["ඩයිනෝ 3 105", 3],
		] as const) {
			await tap(byLabel(host, toy));
			await tap(byLabel(host, `${slot} වන තැන`));
		}
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "number_order",
			order: [3721, 3480, 3105],
		});
	});

	it("dresses a digit by value when the question asks what it is worth", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<CostumeShop
					number={7821}
					digit={8}
					question="represented"
					hint
					evidence={evidence}
					onResponse={onResponse}
				/>,
			),
		);
		const tags = [...host.querySelectorAll(".costume-tag")].map(
			(tag) => tag.textContent,
		);
		expect(tags).toEqual(["8", "80", "800", "8 000"]);
		expect(
			host.querySelector(".costume[data-hint] .costume-tag")?.textContent,
		).toBe("800");
		await tap(byText(host, "800"));
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "drag_to_slot",
			represented_value: 800,
		});
	});
});
