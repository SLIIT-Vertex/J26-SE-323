import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ClassroomActivity } from "../ClassroomActionQuest";

describe("Classroom Action Quest interactions", () => {
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
	it("offers six pose controls and emits body-state evidence", async () => {
		const onResponse = vi.fn();
		await act(async () => root.render(<ClassroomActivity game={{ response_kind: "body_state", command_id: "stretch_arms", allowed_interaction_ids: ["bend", "stretch_arms", "arms_down", "stand_straight", "turn_around", "sit_down"] }} onResponse={onResponse} />));
		const controls = host.querySelectorAll(".pose-controls button");
		expect(controls).toHaveLength(6);
		await act(async () => (controls[1] as HTMLButtonElement).click());
		expect(onResponse).toHaveBeenCalledWith(expect.objectContaining({ kind: "body_state", semantic_action_id: "stretch_arms" }));
	});
	it("provides semantic tap targets for wall, blackboard and origin", async () => {
		const onResponse = vi.fn();
		await act(async () => root.render(<ClassroomActivity game={{ response_kind: "classroom_navigation", command_id: "run_to_blackboard", origin_id: "start-a", character_start_location: "start-a" }} onResponse={onResponse} />));
		expect(host.querySelectorAll(".destination")).toHaveLength(3);
		await act(async () => (host.querySelector(".destination.blackboard") as HTMLButtonElement).click());
		expect(onResponse).toHaveBeenCalledWith(expect.objectContaining({ kind: "classroom_navigation", final_location_id: "blackboard-zone" }));
		expect(host.style.width).toBe("320px");
	});
});
