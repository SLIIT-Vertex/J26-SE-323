import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	PUNCTUATION_ACTIVITIES,
	PunctuationBoard,
} from "../PunctuationJourney";
import {
	type PunctuationGame,
	place,
	preview,
	punctuationResponse,
	removeAt,
} from "../punctuationLogic";

vi.mock("../../gamification/GameHost", () => ({
	PhaserSurface: () => <div />,
}));

const span: PunctuationGame = {
	schema_version: "sinhala-punctuation-item-v1",
	chapter: "said_and_extra",
	activity_id: "quote_handles",
	response_kind: "sinhala_punctuation_span",
	subfamily: "quote:one-sentence",
	goal_si: "goal",
	tokens: [
		{ text_si: "මම" },
		{ text_si: "එන්නම්" },
		{ text_si: "නංගී" },
		{ text_si: "කීවා ය." },
	],
	boundaries: [0, 1, 2, 3, 4].map((p) => ({
		boundary_id: `gap-${p}aaaaaaaaaaa`,
		after_token_index: p - 1,
	})),
	mark_cards: [
		{
			token_id: "mark-open",
			display_si: "“",
			accessible_label_si: "ආරම්භක උඩු කොමාව",
		},
		{
			token_id: "mark-close",
			display_si: "”",
			accessible_label_si: "අවසාන උඩු කොමාව",
		},
	],
};

describe("punctuation logic", () => {
	it("a gap holds one mark and a card moves rather than duplicating", () => {
		let p = place({}, "g1", "c1");
		p = place(p, "g2", "c1");
		expect(p).toEqual({ g2: "c1" });
		p = place(p, "g2", "c2");
		expect(p).toEqual({ g2: "c2" });
		expect(removeAt(p, "g2")).toEqual({});
	});
	it("sends a reversed pair as reversed instead of fixing it", () => {
		const reversed = {
			"gap-0aaaaaaaaaaa": "mark-close",
			"gap-2aaaaaaaaaaa": "mark-open",
		};
		expect(punctuationResponse(span, reversed)).toEqual({
			kind: "sinhala_punctuation_span",
			schema_version: "sinhala-punctuation-response-v1",
			opening_mark_token_id: "mark-close",
			closing_mark_token_id: "mark-open",
			start_boundary_id: "gap-0aaaaaaaaaaa",
			end_boundary_id: "gap-2aaaaaaaaaaa",
		});
	});
	it("previews marks inside whole tokens only", () => {
		const text = preview(span, {
			"gap-0aaaaaaaaaaa": "mark-open",
			"gap-2aaaaaaaaaaa": "mark-close",
		});
		expect(text).toBe("“මම එන්නම්” නංගී කීවා ය.");
	});
	it("keeps the line-break activity locked", () => {
		const linebreak = PUNCTUATION_ACTIVITIES.find(
			(a) => a.id === "G5-SIN-PUNC-LINEBREAK-01",
		);
		expect(
			linebreak && "blockedReason" in linebreak && linebreak.blockedReason,
		).toBeTruthy();
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

describe("PunctuationBoard", () => {
	it("keyboard controls place both quotation marks and submit once", () => {
		const submit = vi.fn();
		act(() =>
			root.render(
				<PunctuationBoard
					revision="r1"
					game={span}
					reducedMotion
					busy={false}
					checkLabel="ok"
					onSubmit={submit}
				/>,
			),
		);
		const click = (token: string) =>
			act(() =>
				host
					.querySelector<HTMLButtonElement>(`[data-token="${token}"]`)
					?.click(),
			);
		click("mark-open");
		click("gap-0aaaaaaaaaaa");
		click("mark-close");
		click("gap-2aaaaaaaaaaa");
		const check = [...host.querySelectorAll("button")].find(
			(b) => b.textContent === "ok",
		);
		act(() => check?.click());
		act(() => check?.click());
		expect(submit).toHaveBeenCalledTimes(1);
		expect(submit.mock.calls[0][0]).toMatchObject({
			start_boundary_id: "gap-0aaaaaaaaaaa",
			end_boundary_id: "gap-2aaaaaaaaaaa",
		});
		// Gaps are named by the token before them, in Sinhala, never by correctness.
		expect(
			host
				.querySelector('[data-token="gap-2aaaaaaaaaaa"]')
				?.getAttribute("aria-label"),
		).toContain("එන්නම්");
	});
});
