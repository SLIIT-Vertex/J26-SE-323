import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import {
	AdventureBackButton,
	AdventureNotice,
	GameSuccessScreen,
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

	it("renders and dismisses the reusable compact notice", async () => {
		const host = document.createElement("div");
		const root = createRoot(host);
		const onDismiss = vi.fn();
		await act(async () =>
			root.render(
				<AdventureNotice
					message="ශූන්‍යය පළමු තැනට යොදන්න බැහැ."
					onDismiss={onDismiss}
				/>,
			),
		);
		expect(host.querySelector("[role='alert']")?.textContent).toContain(
			"ශූන්‍යය පළමු තැනට යොදන්න බැහැ.",
		);
		await act(async () => host.querySelector("button")?.click());
		expect(onDismiss).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
	});

	it("renders the canonical per-game success screen", async () => {
		const host = document.createElement("div");
		const root = createRoot(host);
		const onContinue = vi.fn();
		await act(async () =>
			root.render(
				<GameSuccessScreen gameNumber={1} onContinue={onContinue} />,
			),
		);
		expect(host.querySelector(".game-success-screen")?.getAttribute("data-completed-game")).toBe("1");
		expect(host.querySelector("h2")?.textContent).toBe("ක්‍රීඩාව 1 සම්පූර්ණයි!");
		expect(host.querySelector("button")?.textContent).toBe("ඊළඟ ක්‍රීඩාව");
		expect(host.querySelectorAll(".adventure-progress span")).toHaveLength(3);
		await act(async () => host.querySelector("button")?.click());
		expect(onContinue).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
	});

	it("completes all three numbered markers and offers game selection", async () => {
		const host = document.createElement("div");
		const root = createRoot(host);
		await act(async () =>
			root.render(<GameSuccessScreen gameNumber={3} onContinue={vi.fn()} />),
		);
		expect(host.querySelector("h2")?.textContent).toBe("ක්‍රීඩා තුනම සම්පූර්ණයි!");
		expect(host.querySelector("button")?.textContent).toBe("ක්‍රීඩා තේරීමට");
		expect(host.querySelector(".adventure-progress")?.getAttribute("data-progress-stage")).toBe("4");
		await act(async () => root.unmount());
	});
	it.each([1, 2, 4])("shows exactly %i completed games with a working return button", async (gameCount) => {
		const host = document.createElement("div");
		const root = createRoot(host);
		const onContinue = vi.fn();
		await act(async () => root.render(
			<GameSuccessScreen gameNumber={gameCount} gameCount={gameCount} onContinue={onContinue} />,
		));
		expect(host.querySelectorAll(".adventure-progress span.is-done")).toHaveLength(gameCount);
		expect(host.querySelectorAll(".success-celebration-image")).toHaveLength(1);
		expect(host.querySelector("button")?.textContent).toBe("ක්‍රීඩා තේරීමට");
		await act(async () => host.querySelector("button")?.click());
		expect(onContinue).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
	});

});
