import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import type { SupportView } from "../api/generated";
import {
	ENGLISH_SUPPORT_TAGS,
	SupportRoundFrame,
	SupportRoundPlay,
} from "../SupportRoundFrame";

const TAG_KEYS = {
	visual_guidance: "VISUAL_GUIDANCE",
	step_by_step_guidance: "GUIDED_REASONING",
	worked_parallel_example: "WORKED_EXAMPLE",
	simpler_same_game: "SIMPLER_VERSION",
	prerequisite_repair: "PREREQUISITE_REPAIR",
	conceptual_reexplanation: "CONCEPTUAL_REEXPLANATION",
} as const;

function support(
	type: keyof typeof TAG_KEYS,
	stageKind: "target" | "view" = "target",
): SupportView {
	const tag = TAG_KEYS[type];
	return {
		scaffold_id: `skill:${type}`,
		revision_id: `skill:${type}:round-1@v1`,
		scaffold_type: type,
		english_tag_key: tag,
		title_si: "උදව්ව",
		body_si: ["ක්‍රීඩාව තුළම උත්සාහ කරන්න."],
		visual_alt_text_si: null,
		maximum_steps: 1,
		game_manifest: {
			schema_version: "support-round-v1",
			activity_id: "number_world",
			revision_id: "manifest@v1",
			deterministic_seed: 5,
			skill_id: "G5-MAT-NUM-POSITION-01",
			scaffold_type: type,
			english_tag_key: tag,
			renderer_id: `number_world:${type}`,
			parallel_example_id: "parallel",
			parallel_example_version: "v1",
			parallel_values: [],
			required_actions: 1,
			round_number: 1,
			stage_index: 0,
			stage_count: 1,
			stage_kind: stageKind,
			cues_si: ["අගයන් බලන්න."],
			activity: {
				presentation_id: "00000000-0000-4000-8000-000000000001",
				revision_id: "item@v1",
				skill_id: "G5-MAT-NUM-POSITION-01",
				prompt_si: "එම ක්‍රීඩාව කරන්න.",
				returns_to_failed_item: false,
				game: {
					schema_version: "number-world-item-v1",
					chapter: "place_value_harbour",
					skill_id: "G5-MAT-NUM-POSITION-01",
					number: 52014,
					digit: 2,
					place: 3,
				},
			},
			worked_example: null,
		},
	};
}

