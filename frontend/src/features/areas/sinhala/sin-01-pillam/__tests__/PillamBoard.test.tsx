import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PillamBoard } from "../PillamJourney";
import type { PillamGame } from "../pillamLogic";

vi.mock("../../../../gamification/GameHost", () => ({
	PhaserSurface: () => <div data-testid="canvas" />,
}));

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

const matchGame: PillamGame = {
	schema_version: "sinhala-pillam-item-v1",
	chapter: "pillam_friends",
	activity_id: "pillam_mithuro",
	response_kind: "sinhala_pillam_match",
	match_mode: "name",
	subfamily: "name:distinct",
	goal_si: "අද අපි පිල්ලම්වල හැඩයත් නමත් හඳුනාගනිමු 🌟",
	sign_cards: [
		{ token_id: "sign-aaa", display_si: "◌ි", accessible_label_si: "පිල්ලම් කාඩ්පත" },
	],
	destinations: [
		{ destination_id: "name-111", text_si: "කෙටි ඉස්පිල්ල" },
		{ destination_id: "name-222", text_si: "කොම්බුව" },
	],
};

function click(selector: string) {
	const element = host.querySelector<HTMLButtonElement>(selector);
	if (!element) throw new Error(`missing ${selector}`);
	act(() => element.click());
}

describe("PillamBoard", () => {
	it("tap/keyboard controls place a card and submit exactly once", () => {
		const submit = vi.fn();
		act(() =>
			root.render(
				<PillamBoard
					revision="r1"
					game={matchGame}
					reducedMotion
					busy={false}
					checkLabel="පරීක්ෂා කරන්න"
					onSubmit={submit}
				/>,
			),
		);
		const check = [...host.querySelectorAll("button")].find(
			(b) => b.textContent === "පරීක්ෂා කරන්න",
		);
		expect(check?.disabled).toBe(true);
		click('[data-token="sign-aaa"]');
		click('[data-token="name-222"]');
		expect(check?.disabled).toBe(false);
		act(() => check?.click());
		act(() => check?.click());
		expect(submit).toHaveBeenCalledTimes(1);
		const [response, interaction] = submit.mock.calls[0];
		expect(response).toEqual({
			kind: "sinhala_pillam_match",
			schema_version: "sinhala-pillam-response-v1",
			match_mode: "name",
			placements: [{ source_token_id: "sign-aaa", destination_id: "name-222" }],
		});
		expect(interaction).toMatchObject({ moves: 1, mode: "keyboard" });
	});

	it("starts neutral and resets when the revision changes", () => {
		const submit = vi.fn();
		const render = (revision: string) =>
			act(() =>
				root.render(
					<PillamBoard
						key={revision}
						revision={revision}
						game={matchGame}
						reducedMotion
						busy={false}
						checkLabel="ok"
						onSubmit={submit}
					/>,
				),
			);
		render("r1");
		click('[data-token="sign-aaa"]');
		expect(
			host
				.querySelector('[data-token="sign-aaa"]')
				?.getAttribute("aria-pressed"),
		).toBe("true");
		render("r2");
		expect(
			host
				.querySelector('[data-token="sign-aaa"]')
				?.getAttribute("aria-pressed"),
		).toBe("false");
	});

	it("labels cards in Sinhala without naming the answer", () => {
		act(() =>
			root.render(
				<PillamBoard
					revision="r1"
					game={matchGame}
					reducedMotion
					busy={false}
					checkLabel="ok"
					onSubmit={vi.fn()}
				/>,
			),
		);
		const label =
			host
				.querySelector('[data-token="sign-aaa"]')
				?.getAttribute("aria-label") ?? "";
		expect(label).toMatch(/පිල්ලම් කාඩ්පත/);
		expect(label).not.toMatch(/ඉස්පිල්ල/);
		// Decorative emoji in the goal never enters a scored control.
		expect(host.textContent).not.toContain("🌟");
	});
});
