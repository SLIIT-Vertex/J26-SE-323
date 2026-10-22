import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryActivity } from "../SriLankaDiscovery";

describe("Sri Lanka Discovery activities", () => {
	let container: HTMLDivElement;
	beforeEach(() => {
		container = document.createElement("div");
		document.body.append(container);
	});
	afterEach(() => container.remove());

	it("offers a tap alternative for word mapping", async () => {
		const onResponse = vi.fn();
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<DiscoveryActivity
					game={{
						response_kind: "semantic_label_mapping",
						command_token: "opaque",
						labels: [{ label_id: "l1", text_en: "Temple" }],
						destinations: [{ destination_id: "d1", text_si: "පන්සල" }],
					}}
					onResponse={onResponse}
				/>,
			),
		);
		const buttons = container.querySelectorAll("button");
		await act(async () => {
			(buttons[0] as HTMLButtonElement).click();
		});
		await act(async () => {
			(buttons[1] as HTMLButtonElement).click();
		});
		expect(onResponse).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
	});

	it("places a cultural word into a semantic group", async () => {
		const onResponse = vi.fn();
		const root = createRoot(container);
		await act(async () =>
			root.render(
				<DiscoveryActivity
					game={{
						response_kind: "semantic_grouping",
						command_token: "opaque",
						members: [{ member_id: "m1", text_en: "Kovil" }],
						groups: [{ group_id: "g1", text_en: "Places" }],
					}}
					onResponse={onResponse}
				/>,
			),
		);
		const buttons = container.querySelectorAll("button");
		await act(async () => {
			(buttons[0] as HTMLButtonElement).click();
		});
		await act(async () => {
			(buttons[1] as HTMLButtonElement).click();
		});
		expect(onResponse).toHaveBeenCalledOnce();
		await act(async () => root.unmount());
	});
});
