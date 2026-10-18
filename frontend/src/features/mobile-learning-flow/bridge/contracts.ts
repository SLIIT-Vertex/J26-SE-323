export const BRIDGE_SCHEMA_VERSION = "mobile-learning-react-phaser-bridge-v1" as const;

export interface HalfSetManifest {
	schemaVersion: "half-set-manifest-v1";
	activityId: string;
	revisionId: string;
	deterministicSeed: number;
	totalObjects: number;
	groupCount: 2;
	objectLabelSi: string;
	instructionSi: string;
}

export type BridgeCommand =
	| { type: "load_manifest"; manifest: HalfSetManifest }
	| { type: "start" }
	| { type: "pause" }
	| { type: "resume" }
	| { type: "restore"; snapshot: SceneSnapshot }
	| { type: "present_temporary_support"; titleSi: string; stepsSi: string[] }
	| {
			type: "withdraw_support";
			requestId: string;
			supportRevisionId: string;
		  }
	| { type: "present_independent_activity"; manifest: HalfSetManifest }
	| {
			type: "apply_server_authoritative_result";
			result: "accepted" | "try_again" | "complete" | "invalid";
	  }
	| { type: "dispose" };

export type SceneDomainEvent =
	| { type: "item_opened" }
	| { type: "object_selected"; objectId: string }
	| { type: "object_moved_or_grouped"; objectId: string; group: 0 | 1 }
	| { type: "placement_changed"; groupedCount: number }
	| { type: "answer_submitted"; groupedCount: number }
	| { type: "retry_started" }
	| { type: "support_step_viewed"; step: number }
	| {
			type: "support_interaction_completed";
			manifestRevisionId: string;
			groupedCount: number;
			groupSizes: [number, number];
		  }
	| {
			type: "withdrawal_acknowledged";
			requestId: string;
			supportRevisionId: string;
			manifestRevisionId: string;
			allSupportRemoved: true;
			answerRevealingStateCleared: true;
			inputHandlersCleared: true;
		  }
	| { type: "scene_paused" }
	| { type: "scene_resumed" }
	| { type: "scene_error"; code: string };

export interface SceneSnapshot {
	manifestRevisionId: string;
	placements: Record<string, 0 | 1 | null>;
	paused: boolean;
}

export interface NormalizedMobileEvent {
	schemaVersion: typeof BRIDGE_SCHEMA_VERSION;
	eventId: string;
	sessionId: string;
	episodeId: string;
	presentationId: string | null;
	sequence: number;
	occurredAt: string;
	event: SceneDomainEvent;
}

const commandTypes = new Set([
	"load_manifest",
	"start",
	"pause",
	"resume",
	"restore",
	"present_temporary_support",
	"withdraw_support",
	"present_independent_activity",
	"apply_server_authoritative_result",
	"dispose",
]);
const eventTypes = new Set([
	"item_opened",
	"object_selected",
	"object_moved_or_grouped",
	"placement_changed",
	"answer_submitted",
	"retry_started",
	"support_step_viewed",
	"support_interaction_completed",
	"withdrawal_acknowledged",
	"scene_paused",
	"scene_resumed",
	"scene_error",
]);

export function assertBridgeCommand(
	value: unknown,
): asserts value is BridgeCommand {
	if (
		!value ||
		typeof value !== "object" ||
		!commandTypes.has(String((value as { type?: unknown }).type))
	) {
		throw new Error("INVALID_BRIDGE_COMMAND");
	}
}

export function assertSceneEvent(
	value: unknown,
): asserts value is SceneDomainEvent {
	if (
		!value ||
		typeof value !== "object" ||
		!eventTypes.has(String((value as { type?: unknown }).type))
	) {
		throw new Error("INVALID_SCENE_EVENT");
	}
}

export function attachEventEnvelope(
	event: SceneDomainEvent,
	context: Omit<
		NormalizedMobileEvent,
		"schemaVersion" | "eventId" | "occurredAt" | "event"
	>,
): NormalizedMobileEvent {
	assertSceneEvent(event);
	return {
		schemaVersion: BRIDGE_SCHEMA_VERSION,
		eventId: crypto.randomUUID(),
		occurredAt: new Date().toISOString(),
		...context,
		event,
	};
}
