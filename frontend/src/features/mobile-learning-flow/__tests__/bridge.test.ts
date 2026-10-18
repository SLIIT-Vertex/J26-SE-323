import { describe, expect, it } from "vitest";
import type { HalfSetManifest, SceneDomainEvent } from "../bridge/contracts";
import { MobileLearningBridge } from "../bridge/MobileLearningBridge";
import { HalfSetSceneController } from "../game/HalfSetSceneController";
import { hasMountedGame, releaseGameHost, reserveGameHost } from "../game/createHalfSetGame";

const manifest: HalfSetManifest = {
	schemaVersion: "half-set-manifest-v1",
	activityId: "half",
	revisionId: "support@v1",
	deterministicSeed: 31,
	totalObjects: 6,
	groupCount: 2,
	objectLabelSi: "බෝලය",
	instructionSi: "කාණ්ඩ කරන්න",
};

describe("React–Phaser bridge", () => {
	it("validates lifecycle commands and completely clears support before independent work", () => {
		const bridge = new MobileLearningBridge();
		const events: string[] = [];
		bridge.onEvent((event) => events.push(event.type));
		const controller = new HalfSetSceneController((event) =>
			bridge.emit(event),
		);
		const off = bridge.onCommand((command) => controller.apply(command));
		bridge.command({ type: "load_manifest", manifest });
		bridge.command({ type: "start" });
		bridge.command({
			type: "present_temporary_support",
			titleSi: "උදව්",
			stepsSi: ["පියවර"],
		});
		expect(controller.supportCleared).toBe(false);
		bridge.command({
			type: "withdraw_support",
			requestId: "withdrawal-request",
			supportRevisionId: manifest.revisionId,
		});
		expect(controller.supportCleared).toBe(true);
		expect(controller.accessibilityAnnouncement).toBe("");
		bridge.command({
			type: "present_independent_activity",
			manifest: { ...manifest, revisionId: "after@v1", deterministicSeed: 32 },
		});
		expect(controller.supportCleared).toBe(true);
		expect(events).not.toContain("withdrawal_acknowledged");
		bridge.command({ type: "dispose" });
		off();
		bridge.dispose();
		expect(bridge.listenerCount).toBe(0);
	});

	it("emits completion only for a complete equal grouping", () => {
		const events: SceneDomainEvent[] = [];
		const controller = new HalfSetSceneController((event) => events.push(event));
		controller.apply({ type: "load_manifest", manifest });
		controller.apply({ type: "start" });
		const ids = Object.keys(controller.placements);
		for (const id of ids.slice(0, 5)) controller.place(id, 0);
		expect(controller.submit()).toBe(false);
		controller.place(ids[5], 1);
		expect(controller.submit()).toBe(false);
		for (const id of ids.slice(0, 3)) controller.place(id, 1);
		for (const id of ids.slice(3)) controller.place(id, 0);
		expect(controller.submit()).toBe(true);
		expect(events.filter((event) => event.type === "support_interaction_completed"))
			.toHaveLength(1);
	});

	it("produces deterministic object order, supports restore, and rejects stale snapshots", () => {
		const first = new HalfSetSceneController(() => undefined);
		const second = new HalfSetSceneController(() => undefined);
		first.apply({ type: "load_manifest", manifest });
		second.apply({ type: "load_manifest", manifest });
		expect(Object.keys(first.placements)).toEqual(
			Object.keys(second.placements),
		);
		first.apply({ type: "start" });
		first.place(Object.keys(first.placements)[0], 0);
		const snapshot = first.snapshot();
		second.apply({ type: "restore", snapshot });
		expect(second.snapshot()).toEqual(snapshot);
		expect(() =>
			second.apply({
				type: "restore",
				snapshot: { ...snapshot, manifestRevisionId: "old" },
			}),
		).toThrow("RESTORE_VERSION_CONFLICT");
	});

	it("allows only one Phaser instance reservation per host and releases it on cleanup", () => {
		const host = document.createElement("div");
		reserveGameHost(host);
		expect(hasMountedGame(host)).toBe(true);
		expect(() => reserveGameHost(host)).toThrow("PHASER_INSTANCE_ALREADY_MOUNTED");
		releaseGameHost(host);
		expect(hasMountedGame(host)).toBe(false);
	});

	it("pauses interaction while backgrounded and resumes without losing state", () => {
		const events: string[] = [];
		const controller = new HalfSetSceneController((event) =>
			events.push(event.type),
		);
		controller.apply({ type: "load_manifest", manifest });
		controller.apply({ type: "start" });
		const id = Object.keys(controller.placements)[0];
		controller.apply({ type: "pause" });
		controller.place(id, 0);
		expect(controller.placements[id]).toBeNull();
		controller.apply({ type: "resume" });
		controller.place(id, 0);
		expect(controller.placements[id]).toBe(0);
		expect(events).toEqual(
			expect.arrayContaining(["scene_paused", "scene_resumed"]),
		);
	});
});
