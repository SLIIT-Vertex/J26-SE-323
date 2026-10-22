import type {
	AdditionAdventureSupportManifest,
	BloomBuilderSupportManifest,
	BlueprintSupportManifest,
	CapacityAdventureSupportManifest,
	ChildEpisodeResponse,
	ClassroomActionSupportManifest,
	ClassroomLanguageLiveSupportManifest,
	ConversationStreetSupportManifest,
	DecimalAdventureSupportManifest,
	DirectionAdventureSupportManifest,
	DistanceAdventureSupportManifest,
	DivisionAdventureSupportManifest,
	DraftMissionCatalog,
	DraftMissionRecord,
	DraftTemplateId,
	EarthSkySupportManifest,
	EverydayObjectSupportManifest,
	FamilyConstellationSupportManifest,
	FractionAdventureSupportManifest,
	HeldOutcomeSlot,
	HeritageMuseumSupportManifest,
	InformationStationSupportManifest,
	IslandFoodSupportManifest,
	LearnerStateAction,
	MassAdventureSupportManifest,
	MathematicsOutcomeSlot,
	MoneyAdventureSupportManifest,
	MultiplicationAdventureSupportManifest,
	NumberPatternSupportManifest,
	NumberWorldSupportManifest,
	PlantExplorerSupportManifest,
	PresentationManifest,
	RainbowWardrobeSupportManifest,
	RomanAdventureSupportManifest,
	ServerScore,
	ShapeAdventureSupportManifest,
	SinhalaDraftItemSlot,
	SriLankaDiscoverySupportManifest,
	SubtractionAdventureSupportManifest,
	SupportAnswer,
	SupportGuidancePair,
	SupportLesson,
	SupportView,
	TelemetryAcknowledgement,
	TimeAdventureSupportManifest,
	TransitTerminalSupportManifest,
	WaterWorksSupportManifest,
	WildlifeRangerSupportManifest,
	WorkplaceLinkSupportManifest,
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
							game.schema_version !== "roman-adventure-item-v1" &&
							game.schema_version !== "classroom-action-item-v1" &&
							game.schema_version !== "sri-lanka-discovery-item-v1" &&
							game.schema_version !== "plant-explorer-item-v1" &&
							game.schema_version !== "wildlife-ranger-item-v1" &&
							game.schema_version !== "everyday-object-quest-item-v1" &&
							game.schema_version !== "island-food-festival-item-v1" &&
							game.schema_version !== "water-works-adventure-item-v1" &&
							game.schema_version !== "transit-terminal-quest-item-v1" &&
							game.schema_version !== "rainbow-wardrobe-item-v1" &&
							game.schema_version !== "bloom-builder-garden-item-v1" &&
							game.schema_version !== "workplace-link-city-item-v1" &&
							game.schema_version !== "family-word-constellation-item-v1" &&
							game.schema_version !== "earth-sky-explorer-item-v1" &&
							game.schema_version !== "blueprint-quest-item-v1" &&
							game.schema_version !== "information-station-item-v1" &&
							game.schema_version !== "heritage-museum-item-v1" &&
							game.schema_version !== "classroom-language-live-item-v1" &&
							game.schema_version !== "conversation-street-item-v1" &&
							game.schema_version !== "sinhala-pillam-item-v1" &&
							game.schema_version !== "sinhala-punctuation-item-v1" &&
							game.schema_version !== "sinhala-riddle-item-v1"
						) {
							throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
						}
						const chapter = text(game.chapter);
						const allowedChapters =
							game.schema_version === "sinhala-pillam-item-v1"
								? ["pillam_friends", "akshara_workshop", "compound_garden"]
								: game.schema_version === "sinhala-punctuation-item-v1"
									? [
											"sentence_rail",
											"small_marks_workshop",
											"said_and_extra",
											"short_dash_path",
										]
									: game.schema_version === "sinhala-riddle-item-v1"
										? ["clue_path", "clue_bridge", "word_secret_box"]
										: game.schema_version === "number-world-item-v1"
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
													: game.schema_version ===
															"subtraction-adventure-item-v1"
														? [
																"place_value_board",
																"regrouping_workshop",
																"difference_story",
															]
														: game.schema_version ===
																"multiplication-adventure-item-v1"
															? [
																	"table_explorer",
																	"column_workshop",
																	"story_mission",
																]
															: game.schema_version === "time-adventure-item-v1"
																? [
																		"time_tools",
																		"twenty_four_hour_mission",
																		"time_journey",
																	]
																: game.schema_version ===
																		"division-adventure-item-v1"
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
																								"classroom-action-item-v1"
																							? [
																									"action_mirror",
																									"classroom_dash",
																									"come_back",
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
																										: game.schema_version ===
																												"sri-lanka-discovery-item-v1"
																											? [
																													"word_explorer",
																													"national_gallery",
																													"community_sort",
																												]
																											: game.schema_version ===
																													"plant-explorer-item-v1"
																												? [
																														"garden_word_hunt",
																														"build_a_plant",
																														"one_or_many",
																													]
																												: game.schema_version ===
																														"wildlife-ranger-item-v1"
																													? [
																															"animal_spotter",
																															"lesson_trail_sort",
																															"body_part_detective",
																														]
																													: game.schema_version ===
																															"everyday-object-quest-item-v1"
																														? [
																																"object_pop",
																																"two_room_tidy",
																																"name_builder",
																															]
																														: game.schema_version ===
																																"island-food-festival-item-v1"
																															? [
																																	"market_match",
																																	"festival_stall_sort",
																																	"recipe_word_kitchen",
																																]
																															: game.schema_version ===
																																	"water-works-adventure-item-v1"
																																? [
																																		"droplet_match",
																																		"pipe_route",
																																		"splash_detective",
																																	]
																																: game.schema_version ===
																																		"transit-terminal-quest-item-v1"
																																	? [
																																			"ticket_match",
																																			"departure_board",
																																			"signal_detective",
																																		]
																																	: game.schema_version ===
																																			"rainbow-wardrobe-item-v1"
																																		? [
																																				"rainbow_wardrobe",
																																			]
																																		: game.schema_version ===
																																				"bloom-builder-garden-item-v1"
																																			? [
																																					"seed_packet_match",
																																					"garden_bed_relay",
																																					"petal_pattern_detective",
																																				]
																																			: game.schema_version ===
																																					"workplace-link-city-item-v1"
																																				? [
																																						"job_badge_match",
																																						"work_route_connector",
																																						"city_network_challenge",
																																					]
																																				: game.schema_version ===
																																						"family-word-constellation-item-v1"
																																					? [
																																							"word_star",
																																							"constellation",
																																						]
																																					: game.schema_version ===
																																							"earth-sky-explorer-item-v1"
																																						? [
																																								"skyword_signal_bridge",
																																								"panorama_label_quest",
																																								"nature_lens_detective",
																																							]
																																						: game.schema_version ===
																																								"blueprint-quest-item-v1"
																																							? [
																																									"place_card_explorer",
																																									"blueprint_zone_sort",
																																									"room_name_workshop",
																																								]
																																							: game.schema_version ===
																																									"information-station-item-v1"
																																								? [
																																										"word_signal_bridge",
																																										"information_object_dock",
																																										"signal_console_challenge",
																																									]
																																								: game.schema_version ===
																																										"heritage-museum-item-v1"
																																									? [
																																											"museum_word_bridge",
																																											"exhibit_label_match",
																																											"curator_lens_challenge",
																																										]
																																									: game.schema_version ===
																																											"classroom-language-live-item-v1"
																																										? [
																																												"phrase_portal_sort",
																																												"command_stage_director",
																																												"situation_bubble_match",
																																												"question_tile_studio",
																																											]
																																										: game.schema_version ===
																																												"conversation-street-item-v1"
																																											? [
																																													"conversation_matchmaker",
																																													"dialogue_director",
																																													"fictional_profile_reply_lab",
																																													"show_and_tell_conversation",
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
			"simpler_same_game",
			"prerequisite_repair",
			"conceptual_reexplanation",
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
	if (game.schema_version === "support-round-v1") {
		const englishTagKey = text(row.english_tag_key);
		const allowedTags = new Set([
			"VISUAL_GUIDANCE",
			"GUIDED_REASONING",
			"WORKED_EXAMPLE",
			"SIMPLER_VERSION",
			"PREREQUISITE_REPAIR",
			"CONCEPTUAL_REEXPLANATION",
		]);
		if (!allowedTags.has(englishTagKey))
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		const stageKind = text(game.stage_kind);
		if (!["practice", "target", "view"].includes(stageKind))
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		const activity =
			game.activity == null
				? null
				: (() => {
						const source = object(game.activity);
						const parsed = parseManifest({
							presentation_id: source.presentation_id,
							revision_id: source.revision_id,
							measurement_role: "supported_practice",
							assistance_state: "none",
							prompt_si: source.prompt_si,
							accessibility_label_si: source.prompt_si,
							options: [],
							content_version: "support-round-v1",
							game: source.game,
						});
						if (
							!parsed?.game ||
							typeof source.returns_to_failed_item !== "boolean"
						)
							throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
						return {
							presentation_id: parsed.presentation_id,
							revision_id: parsed.revision_id,
							skill_id: text(source.skill_id),
							prompt_si: parsed.prompt_si,
							game: parsed.game,
							returns_to_failed_item: source.returns_to_failed_item,
							answer: supportAnswer(source.answer),
						};
					})();
		const worked =
			game.worked_example == null
				? null
				: (() => {
						const source = object(game.worked_example);
						const parsed = parseManifest({
							presentation_id: source.presentation_id,
							revision_id: source.revision_id,
							measurement_role: "supported_practice",
							assistance_state: "none",
							prompt_si: source.prompt_si,
							accessibility_label_si: source.prompt_si,
							options: [],
							content_version: "support-round-v1",
							game: source.game,
						});
						if (!parsed?.game || !Array.isArray(source.steps_si))
							throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
						return {
							presentation_id: parsed.presentation_id,
							revision_id: parsed.revision_id,
							skill_id: text(source.skill_id),
							prompt_si: parsed.prompt_si,
							game: parsed.game,
							steps_si: source.steps_si.map(text),
							solution: object(source.solution) as never,
							answer: supportAnswer(source.answer),
						};
					})();
		const cues = Array.isArray(game.cues_si) ? game.cues_si.map(text) : null;
		const roundNumber = Number(game.round_number);
		const stageIndex = Number(game.stage_index);
		const stageCount = Number(game.stage_count);
		if (
			!cues ||
			!Number.isSafeInteger(roundNumber) ||
			roundNumber < 1 ||
			!Number.isSafeInteger(stageIndex) ||
			stageIndex < 0 ||
			!Number.isSafeInteger(stageCount) ||
			stageCount < 1 ||
			stageIndex >= stageCount ||
			// A demonstration shows a worked example, or the child's own board solved (maths
			// visual guidance); every other stage is played on an activity.
			(stageKind === "view"
				? worked === null && activity === null
				: activity === null)
		)
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		return {
			scaffold_id: text(row.scaffold_id),
			revision_id: text(row.revision_id),
			scaffold_type: scaffoldType as SupportView["scaffold_type"],
			english_tag_key: englishTagKey as NonNullable<
				SupportView["english_tag_key"]
			>,
			title_si: text(row.title_si),
			body_si: row.body_si as string[],
			visual_alt_text_si:
				row.visual_alt_text_si === null ? null : text(row.visual_alt_text_si),
			maximum_steps: maximumSteps,
			game_manifest: {
				schema_version: "support-round-v1",
				activity_id: text(game.activity_id),
				revision_id: text(game.revision_id),
				deterministic_seed: Number(game.deterministic_seed),
				skill_id: text(game.skill_id),
				scaffold_type: scaffoldType as SupportView["scaffold_type"],
				english_tag_key: englishTagKey as NonNullable<
					SupportView["english_tag_key"]
				>,
				renderer_id: text(game.renderer_id),
				parallel_example_id: text(game.parallel_example_id),
				parallel_example_version: "v1",
				parallel_values: [],
				required_actions: 1,
				round_number: roundNumber,
				stage_index: stageIndex,
				stage_count: stageCount,
				stage_kind: stageKind as "practice" | "target" | "view",
				cues_si: cues,
				guidance: supportGuidance(game.guidance),
				lesson: supportLesson(game.lesson),
				activity,
				worked_example: worked,
			},
		};
	}
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
		"classroom-action-support-v1",
		"sri-lanka-discovery-support-v1",
		"plant-explorer-support-v1",
		"wildlife-ranger-support-v1",
		"everyday-object-quest-support-v1",
		"island-food-festival-support-v1",
		"water-works-adventure-support-v1",
		"transit-terminal-quest-support-v1",
		"rainbow-wardrobe-support-v1",
		"bloom-builder-garden-support-v1",
		"workplace-link-city-support-v1",
		"family-word-constellation-support-v1",
		"earth-sky-explorer-support-v1",
		"blueprint-quest-support-v1",
		"information-station-support-v1",
		"heritage-museum-support-v1",
		"classroom-language-live-support-v1",
		"conversation-street-support-v1",
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
							| "roman-adventure-support-v1"
							| "classroom-action-support-v1"
							| "sri-lanka-discovery-support-v1"
							| "plant-explorer-support-v1"
							| "wildlife-ranger-support-v1"
							| "everyday-object-quest-support-v1"
							| "island-food-festival-support-v1"
							| "water-works-adventure-support-v1"
							| "transit-terminal-quest-support-v1"
							| "rainbow-wardrobe-support-v1"
							| "bloom-builder-garden-support-v1"
							| "workplace-link-city-support-v1"
							| "family-word-constellation-support-v1"
							| "earth-sky-explorer-support-v1"
							| "blueprint-quest-support-v1"
							| "information-station-support-v1"
							| "heritage-museum-support-v1"
							| "classroom-language-live-support-v1"
							| "conversation-street-support-v1",
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
																								"classroom-action-support-v1"
																							? "classroom-action-item-v1"
																							: game.schema_version ===
																									"mass-adventure-support-v1"
																								? "mass-adventure-item-v1"
																								: game.schema_version ===
																										"sri-lanka-discovery-support-v1"
																									? "sri-lanka-discovery-item-v1"
																									: game.schema_version ===
																											"plant-explorer-support-v1"
																										? "plant-explorer-item-v1"
																										: game.schema_version ===
																												"wildlife-ranger-support-v1"
																											? "wildlife-ranger-item-v1"
																											: game.schema_version ===
																													"everyday-object-quest-support-v1"
																												? "everyday-object-quest-item-v1"
																												: game.schema_version ===
																														"island-food-festival-support-v1"
																													? "island-food-festival-item-v1"
																													: game.schema_version ===
																															"water-works-adventure-support-v1"
																														? "water-works-adventure-item-v1"
																														: game.schema_version ===
																																"transit-terminal-quest-support-v1"
																															? "transit-terminal-quest-item-v1"
																															: game.schema_version ===
																																	"rainbow-wardrobe-support-v1"
																																? "rainbow-wardrobe-item-v1"
																																: game.schema_version ===
																																		"bloom-builder-garden-support-v1"
																																	? "bloom-builder-garden-item-v1"
																																	: game.schema_version ===
																																			"workplace-link-city-support-v1"
																																		? "workplace-link-city-item-v1"
																																		: game.schema_version ===
																																				"family-word-constellation-support-v1"
																																			? "family-word-constellation-item-v1"
																																			: game.schema_version ===
																																					"earth-sky-explorer-support-v1"
																																				? "earth-sky-explorer-item-v1"
																																				: game.schema_version ===
																																						"blueprint-quest-support-v1"
																																					? "blueprint-quest-item-v1"
																																					: game.schema_version ===
																																							"information-station-support-v1"
																																						? "information-station-item-v1"
																																						: game.schema_version ===
																																								"heritage-museum-support-v1"
																																							? "heritage-museum-item-v1"
																																							: game.schema_version ===
																																									"classroom-language-live-support-v1"
																																								? "classroom-language-live-item-v1"
																																								: game.schema_version ===
																																										"conversation-street-support-v1"
																																									? "conversation-street-item-v1"
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
									| RomanAdventureSupportManifest["worked_example"]["game"]
									| ClassroomActionSupportManifest["worked_example"]["game"]
									| SriLankaDiscoverySupportManifest["worked_example"]["game"]
									| PlantExplorerSupportManifest["worked_example"]["game"]
									| WildlifeRangerSupportManifest["worked_example"]["game"]
									| EverydayObjectSupportManifest["worked_example"]["game"]
									| IslandFoodSupportManifest["worked_example"]["game"]
									| WaterWorksSupportManifest["worked_example"]["game"]
									| TransitTerminalSupportManifest["worked_example"]["game"]
									| RainbowWardrobeSupportManifest["worked_example"]["game"]
									| BloomBuilderSupportManifest["worked_example"]["game"]
									| WorkplaceLinkSupportManifest["worked_example"]["game"]
									| FamilyConstellationSupportManifest["worked_example"]["game"]
									| EarthSkySupportManifest["worked_example"]["game"]
									| BlueprintSupportManifest["worked_example"]["game"]
									| InformationStationSupportManifest["worked_example"]["game"]
									| HeritageMuseumSupportManifest["worked_example"]["game"]
									| ClassroomLanguageLiveSupportManifest["worked_example"]["game"]
									| ConversationStreetSupportManifest["worked_example"]["game"],
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
									| RomanAdventureSupportManifest["worked_example"]["correct_response"]
									| ClassroomActionSupportManifest["worked_example"]["correct_response"]
									| SriLankaDiscoverySupportManifest["worked_example"]["correct_response"]
									| PlantExplorerSupportManifest["worked_example"]["correct_response"]
									| WildlifeRangerSupportManifest["worked_example"]["correct_response"]
									| EverydayObjectSupportManifest["worked_example"]["correct_response"]
									| IslandFoodSupportManifest["worked_example"]["correct_response"]
									| WaterWorksSupportManifest["worked_example"]["correct_response"]
									| TransitTerminalSupportManifest["worked_example"]["correct_response"]
									| RainbowWardrobeSupportManifest["worked_example"]["correct_response"]
									| BloomBuilderSupportManifest["worked_example"]["correct_response"]
									| WorkplaceLinkSupportManifest["worked_example"]["correct_response"]
									| FamilyConstellationSupportManifest["worked_example"]["correct_response"]
									| EarthSkySupportManifest["worked_example"]["correct_response"]
									| BlueprintSupportManifest["worked_example"]["correct_response"]
									| InformationStationSupportManifest["worked_example"]["correct_response"]
									| HeritageMuseumSupportManifest["worked_example"]["correct_response"]
									| ClassroomLanguageLiveSupportManifest["worked_example"]["correct_response"]
									| ConversationStreetSupportManifest["worked_example"]["correct_response"],
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
	const supportRound = parseSupportRoundStatus(row.support_round);
	const learnerStateAction = parseLearnerStateAction(row.learner_state_action);
	return {
		...parsed,
		...(serverScore ? { server_score: serverScore } : {}),
		...(supportRound ? { support_round: supportRound } : {}),
		...(learnerStateAction ? { learner_state_action: learnerStateAction } : {}),
	};
}

const LEARNER_STATE_ACTIONS: readonly LearnerStateAction[] = [
	"none",
	"monitor",
	"request_tutor_support",
	"request_reengagement_support",
	"collect_more_evidence",
];

/** An unknown action is ignored: learner-state is optional evidence and never fails an answer. */
function parseLearnerStateAction(value: unknown): LearnerStateAction | null {
	return LEARNER_STATE_ACTIONS.find((action) => action === value) ?? null;
}

function parseSupportRoundStatus(value: unknown) {
	if (value == null) return null;
	const row = object(value);
	const roundNumber = Number(row.round_number);
	const scaffoldType = text(row.scaffold_type) as NonNullable<
		ChildEpisodeResponse["support_round"]
	>["scaffold_type"];
	const stageKind = row.stage_kind == null ? null : text(row.stage_kind);
	if (
		!Number.isSafeInteger(roundNumber) ||
		roundNumber < 1 ||
		(stageKind !== null && !["practice", "target", "view"].includes(stageKind))
	)
		throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
	return {
		round_number: roundNumber,
		scaffold_type: scaffoldType,
		english_tag_key: text(row.english_tag_key) as NonNullable<
			ChildEpisodeResponse["support_round"]
		>["english_tag_key"],
		stage_kind: stageKind as "practice" | "target" | "view" | null,
		previous_attempt_correct:
			row.previous_attempt_correct == null
				? null
				: bool(row.previous_attempt_correct),
		another_round_required: bool(row.another_round_required),
		withdrawal_allowed: bool(row.withdrawal_allowed),
		support_revision_id: text(row.support_revision_id),
		manifest_revision_id: text(row.manifest_revision_id),
	};
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
	if (row.feedback_si != null) parsed.feedback_si = text(row.feedback_si);
	if (row.reveal_key != null) {
		const key = text(row.reveal_key);
		if (!/^[a-z_]+$/.test(key))
			throw new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST");
		parsed.reveal_key = key;
	}
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
	"pillam_journey",
	"punctuation_journey",
	"riddle_journey",
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
	// 54 mapped areas: G5-AREA-SIN-16 was retired from the catalogue.
	if (!Array.isArray(row.missions) || row.missions.length !== 54) {
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

/** The answer a help stage shows on its board: tinted while playing, filled when solved. */
function supportAnswer(value: unknown): SupportAnswer | null {
	if (value == null || typeof value !== "object") return null;
	const row = value as Record<string, unknown>;
	if (row.mode !== "tint" && row.mode !== "filled") return null;
	const strings = (list: unknown) =>
		Array.isArray(list) ? list.map(text) : [];
	return {
		mode: row.mode,
		lines: strings(row.lines),
		marks: strings(row.marks),
	};
}

function supportGuidance(value: unknown): SupportGuidancePair[] {
	if (!Array.isArray(value)) return [];
	return value
		.filter((pair) => pair && typeof pair === "object")
		.map((pair) => {
			const row = pair as Record<string, unknown>;
			return {
				question_si: text(row.question_si),
				answer_si: text(row.answer_si),
			};
		});
}

/** A maths help stage's lesson: steps, the answer, theory, hints and the child's mistake. */
function supportLesson(value: unknown): SupportLesson | null {
	if (value == null || typeof value !== "object") return null;
	const row = value as Record<string, unknown>;
	const strings = (list: unknown) =>
		Array.isArray(list) ? list.map(text) : [];
	const notes = Array.isArray(row.notes)
		? row.notes
				.filter((note) => note && typeof note === "object")
				.map((note) => {
					const item = note as Record<string, unknown>;
					return { title_si: text(item.title_si), text_si: text(item.text_si) };
				})
		: [];
	const diagnosis =
		row.diagnosis && typeof row.diagnosis === "object"
			? (() => {
					const item = row.diagnosis as Record<string, unknown>;
					return {
						you_did_si: text(item.you_did_si),
						went_wrong_si: text(item.went_wrong_si),
					};
				})()
			: null;
	return {
		title_si: text(row.title_si),
		notes,
		steps_si: strings(row.steps_si),
		answer_si: row.answer_si == null ? null : text(row.answer_si),
		hints_si: strings(row.hints_si),
		another_view_si: strings(row.another_view_si),
		diagnosis,
		continue_label_si:
			row.continue_label_si == null ? null : text(row.continue_label_si),
	};
}
