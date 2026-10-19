import type {
	AdditionAdventureSupportManifest,
	CapacityAdventureSupportManifest,
	ChildEpisodeResponse,
	DecimalAdventureSupportManifest,
	DirectionAdventureSupportManifest,
	DistanceAdventureSupportManifest,
	DivisionAdventureSupportManifest,
	DraftMissionCatalog,
	DraftMissionRecord,
	DraftTemplateId,
	FractionAdventureSupportManifest,
	HeldOutcomeSlot,
	MassAdventureSupportManifest,
	MathematicsOutcomeSlot,
	MoneyAdventureSupportManifest,
	MultiplicationAdventureSupportManifest,
	NumberPatternSupportManifest,
	NumberWorldSupportManifest,
	PresentationManifest,
	RomanAdventureSupportManifest,
	ServerScore,
	ShapeAdventureSupportManifest,
	SinhalaDraftItemSlot,
	SubtractionAdventureSupportManifest,
	SupportView,
	TelemetryAcknowledgement,
	TimeAdventureSupportManifest,
} from "./generated";

export type { ServerScore } from "./generated";

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
	if (!Array.isArray(row.options)) {
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
		game:
			row.game == null
				? null
				: (() => {
						const game = object(row.game);
						if (
							game.schema_version !== "number-world-item-v1" &&
							game.schema_version !== "addition-adventure-item-v1" &&
							game.schema_version !== "number-pattern-item-v1" &&
							game.schema_version !== "subtraction-adventure-item-v1" &&
							game.schema_version !== "fraction-adventure-item-v1" &&
							game.schema_version !== "multiplication-adventure-item-v1" &&
							game.schema_version !== "time-adventure-item-v1" &&
							game.schema_version !== "division-adventure-item-v1" &&
							game.schema_version !== "distance-adventure-item-v1" &&
							game.schema_version !== "money-adventure-item-v1" &&
							game.schema_version !== "capacity-adventure-item-v1" &&
							game.schema_version !== "mass-adventure-item-v1" &&
							game.schema_version !== "shape-adventure-item-v1" &&
							game.schema_version !== "direction-adventure-item-v1" &&
							game.schema_version !== "decimal-adventure-item-v1" &&
							game.schema_version !== "roman-adventure-item-v1"
						) {
							throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
						}
						const chapter = text(game.chapter);
						const allowedChapters =
							game.schema_version === "number-world-item-v1"
								? [
										"place_value_harbour",
										"firefly_abacus",
										"kite_workshop",
										"river_route_rally",
									]
								: game.schema_version === "addition-adventure-item-v1"
									? [
											"fruit_catch",
											"tuk_tuk_journey",
											"carrying_crane",
											"market_delivery_planner",
											"festival_data_detective",
										]
									: game.schema_version === "number-pattern-item-v1"
										? [
												"number_step_trail",
												"multiplication_bridge",
												"pattern_power_machine",
											]
										: game.schema_version === "subtraction-adventure-item-v1"
											? [
													"place_value_board",
													"regrouping_workshop",
													"difference_story",
												]
											: game.schema_version ===
													"multiplication-adventure-item-v1"
												? ["table_explorer", "column_workshop", "story_mission"]
												: game.schema_version === "time-adventure-item-v1"
													? [
															"time_tools",
															"twenty_four_hour_mission",
															"time_journey",
														]
													: game.schema_version === "division-adventure-item-v1"
														? [
																"equal_share",
																"paper_division",
																"division_story",
															]
														: game.schema_version ===
																"distance-adventure-item-v1"
															? [
																	"unit_path",
																	"distance_calculation",
																	"distance_problems",
																]
															: game.schema_version ===
																	"money-adventure-item-v1"
																? [
																		"money_recognition",
																		"money_calculation",
																		"little_shop",
																	]
																: game.schema_version ===
																		"capacity-adventure-item-v1"
																	? [
																			"water_laboratory",
																			"litre_machine",
																			"water_delivery",
																		]
																	: game.schema_version ===
																			"roman-adventure-item-v1"
																		? [
																				"roman_match",
																				"emoji_count",
																				"roman_arithmetic",
																			]
																		: game.schema_version ===
																				"shape-adventure-item-v1"
																			? [
																					"shape_table",
																					"orientation_lab",
																					"solid_net_match",
																				]
																			: game.schema_version ===
																					"direction-adventure-item-v1"
																				? [
																						"main_direction_compass",
																						"secondary_direction_compass",
																						"place_direction_scene",
																					]
																				: game.schema_version ===
																						"decimal-adventure-item-v1"
																					? [
																							"decimal_reading_match",
																							"decimal_tenths_shading",
																							"tenths_fraction_to_decimal",
																							"decimal_to_tenths_fraction",
																						]
																					: game.schema_version ===
																							"mass-adventure-item-v1"
																						? [
																								"weighing_station",
																								"kilogram_machine",
																								"market_delivery",
																							]
																						: [
																								"equal_share_studio",
																								"quarter_orchard",
																								"tenths_mosaic",
																							];
						if (!allowedChapters.includes(chapter))
							throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
						return game as PresentationManifest["game"];
					})(),
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
	const requiredActions = Number(game.required_actions);
	const isAdaptiveGame = [
		"number-world-support-v1",
		"addition-adventure-support-v1",
		"number-pattern-support-v1",
		"subtraction-adventure-support-v1",
		"fraction-adventure-support-v1",
		"multiplication-adventure-support-v1",
		"time-adventure-support-v1",
		"division-adventure-support-v1",
		"distance-adventure-support-v1",
		"money-adventure-support-v1",
		"capacity-adventure-support-v1",
		"mass-adventure-support-v1",
		"shape-adventure-support-v1",
		"direction-adventure-support-v1",
		"decimal-adventure-support-v1",
		"roman-adventure-support-v1",
	].includes(String(game.schema_version));
	if (
		(!isAdaptiveGame && game.schema_version !== "half-set-manifest-v1") ||
		!Number.isSafeInteger(deterministicSeed) ||
		(!isAdaptiveGame &&
			(!Number.isSafeInteger(totalObjects) ||
				totalObjects < 2 ||
				totalObjects > 40 ||
				totalObjects % 2 !== 0 ||
				groupCount !== 2)) ||
		(isAdaptiveGame &&
			(!Number.isSafeInteger(requiredActions) ||
				requiredActions < 1 ||
				requiredActions > 6 ||
				!Array.isArray(game.parallel_values) ||
				game.parallel_values.some(
					(value) => !Number.isSafeInteger(Number(value)),
				))) ||
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
		game_manifest: (isAdaptiveGame
			? game.schema_version === "number-world-support-v1"
				? {
						schema_version: "number-world-support-v1",
						activity_id: text(game.activity_id),
						revision_id: text(game.revision_id),
						deterministic_seed: deterministicSeed,
						skill_id: text(game.skill_id),
						scaffold_type: scaffoldType as SupportView["scaffold_type"],
						renderer_id: text(game.renderer_id),
						parallel_example_id: text(game.parallel_example_id),
						parallel_example_version:
							game.parallel_example_version === "v1"
								? "v1"
								: (() => {
										throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
									})(),
						parallel_values: Array.isArray(game.parallel_values)
							? game.parallel_values.map(Number)
							: [],
						required_actions: requiredActions,
						focus_step_index: Number.isSafeInteger(
							Number(game.focus_step_index),
						)
							? Number(game.focus_step_index)
							: undefined,
						worked_example: (() => {
							const worked = object(game.worked_example);
							const workedGame = object(worked.game);
							const response = object(worked.correct_response);
							if (
								worked.mode !== "exact_failed_activity" ||
								workedGame.schema_version !== "number-world-item-v1" ||
								typeof response.kind !== "string" ||
								!Array.isArray(worked.steps_si) ||
								worked.steps_si.some((step) => typeof step !== "string")
							)
								throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
							return {
								mode: "exact_failed_activity",
								prompt_si: text(worked.prompt_si),
								game: workedGame as NumberWorldSupportManifest["worked_example"]["game"],
								correct_response:
									response as unknown as NumberWorldSupportManifest["worked_example"]["correct_response"],
								steps_si: worked.steps_si as string[],
							};
						})(),
					}
				: {
						schema_version: game.schema_version as
							| "addition-adventure-support-v1"
							| "number-pattern-support-v1"
							| "subtraction-adventure-support-v1"
							| "fraction-adventure-support-v1"
							| "multiplication-adventure-support-v1"
							| "time-adventure-support-v1"
							| "division-adventure-support-v1"
							| "distance-adventure-support-v1"
							| "money-adventure-support-v1"
							| "capacity-adventure-support-v1"
							| "mass-adventure-support-v1"
							| "shape-adventure-support-v1"
							| "direction-adventure-support-v1"
							| "decimal-adventure-support-v1"
							| "roman-adventure-support-v1",
						activity_id: text(game.activity_id),
						revision_id: text(game.revision_id),
						deterministic_seed: deterministicSeed,
						skill_id: text(game.skill_id),
						scaffold_type: scaffoldType as SupportView["scaffold_type"],
						renderer_id: text(game.renderer_id),
						parallel_example_id: text(game.parallel_example_id),
						parallel_example_version:
							game.parallel_example_version === "v1"
								? "v1"
								: (() => {
										throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
									})(),
						parallel_values: Array.isArray(game.parallel_values)
							? game.parallel_values.map(Number)
							: [],
						required_actions: requiredActions,
						focus_step_index: Number.isSafeInteger(
							Number(game.focus_step_index),
						)
							? Number(game.focus_step_index)
							: undefined,
						focus_column:
							typeof game.focus_column === "string"
								? game.focus_column
								: undefined,
						worked_example: (() => {
							const worked = object(game.worked_example);
							const workedGame = object(worked.game);
							const response =
								worked.correct_response === null
									? null
									: object(worked.correct_response);
							if (
								worked.mode !== "exact_failed_activity" ||
								workedGame.schema_version !==
									(game.schema_version === "number-pattern-support-v1"
										? "number-pattern-item-v1"
										: game.schema_version === "subtraction-adventure-support-v1"
											? "subtraction-adventure-item-v1"
											: game.schema_version === "fraction-adventure-support-v1"
												? "fraction-adventure-item-v1"
												: game.schema_version ===
														"multiplication-adventure-support-v1"
													? "multiplication-adventure-item-v1"
													: game.schema_version === "time-adventure-support-v1"
														? "time-adventure-item-v1"
														: game.schema_version ===
																"division-adventure-support-v1"
															? "division-adventure-item-v1"
															: game.schema_version ===
																	"distance-adventure-support-v1"
																? "distance-adventure-item-v1"
																: game.schema_version ===
																		"money-adventure-support-v1"
																	? "money-adventure-item-v1"
																	: game.schema_version ===
																			"capacity-adventure-support-v1"
																		? "capacity-adventure-item-v1"
																		: game.schema_version ===
																				"shape-adventure-support-v1"
																			? "shape-adventure-item-v1"
																			: game.schema_version ===
																					"direction-adventure-support-v1"
																				? "direction-adventure-item-v1"
																				: game.schema_version ===
																						"decimal-adventure-support-v1"
																					? "decimal-adventure-item-v1"
																					: game.schema_version ===
																							"roman-adventure-support-v1"
																						? "roman-adventure-item-v1"
																						: game.schema_version ===
																								"mass-adventure-support-v1"
																							? "mass-adventure-item-v1"
																							: "addition-adventure-item-v1") ||
								(response !== null && typeof response.kind !== "string") ||
								!Array.isArray(worked.steps_si) ||
								worked.steps_si.some((step) => typeof step !== "string")
							)
								throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
							return {
								mode: "exact_failed_activity",
								prompt_si: text(worked.prompt_si),
								game: workedGame as
									| AdditionAdventureSupportManifest["worked_example"]["game"]
									| NumberPatternSupportManifest["worked_example"]["game"]
									| SubtractionAdventureSupportManifest["worked_example"]["game"]
									| FractionAdventureSupportManifest["worked_example"]["game"]
									| MultiplicationAdventureSupportManifest["worked_example"]["game"]
									| TimeAdventureSupportManifest["worked_example"]["game"]
									| DivisionAdventureSupportManifest["worked_example"]["game"]
									| DistanceAdventureSupportManifest["worked_example"]["game"]
									| MoneyAdventureSupportManifest["worked_example"]["game"]
									| CapacityAdventureSupportManifest["worked_example"]["game"]
									| MassAdventureSupportManifest["worked_example"]["game"]
									| ShapeAdventureSupportManifest["worked_example"]["game"]
									| DirectionAdventureSupportManifest["worked_example"]["game"]
									| DecimalAdventureSupportManifest["worked_example"]["game"]
									| RomanAdventureSupportManifest["worked_example"]["game"],
								correct_response: response as
									| AdditionAdventureSupportManifest["worked_example"]["correct_response"]
									| NumberPatternSupportManifest["worked_example"]["correct_response"]
									| SubtractionAdventureSupportManifest["worked_example"]["correct_response"]
									| FractionAdventureSupportManifest["worked_example"]["correct_response"]
									| MultiplicationAdventureSupportManifest["worked_example"]["correct_response"]
									| TimeAdventureSupportManifest["worked_example"]["correct_response"]
									| DivisionAdventureSupportManifest["worked_example"]["correct_response"]
									| DistanceAdventureSupportManifest["worked_example"]["correct_response"]
									| MoneyAdventureSupportManifest["worked_example"]["correct_response"]
									| CapacityAdventureSupportManifest["worked_example"]["correct_response"]
									| MassAdventureSupportManifest["worked_example"]["correct_response"]
									| ShapeAdventureSupportManifest["worked_example"]["correct_response"]
									| DirectionAdventureSupportManifest["worked_example"]["correct_response"]
									| DecimalAdventureSupportManifest["worked_example"]["correct_response"]
									| RomanAdventureSupportManifest["worked_example"]["correct_response"],
								steps_si: worked.steps_si as string[],
							};
						})(),
					}
			: {
					schema_version: "half-set-manifest-v1",
					activity_id: text(game.activity_id),
					revision_id: text(game.revision_id),
					deterministic_seed: deterministicSeed,
					total_objects: totalObjects,
					group_count: 2,
					object_label_si: text(game.object_label_si),
					instruction_si: text(game.instruction_si),
				}) as SupportView["game_manifest"],
	};
}

