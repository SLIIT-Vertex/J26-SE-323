import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import {
	AdventureBackButton,
	SuccessCelebration,
} from "../AdventureShared";

describe("shared adventure presentation", () => {
	it("uses an accessible icon-only back control", async () => {
		const host = document.createElement("div");
		const root = createRoot(host);
		const onClick = vi.fn();
		await act(async () => root.render(<AdventureBackButton onClick={onClick} />));
		const button = host.querySelector("button");
		expect(button?.getAttribute("aria-label")).toBe("ආපසු");
		expect(button?.textContent).toBe("");
		expect(button?.querySelector("svg")?.getAttribute("aria-hidden")).toBe(
			"true",
		);
		await act(async () => button?.click());
		expect(onClick).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
	});

	it("renders the common decorative success illustration", async () => {
		const host = document.createElement("div");
		const root = createRoot(host);
		await act(async () => root.render(<SuccessCelebration />));
		const image = host.querySelector("img.success-celebration-image");
		expect(image?.getAttribute("src")).toBe(
			"/curriculum/game/shared/child-celebrating-stars.png",
		);
		expect(image?.getAttribute("alt")).toBe("");
		await act(async () => root.unmount());
	});
});
