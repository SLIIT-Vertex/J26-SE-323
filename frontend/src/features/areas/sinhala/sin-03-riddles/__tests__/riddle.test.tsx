import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RiddleBoard } from "../RiddleJourney";
import { RiddleReveal } from "../RiddleReveal";
import {
	type RiddleGame,
	recordAction,
	riddleResponse,
	toggleSpan,
} from "../riddleLogic";

vi.mock("../../../../gamification/GameHost", () => ({
	PhaserSurface: () => <div />,
}));

const game: RiddleGame = {
	schema_version: "sinhala-riddle-item-v1",
	chapter: "clue_path",
	activity_id: "clue_path",
	response_kind: "sinhala_riddle_solution",
	subfamily: "direct:short",
	goal_si: "goal",
	riddle_lines_si: ["උදැල්ල අරගෙන", "කුඹුරට යනවා"],
	clue_spans: [
		{ span_id: "span-aaaaaaaaaaaa", text_si: "උදැල්ල අරගෙන" },
		{ span_id: "span-bbbbbbbbbbbb", text_si: "කුඹුරට යනවා" },
	],
	answer_cards: [
		{ card_id: "card-111111111111", text_si: "කොකා" },
		{ card_id: "card-222222222222", text_si: "ගොවියා" },
		{ card_id: "card-333333333333", text_si: "මොනරා" },
		{ card_id: "card-444444444444", text_si: "ජිරාෆ්" },
	],
	evidence_limit: 2,
};

describe("riddle logic", () => {
	it("evidence is the child's own, in order, bounded", () => {
		expect(toggleSpan([], "a", 2)).toEqual(["a"]);
		expect(toggleSpan(["a"], "a", 2)).toEqual([]);
		expect(toggleSpan(["a", "b"], "c", 2)).toEqual(["a", "b"]);
		const history = Array.from({ length: 50 }).reduce<
			ReturnType<typeof recordAction>
		>((h) => recordAction(h, { type: "select_span", id: "a" }), []);
		expect(history).toHaveLength(40);
		expect(riddleResponse("c", ["a"])).toEqual({
			kind: "sinhala_riddle_solution",
			schema_version: "sinhala-riddle-response-v1",
			answer_card_id: "c",
			evidence_span_ids: ["a"],
		});
	});
});

let host: HTMLDivElement;
let root: Root;
beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});
afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("RiddleBoard", () => {
	it("shows the whole riddle, equal cards, and submits answer plus evidence once", () => {
		const submit = vi.fn();
		act(() =>
			root.render(
				<RiddleBoard
					revision="r"
					game={game}
					reducedMotion
					busy={false}
					checkLabel="ok"
					onSubmit={submit}
				/>,
			),
		);
		expect(host.textContent).toContain("උදැල්ල අරගෙන");
		expect(host.textContent).toContain("කුඹුරට යනවා");
		const classes = new Set(
			[...host.querySelectorAll(".rd-card")].map((b) => b.className),
		);
		expect(classes.size).toBe(1);
		const click = (t: string) =>
			act(() =>
				host.querySelector<HTMLButtonElement>(`[data-token="${t}"]`)?.click(),
			);
		click("span-bbbbbbbbbbbb");
		click("card-222222222222");
		const check = [...host.querySelectorAll("button")].find(
			(b) => b.textContent === "ok",
		);
		act(() => check?.click());
		act(() => check?.click());
		expect(submit).toHaveBeenCalledTimes(1);
		expect(submit.mock.calls[0][0]).toMatchObject({
			answer_card_id: "card-222222222222",
			evidence_span_ids: ["span-bbbbbbbbbbbb"],
		});
		// No answer, emoji or illustration on the independent board.
		expect(host.querySelector("svg")).toBeNull();
		expect(host.textContent).not.toMatch(/🦚|🦒|🕯️|🌙|⚽|☂️|🚂|🌈|🦋|🔑|🪁|🍄/u);
	});
});

describe("RiddleReveal", () => {
	it("keeps කොස්ස and ඉදල as different labelled drawings and labels emojis", () => {
		act(() =>
			root.render(
				<>
					<RiddleReveal revealKey="kossa" />
					<RiddleReveal revealKey="idala" />
					<RiddleReveal revealKey="monaraa" />
				</>,
			),
		);
		const labels = [...host.querySelectorAll('[role="img"]')].map((n) =>
			n.getAttribute("aria-label"),
		);
		expect(labels).toEqual(["කොස්ස", "ඉදල", "මොනරා"]);
		const drawings = [...host.querySelectorAll("svg")].map((n) => n.innerHTML);
		expect(drawings[0]).not.toEqual(drawings[1]);
	});
});
