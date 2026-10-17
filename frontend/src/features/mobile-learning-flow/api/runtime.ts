import type {
	ChildEpisodeResponse,
	DraftMissionCatalog,
	DraftMissionRecord,
	DraftTemplateId,
	HeldOutcomeSlot,
	MathematicsOutcomeSlot,
	PresentationManifest,
	SinhalaDraftItemSlot,
	SupportView,
	TelemetryAcknowledgement,
} from "./generated";

const researchOnlyKeys = new Set([
	"correct_option_id",
	"rubric",
	"misconception",
	"probabilities",
	"raw_independence_gain",
	"percentage_point_value",
	"policy_update_status",
	"exclusion_reasons",
	"propensity",
]);

export class ContractError extends Error {
	constructor(readonly code: string) {
		super(code);
	}
}

function object(value: unknown): Record<string, unknown> {
	if (!value || typeof value !== "object" || Array.isArray(value)) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return value as Record<string, unknown>;
}

function text(value: unknown): string {
	if (typeof value !== "string" || value.length === 0) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return value;
}

function noPrivateFields(value: unknown): void {
	if (!value || typeof value !== "object") return;
	for (const [key, child] of Object.entries(value)) {
		if (researchOnlyKeys.has(key))
			throw new ContractError("RESEARCH_FIELD_EXPOSURE");
		noPrivateFields(child);
	}
}

function parseManifest(value: unknown): PresentationManifest | null {
	if (value === null || value === undefined) return null;
	const row = object(value);
	const role = text(row.measurement_role);
	if (
		![
			"practice",
			"unsupported_before",
			"supported_practice",
			"unsupported_after",
			"retention",
		].includes(role)
	) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	if (row.assistance_state !== "none")
		throw new ContractError("UNSUPPORTED_ASSISTANCE_ACTIVE");
	if (!Array.isArray(row.options) || row.options.length < 2) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		presentation_id: text(row.presentation_id),
		revision_id: text(row.revision_id),
		measurement_role: role as PresentationManifest["measurement_role"],
		assistance_state: "none",
		prompt_si: text(row.prompt_si),
		accessibility_label_si: text(row.accessibility_label_si),
		options: row.options.map((entry) => {
			const option = object(entry);
			return {
				option_id: text(option.option_id),
				text_si: text(option.text_si),
			};
		}),
		content_version: text(row.content_version),
	};
}

function parseSupport(value: unknown): SupportView | null {
	if (value === null || value === undefined) return null;
	const row = object(value);
	const game = object(row.game_manifest);
	const scaffoldType = text(row.scaffold_type);
	if (
		![
			"visual_guidance",
			"worked_parallel_example",
			"step_by_step_guidance",
		].includes(scaffoldType)
	) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	if (
		!Array.isArray(row.body_si) ||
		row.body_si.some((line) => typeof line !== "string")
	) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	const deterministicSeed = Number(game.deterministic_seed);
	const totalObjects = Number(game.total_objects);
	const groupCount = Number(game.group_count);
	const maximumSteps = Number(row.maximum_steps);
	if (
		game.schema_version !== "half-set-manifest-v1" ||
		!Number.isSafeInteger(deterministicSeed) ||
		!Number.isSafeInteger(totalObjects) ||
		totalObjects < 2 ||
		totalObjects > 40 ||
		totalObjects % 2 !== 0 ||
		groupCount !== 2 ||
		!Number.isSafeInteger(maximumSteps) ||
		maximumSteps < 1 ||
		maximumSteps > 20
	) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		scaffold_id: text(row.scaffold_id),
		revision_id: text(row.revision_id),
		scaffold_type: scaffoldType as SupportView["scaffold_type"],
		title_si: text(row.title_si),
		body_si: row.body_si as string[],
		visual_alt_text_si:
			row.visual_alt_text_si === null ? null : text(row.visual_alt_text_si),
		maximum_steps: maximumSteps,
		game_manifest: {
			schema_version: "half-set-manifest-v1",
			activity_id: text(game.activity_id),
			revision_id: text(game.revision_id),
			deterministic_seed: deterministicSeed,
			total_objects: totalObjects,
			group_count: 2,
			object_label_si: text(game.object_label_si),
			instruction_si: text(game.instruction_si),
		},
	};
}

