import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RomanActivity, RomanSymbolBank } from "../RomanAdventureJourney";

describe("Roman adventure interactions", () => {
	let host: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		host = document.createElement("div");
		host.style.width = "320px";
		document.body.append(host);
		root = createRoot(host);
	});
	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});
	it("submits five matches as constructed evidence", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<RomanActivity
					game={{
						response_kind: "roman_numeral_match",
						round_id: "r1",
						arabic_values: [1, 4, 5, 9, 10],
						roman_tiles: ["i", "iv", "v", "ix", "x"],
					}}
					onResponse={onResponse}
				/>,
			),
		);
		const sections = host.querySelectorAll("section");
		for (let index = 0; index < 5; index += 1) {
			await act(async () =>
				(
					sections[0].querySelectorAll("button")[index] as HTMLButtonElement
				).click(),
			);
			await act(async () =>
				(
					sections[1].querySelectorAll("button")[index] as HTMLButtonElement
				).click(),
			);
		}
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "roman_numeral_match",
				matches: expect.arrayContaining([
					{ arabic_value: 9, selected_roman: "ix" },
				]),
			}),
		);
	});
	it("renders every emoji as its own labelled counting control", async () => {
		await act(async () =>
			root.render(
				<RomanActivity
					game={{
						response_kind: "emoji_quantity_to_roman",
						group_id: "g1",
						emoji_id: "star",
						emoji_symbol: "⭐",
						quantity: 6,
					}}
					onResponse={vi.fn()}
				/>,
			),
		);
		const buttons = host.querySelectorAll(".emoji-grid button");
		expect(buttons).toHaveLength(6);
		expect(buttons[0].getAttribute("aria-label")).toContain("තරුව 1");
	});
	it("accepts physical keyboard symbols", async () => {
		const onAdd = vi.fn();
		await act(async () =>
			root.render(
				<RomanSymbolBank symbols={[]} onAdd={onAdd} onRemove={vi.fn()} />,
			),
		);
		const fieldset = host.querySelector("fieldset") as HTMLFieldSetElement;
		await act(async () =>
			fieldset.dispatchEvent(
				new KeyboardEvent("keydown", { key: "v", bubbles: true }),
			),
		);
		expect(onAdd).toHaveBeenCalledWith("v");
	});
	it("renders symbol controls inside the mobile-width host", async () => {
		await act(async () =>
			root.render(
				<div className="roman-adventure">
					<RomanSymbolBank symbols={[]} onAdd={vi.fn()} onRemove={vi.fn()} />
				</div>,
			),
		);
		const button = host.querySelector("button") as HTMLButtonElement;
		expect(host.style.width).toBe("320px");
		expect(button.closest(".symbol-bank")).not.toBeNull();
		expect(button.getAttribute("aria-label")).toContain("සංකේතය");
	});
});
