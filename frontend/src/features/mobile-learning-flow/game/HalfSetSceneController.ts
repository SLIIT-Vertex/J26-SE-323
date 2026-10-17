import type {
	BridgeCommand,
	HalfSetManifest,
	SceneDomainEvent,
	SceneSnapshot,
} from "../bridge/contracts";

type Emit = (event: SceneDomainEvent) => void;

export class HalfSetSceneController {
	manifest: HalfSetManifest | null = null;
	placements: Record<string, 0 | 1 | null> = {};
	support: { titleSi: string; stepsSi: string[] } | null = null;
	accessibilityAnnouncement = "";
	paused = false;
	disposed = false;
	started = false;

	constructor(private readonly emit: Emit) {}

	apply(command: BridgeCommand): void {
		if (command.type === "dispose") {
			this.clearSupport();
			this.placements = {};
			this.manifest = null;
			this.disposed = true;
			return;
		}
		if (this.disposed) throw new Error("SCENE_DISPOSED");
		switch (command.type) {
			case "load_manifest":
			case "present_independent_activity":
				this.validateManifest(command.manifest);
				this.clearSupport();
				this.manifest = command.manifest;
				this.placements = this.seededPlacements(command.manifest);
				break;
			case "start":
				if (!this.manifest) throw new Error("MANIFEST_REQUIRED");
				this.started = true;
				this.emit({ type: "item_opened" });
				break;
			case "pause":
				this.paused = true;
				this.emit({ type: "scene_paused" });
				break;
			case "resume":
				this.paused = false;
				this.emit({ type: "scene_resumed" });
				break;
			case "restore":
				this.restore(command.snapshot);
				break;
			case "present_temporary_support":
				this.support = {
					titleSi: command.titleSi,
					stepsSi: [...command.stepsSi],
				};
				this.accessibilityAnnouncement = command.stepsSi[0] ?? command.titleSi;
				this.emit({ type: "support_step_viewed", step: 1 });
				break;
			case "withdraw_support":
				this.clearSupport();
				this.placements = {};
				this.started = false;
				break;
			case "apply_server_authoritative_result":
				if (command.result === "try_again")
					this.emit({ type: "retry_started" });
				break;
		}
	}

	place(objectId: string, group: 0 | 1): void {
		if (!this.canInteract() || !(objectId in this.placements)) return;
		this.emit({ type: "object_selected", objectId });
		this.placements[objectId] = group;
		this.emit({ type: "object_moved_or_grouped", objectId, group });
		this.emit({ type: "placement_changed", groupedCount: this.groupedCount });
	}

	submit(): boolean {
		if (!this.canInteract() || !this.manifest) return false;
		const groupSizes: [number, number] = [
			Object.values(this.placements).filter((value) => value === 0).length,
			Object.values(this.placements).filter((value) => value === 1).length,
		];
		this.emit({ type: "answer_submitted", groupedCount: this.groupedCount });
		const complete =
			this.groupedCount === this.manifest.totalObjects &&
			groupSizes[0] === groupSizes[1];
		if (complete) {
			this.emit({
				type: "support_interaction_completed",
				manifestRevisionId: this.manifest.revisionId,
				groupedCount: this.groupedCount,
				groupSizes,
			});
		}
		return complete;
	}

	snapshot(): SceneSnapshot {
		if (!this.manifest) throw new Error("MANIFEST_REQUIRED");
		return {
			manifestRevisionId: this.manifest.revisionId,
			placements: { ...this.placements },
			paused: this.paused,
		};
	}

	get groupedCount(): number {
		return Object.values(this.placements).filter((value) => value !== null)
			.length;
	}

	get supportCleared(): boolean {
		return this.support === null && this.accessibilityAnnouncement === "";
	}

	private canInteract(): boolean {
		return (
			this.started && !this.paused && !this.disposed && this.manifest !== null
		);
	}

	private clearSupport(): void {
		this.support = null;
		this.accessibilityAnnouncement = "";
	}

	private restore(snapshot: SceneSnapshot): void {
		if (
			!this.manifest ||
			snapshot.manifestRevisionId !== this.manifest.revisionId
		) {
			throw new Error("RESTORE_VERSION_CONFLICT");
		}
		this.placements = { ...snapshot.placements };
		this.paused = snapshot.paused;
	}

	private validateManifest(manifest: HalfSetManifest): void {
		if (
			manifest.schemaVersion !== "half-set-manifest-v1" ||
			manifest.groupCount !== 2 ||
			manifest.totalObjects < 2 ||
			manifest.totalObjects > 40 ||
			manifest.totalObjects % 2 !== 0
		) {
			throw new Error("INVALID_HALF_SET_MANIFEST");
		}
	}

	private seededPlacements(manifest: HalfSetManifest): Record<string, null> {
		let state = manifest.deterministicSeed >>> 0;
		const ids = Array.from(
			{ length: manifest.totalObjects },
			(_, index) => `object-${index + 1}`,
		);
		ids.sort(() => {
			state = (1664525 * state + 1013904223) >>> 0;
			return state / 2 ** 32 - 0.5;
		});
		return Object.fromEntries(ids.map((id) => [id, null]));
	}
}