export function parseChildEpisodeResponse(
	value: unknown,
): ChildEpisodeResponse {
	noPrivateFields(value);
	const row = object(value);
	const reward = row.reward == null ? null : object(row.reward);
	return {
		episode_id: text(row.episode_id),
		status: text(row.status),
		manifest: parseManifest(row.manifest),
		support: parseSupport(row.support),
		reward: reward
			? { points: Number(reward.points), reason: text(reward.reason) }
			: null,
	};
}

export function parseTelemetryAcknowledgement(
	value: unknown,
): TelemetryAcknowledgement {
	const row = object(value);
	return {
		accepted: Number(row.accepted),
		duplicates: Number(row.duplicates),
		next_sequence: Number(row.next_sequence),
	};
}

const answerKeyFields = new Set([
	"accepted_response",
	"answer_key",
	"correct_option_id",
	"server_answer_keys",
]);

const draftTemplates = new Set<DraftTemplateId>([
	"market_mission",
	"half_set",
	"pattern_temple",
	"parcel_workshop",
	"word_workshop",
	"story_studio",
	"eco_explorer",
]);

function rejectAnswerKeys(value: unknown): void {
	if (Array.isArray(value)) {
		for (const child of value) rejectAnswerKeys(child);
		return;
	}
	if (!value || typeof value !== "object") return;
	for (const [key, child] of Object.entries(value)) {
		if (answerKeyFields.has(key)) throw new ContractError("ANSWER_KEY_EXPOSURE");
		rejectAnswerKeys(child);
	}
}

function bool(value: unknown): boolean {
	if (typeof value !== "boolean") {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return value;
}

function same<T extends string | boolean>(value: unknown, expected: T): T {
	if (value !== expected) throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	return expected;
}

function slotList<T>(
	value: unknown,
	parse: (row: Record<string, unknown>) => T,
): T[] {
	if (value === undefined) return [];
	if (!Array.isArray(value)) throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	return value.map((entry) => parse(object(entry)));
}

function parseMathematicsSlot(row: Record<string, unknown>): MathematicsOutcomeSlot {
	return {
		node_id: text(row.node_id),
		parent_area_id: text(row.parent_area_id),
		trace_competency_id: text(row.trace_competency_id),
		supplied_area_match: bool(row.supplied_area_match),
		confidence: same(row.confidence, "medium"),
		draft_item: same(row.draft_item, true),
		publication_status: same(row.publication_status, "blocked"),
		item_text: text(row.item_text),
	};
}

function parseSinhalaDraftSlot(row: Record<string, unknown>): SinhalaDraftItemSlot {
	return {
		node_id: text(row.node_id),
		parent_area_id: text(row.parent_area_id),
		confidence: same(row.confidence, "high"),
		draft_item: same(row.draft_item, true),
		publication_status: same(row.publication_status, "blocked"),
		area_match: bool(row.area_match),
		item_text: text(row.item_text),
	};
}

function parseHeldSlot(row: Record<string, unknown>): HeldOutcomeSlot {
	if (row.child_question !== null) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		node_id: text(row.node_id),
		parent_area_id: text(row.parent_area_id),
		confidence: same(row.confidence, "low"),
		held: same(row.held, true),
		draft_item: same(row.draft_item, false),
		publication_status: same(row.publication_status, "blocked"),
		traced_text: text(row.traced_text),
		child_question: null,
	};
}

export function parseDraftMissionRecord(value: unknown): DraftMissionRecord {
	rejectAnswerKeys(value);
	const row = object(value);
	const templateId = text(row.template_id);
	if (!draftTemplates.has(templateId as DraftTemplateId)) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		area_id: text(row.area_id),
		cited_node_id: text(row.cited_node_id),
		template_id: templateId as DraftTemplateId,
		development_only: same(row.development_only, true),
		publication_status: same(row.publication_status, "blocked"),
		outcome_slots: slotList(row.outcome_slots, parseMathematicsSlot),
		draft_item_slots: slotList(row.draft_item_slots, parseSinhalaDraftSlot),
		held_slots: slotList(row.held_slots, parseHeldSlot),
	};
}

export function parseDraftMissionCatalog(value: unknown): DraftMissionCatalog {
	rejectAnswerKeys(value);
	const row = object(value);
	if (!Array.isArray(row.missions) || row.missions.length !== 55) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	return {
		package_version: same(row.package_version, "grade5-draft-mission-catalog-v1"),
		development_only: same(row.development_only, true),
		publication_status: same(row.publication_status, "blocked"),
		missions: row.missions.map((mission) => parseDraftMissionRecord(mission)),
	};
}