export type ScoredEpisodeResponse = ChildEpisodeResponse;

export function parseChildEpisodeResponse(
	value: unknown,
): ScoredEpisodeResponse {
	noPrivateFields(value);
	const row = object(value);
	const reward = row.reward == null ? null : object(row.reward);
	const parsed = {
		episode_id: text(row.episode_id),
		status: text(row.status),
		manifest: parseManifest(row.manifest),
		support: parseSupport(row.support),
		reward: reward
			? { points: Number(reward.points), reason: text(reward.reason) }
			: null,
	};
	const serverScore = parseServerScore(row.server_score);
	return serverScore ? { ...parsed, server_score: serverScore } : parsed;
}

function parseServerScore(value: unknown): ServerScore | null {
	if (value == null) return null;
	const row = object(value);
	if (row.server_authoritative !== true) {
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	}
	const parsed: ServerScore = {
		earned_score: text(row.earned_score),
		maximum_score: text(row.maximum_score),
		scoring_version: text(row.scoring_version),
		server_authoritative: true,
		measurement_role: text(row.measurement_role),
		correct: row.correct === true,
	};
	if (row.attempt_id != null) parsed.attempt_id = text(row.attempt_id);
	if (row.presentation_id != null)
		parsed.presentation_id = text(row.presentation_id);
	if (row.item_revision_id != null)
		parsed.item_revision_id = text(row.item_revision_id);
	if (row.feedback_step_index != null) {
		const feedbackStep = Number(row.feedback_step_index);
		if (
			!Number.isSafeInteger(feedbackStep) ||
			feedbackStep < 0 ||
			feedbackStep > 2
		)
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		parsed.feedback_step_index = feedbackStep;
	}
	if (row.feedback_column != null)
		parsed.feedback_column = text(row.feedback_column);
	return parsed;
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
		if (answerKeyFields.has(key))
			throw new ContractError("ANSWER_KEY_EXPOSURE");
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
	if (value !== expected)
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	return expected;
}

function slotList<T>(
	value: unknown,
	parse: (row: Record<string, unknown>) => T,
): T[] {
	if (value === undefined) return [];
	if (!Array.isArray(value))
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	return value.map((entry) => parse(object(entry)));
}

function parseMathematicsSlot(
	row: Record<string, unknown>,
): MathematicsOutcomeSlot {
	return {
		node_id: text(row.node_id),
		parent_area_id: text(row.parent_area_id),
		trace_competency_id: text(row.trace_competency_id),
		supplied_area_match: bool(row.supplied_area_match),
		confidence: same(row.confidence, "medium"),
		draft_item: same(row.draft_item, true),
		item_text: text(row.item_text),
	};
}

function parseSinhalaDraftSlot(
	row: Record<string, unknown>,
): SinhalaDraftItemSlot {
	return {
		node_id: text(row.node_id),
		parent_area_id: text(row.parent_area_id),
		confidence: same(row.confidence, "high"),
		draft_item: same(row.draft_item, true),
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
		package_version: same(
			row.package_version,
			"grade5-draft-mission-catalog-v1",
		),
		missions: row.missions.map((mission) => parseDraftMissionRecord(mission)),
	};
}
