import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationBoard } from "../ConversationStreet";

vi.mock("../ConversationScene", () => ({
	ConversationScene: () => <div>Story scene</div>,
}));
let host: HTMLDivElement;
let root: Root;
const respond = vi.fn();
beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
	respond.mockClear();
});
afterEach(() => {
	act(() => root.unmount());
	host.remove();
});
function render(game: Record<string, unknown>) {
	act(() =>
		root.render(
			<ConversationBoard
				game={{ command_token: "cmd", ...game }}
				onResponse={respond}
			/>,
		),
	);
}
function click(text: string) {
	const button = [...host.querySelectorAll("button")].find((node) =>
		node.textContent?.includes(text),
	);
	if (!button) throw new Error(`Missing button: ${text}`);
	act(() => button.click());
}
describe("Conversation Street interactions", () => {
	it("shows matched replies and keeps sequential unique links after replacement", () => {
		render({
			response_kind: "conversation_pair_links",
			questions: [
				{ question_token: "q1", text_en: "Your name?" },
				{ question_token: "q2", text_en: "Your age?" },
			],
			responses: [
				{ response_token: "r1", text_en: "Ruwan." },
				{ response_token: "r2", text_en: "Eight." },
			],
		});
		click("Your name?");
		click("Ruwan.");
		click("Your age?");
		click("Eight.");
		expect(host.querySelector(".cs-linked-reply")?.textContent).toBe("Ruwan.");
		click("Your name?");
		act(() =>
			(
				host.querySelector(".cs-response-sheet button") as HTMLButtonElement
			).click(),
		);
		expect(
			respond.mock.lastCall?.[0].links.map(
				(row: { sequence: number }) => row.sequence,
			),
		).toEqual([1, 2]);
		click("Your name?");
		act(() =>
			(
				host.querySelectorAll(
					".cs-response-sheet button",
				)[1] as HTMLButtonElement
			).click(),
		);
		expect(respond.mock.lastCall?.[0].unlinked_question_tokens).toEqual(["q2"]);
		expect(respond.mock.lastCall?.[0].revisions).toBe(2);
	});
	it("shows sentence pieces in chosen order and lets the learner remove them", () => {
		render({
			response_kind: "fictional_profile_reply",
			profile_token: "p",
			profile_label: "Fictional profile B",
			question_token: "q",
			question_text: "Your name?",
			profile_facts: [],
			chunks: [
				{ chunk_token: "c2", text_en: "Ruwan." },
				{ chunk_token: "c1", text_en: "I am" },
			],
		});
		expect(host.querySelector("h2")?.textContent).toBe("Character B");
		expect(host.querySelector("details")).toBeNull();
		click("I am");
		click("Ruwan.");
		expect(
			[...host.querySelectorAll(".cs-slots button")].map((row) =>
				row.textContent?.trim(),
			),
		).toEqual(["I am ×", "Ruwan. ×"]);
		click("I am");
		expect(respond.mock.lastCall?.[0].ordered_chunk_tokens).toEqual(["c2"]);
		expect(respond.mock.lastCall?.[0].unused_chunk_tokens).toEqual(["c1"]);
	});
	it("allows removing dialogue turns and re-enables their choices", () => {
		render({
			response_kind: "conversation_turn_sequence",
			dialogue_token: "d",
			speaker_labels: [],
			turns: [
				{ turn_token: "t1", speaker_token: "a", text_en: "Can you sing?" },
				{ turn_token: "t2", speaker_token: "b", text_en: "Yes, I can." },
			],
		});
		click("Can you sing?");
		click("Yes, I can.");
		click("Can you sing?");
		expect(respond.mock.lastCall?.[0].ordered_turn_tokens).toEqual(["t2"]);
		expect(
			(host.querySelector(".cs-response-sheet button") as HTMLButtonElement)
				.disabled,
		).toBe(false);
	});
	it("visibly selects a scene reply and allows changing it", () => {
		render({
			response_kind: "conversation_scene_reply",
			scene_token: "s",
			prompt_token: "q",
			prompt_text: "What is this?",
			scene_renderer: { non_colour_cue: "bush" },
			responses: [
				{ response_token: "r1", text_en: "A bush." },
				{ response_token: "r2", text_en: "A house." },
			],
		});
		click("A bush.");
		click("A house.");
		expect(host.querySelectorAll('[aria-pressed="true"]')).toHaveLength(1);
		expect(host.querySelector('[aria-pressed="true"]')?.textContent).toBe(
			"A house.",
		);
		expect(respond.mock.lastCall?.[0].response_token).toBe("r2");
	});
});