describe("SupportRoundFrame", () => {
	for (const [type, label] of [
		["visual_guidance", "Visual guidance"],
		["simpler_same_game", "Simpler version"],
	] as const) {
		it(`shows ${label} and mounts the game activity`, async () => {
			const host = document.createElement("div");
			document.body.append(host);
			const root = createRoot(host);
			const renderActivity = vi.fn(() => (
				<div data-game-activity="number-world" />
			));
			await act(async () =>
				root.render(
					<SupportRoundFrame
						support={support(type)}
						renderActivity={renderActivity}
						onViewComplete={() => undefined}
					/>,
				),
			);
			expect(host.querySelector(".support-round-tag")?.textContent).toBe(label);
			expect(
				host.querySelector('[data-game-activity="number-world"]'),
			).not.toBeNull();
			expect(renderActivity).toHaveBeenCalledTimes(1);
			await act(async () => root.unmount());
			host.remove();
		});
	}

	it("labels every server help type with its small English tag", async () => {
		const expected = {
			visual_guidance: "Visual guidance",
			step_by_step_guidance: "Guided reasoning",
			worked_parallel_example: "Worked example",
			simpler_same_game: "Simpler version",
			prerequisite_repair: "Prerequisite repair",
			conceptual_reexplanation: "Conceptual re-explanation",
		} as const;
		for (const [type, label] of Object.entries(expected)) {
			expect(
				ENGLISH_SUPPORT_TAGS[TAG_KEYS[type as keyof typeof TAG_KEYS]],
			).toBe(label);
			const host = document.createElement("div");
			const root = createRoot(host);
			await act(async () =>
				root.render(
					<SupportRoundFrame
						support={support(type as keyof typeof TAG_KEYS)}
						renderActivity={() => <div data-game-activity="game" />}
						onViewComplete={() => undefined}
					/>,
				),
			);
			expect(host.querySelector(".support-round-tag")?.textContent).toBe(label);
			expect(
				host.querySelector(".support-round-tag")?.getAttribute("lang"),
			).toBe("en");
			await act(async () => root.unmount());
		}
	});

	it("hides the check button while a worked example is only being shown", async () => {
		for (const [stageKind, buttons] of [
			["view", ["දැන් මම කරමි"]],
			["target", ["Check"]],
		] as const) {
			const host = document.createElement("div");
			const root = createRoot(host);
			await act(async () =>
				root.render(
					<SupportRoundPlay
						support={support("worked_parallel_example", stageKind)}
						busy={false}
						ready
						checkLabel="Check"
						onCheck={() => undefined}
						onViewComplete={() => undefined}
						renderActivity={() => <div data-game-activity="game" />}
					/>,
				),
			);
			expect(
				[...host.querySelectorAll("button")].map(
					(button) => button.textContent,
				),
			).toEqual(buttons);
			await act(async () => root.unmount());
		}
	});

	it("shows only the English tag, never the Sinhala help name", async () => {
		const host = document.createElement("div");
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<SupportRoundFrame
					support={support("visual_guidance")}
					renderActivity={() => <div data-game-activity="game" />}
					onViewComplete={() => undefined}
				/>,
			),
		);
		expect(host.textContent).toContain("Visual guidance");
		expect(host.textContent).not.toContain("උදව්ව");
		await act(async () => root.unmount());
	});

	it("answers each guided question for this game", async () => {
		const view = support("step_by_step_guidance");
		if (view.game_manifest.schema_version !== "support-round-v1")
			throw new Error();
		view.game_manifest.guidance = [
			{ question_si: "ප්‍රශ්නය කුමක්ද?", answer_si: "ඉලක්කම 2 සොයන්න." },
			{ question_si: "පිළිතුර ගැළපේද?", answer_si: "පිළිතුර: 2" },
		];
		const host = document.createElement("div");
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<SupportRoundFrame
					support={view}
					renderActivity={() => <div data-game-activity="game" />}
					onViewComplete={() => undefined}
				/>,
			),
		);
		const pairs = [...host.querySelectorAll(".support-round-guidance li")].map(
			(row) => [
				row.querySelector("strong")?.textContent,
				row.querySelector("span")?.textContent,
			],
		);
		expect(pairs).toEqual([
			["ප්‍රශ්නය කුමක්ද?", "ඉලක්කම 2 සොයන්න."],
			["පිළිතුර ගැළපේද?", "පිළිතුර: 2"],
		]);
		await act(async () => root.unmount());
	});

	it("tints the real answer on the board while the child still plays", async () => {
		const view = support("simpler_same_game");
		if (
			view.game_manifest.schema_version !== "support-round-v1" ||
			!view.game_manifest.activity
		)
			throw new Error();
		view.game_manifest.activity.answer = {
			mode: "tint",
			lines: ["Father → පියා"],
			marks: ["Father", "පියා"],
		};
		const host = document.createElement("div");
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<SupportRoundFrame
					support={view}
					renderActivity={() => (
						<div>
							<button type="button">Father</button>
							<button type="button">Mother</button>
							<button type="button">පියා</button>
						</div>
					)}
					onViewComplete={() => undefined}
				/>,
			),
		);
		const marked = [...host.querySelectorAll(".support-answer-mark")].map(
			(element) => element.textContent,
		);
		expect(marked).toEqual(["Father", "පියා"]);
		const board = host.querySelector(".support-answer-board");
		expect(board?.getAttribute("data-answer-mode")).toBe("tint");
		expect(board?.hasAttribute("inert")).toBe(false);
		await act(async () => root.unmount());
	});

	it("shows a worked example already solved, and the child can still touch the board", async () => {
		const view = support("worked_parallel_example", "view");
		if (view.game_manifest.schema_version !== "support-round-v1")
			throw new Error();
		const activity = view.game_manifest.activity;
		if (!activity) throw new Error();
		view.game_manifest.activity = null;
		view.game_manifest.worked_example = {
			presentation_id: activity.presentation_id,
			revision_id: "worked@v1",
			skill_id: activity.skill_id,
			prompt_si: "විසඳූ උදාහරණය බලන්න.",
			game: activity.game,
			steps_si: ["ඉලක්කම සොයමු."],
			solution: { kind: "drag_to_slot", selected_place: 1 },
			answer: { mode: "filled", lines: ["45"], marks: ["45"] },
		};
		const host = document.createElement("div");
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<SupportRoundFrame
					support={view}
					renderActivity={() => <button type="button">45</button>}
					onViewComplete={() => undefined}
				/>,
			),
		);
		const board = host.querySelector(".support-answer-board");
		expect(board?.getAttribute("data-answer-mode")).toBe("filled");
		// Solved, but not locked: the child can place the shown answer themselves.
		expect(board?.hasAttribute("inert")).toBe(false);
		expect(board?.querySelector(".support-answer-mark")?.textContent).toBe(
			"45",
		);
		expect(host.querySelector(".support-answer-lines")?.textContent).toContain(
			"45",
		);
		await act(async () => root.unmount());
	});
});

describe("SupportRoundFrame lesson", () => {
	it("shows a visual demonstration solved, with a next button and nothing to submit", async () => {
		const view = support("visual_guidance", "view");
		if (view.game_manifest.schema_version !== "support-round-v1")
			throw new Error();
		view.game_manifest.lesson = {
			title_si: "බලන්න: මෙසේ කරයි",
			notes: [],
			steps_si: ["52 014 හි 2 ඇත්තේ දහස ස්ථානයේ."],
			answer_si: "2 තිබෙන්නේ දහස ස්ථානයේ.",
			hints_si: [],
			another_view_si: [],
			diagnosis: null,
			continue_label_si: "ඊළඟ",
		};
		const onViewComplete = vi.fn();
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<SupportRoundPlay
					support={view}
					busy={false}
					ready
					checkLabel="තහවුරු කරන්න"
					onCheck={vi.fn()}
					onViewComplete={onViewComplete}
					renderActivity={() => <button type="button">board</button>}
				/>,
			),
		);
		expect(host.querySelector(".support-lesson-steps")?.textContent).toContain(
			"දහස ස්ථානයේ",
		);
		expect(host.querySelector(".support-lesson-answer")?.textContent).toContain(
			"2 තිබෙන්නේ දහස ස්ථානයේ.",
		);
		const buttons = [...host.querySelectorAll("button")].map(
			(button) => button.textContent,
		);
		expect(buttons).toContain("ඊළඟ");
		expect(buttons).not.toContain("තහවුරු කරන්න");
		await act(async () =>
			[...host.querySelectorAll("button")]
				.find((b) => b.textContent === "ඊළඟ")
				?.click(),
		);
		expect(onViewComplete).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
		host.remove();
	});

	it("starts prerequisite repair from what the child did, without saying the answer", async () => {
		const target = support("prerequisite_repair");
		if (target.game_manifest.schema_version !== "support-round-v1")
			throw new Error();
		target.game_manifest.lesson = {
			title_si: "වැරදුණු තැන",
			notes: [{ title_si: "මූලික කුසලතාව", text_si: "මානසික එකතු කිරීම" }],
			steps_si: [],
			answer_si: null,
			hints_si: ["එකක තීරුවෙන් පටන් ගන්න."],
			another_view_si: ["4597 = 4000 + 500 + 90 + 7"],
			diagnosis: {
				you_did_si: "ඔබේ එකතුව 7610",
				went_wrong_si: "දහය තීරුවට ගෙන ආ 1 එකතු කිරීමට අමතක විය.",
			},
			continue_label_si: null,
		};
		const host = document.createElement("div");
		document.body.append(host);
		const root = createRoot(host);
		await act(async () =>
			root.render(
				<SupportRoundFrame
					support={target}
					onViewComplete={vi.fn()}
					renderActivity={() => <div>board</div>}
				/>,
			),
		);
		expect(
			host.querySelector(".support-lesson-diagnosis")?.textContent,
		).toContain("ගෙන ආ 1");
		expect(host.querySelector(".support-lesson-notes")?.textContent).toContain(
			"මානසික එකතු කිරීම",
		);
		expect(host.querySelector(".support-lesson-hints")?.textContent).toContain(
			"එකක තීරුවෙන්",
		);
		expect(host.querySelector(".support-lesson-another")).not.toBeNull();
		expect(host.querySelector(".support-lesson-answer")).toBeNull();
		await act(async () => root.unmount());
		host.remove();
	});
});
