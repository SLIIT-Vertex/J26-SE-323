# Connections to the other components

This page says how the adaptive game connects to every other MindBridge component: which ids are
shared, how each game skill maps to the team's Universal Skill Nodes, what crosses each boundary,
in which direction, when, and what happens when the other side is missing. It also lists what is
built but not wired, and every known mismatch, so no connection has to be guessed.

Checked against the code on 2026-11-18. When this page and the code disagree, the code is right
and this page needs fixing.

## 1. The components

| Component | Code | Its docs | Connected to the game? |
|---|---|---|---|
| Shared learner | `backend/app/shared/learner/` | [`architecture.md`](../architecture.md) | **Yes.** Every game record is keyed by `learners.id` |
| Knowledge Tracing (BHS-KT) | `backend/app/knowledge_tracing/` | [`docs/bhs-kt/`](../bhs-kt/00_README.md) | **Yes, one way.** It reads the game's scored answers (§4) |
| Learner State | `backend/app/learner_state/` | [`docs/learner-state/`](../learner-state/00_README.md) | **Yes, both ways.** The game records answers into it (§5) and reads its result for Model 2 (§6) |
| Shared curriculum (RAG) | `backend/app/curriculum/` | [`docs/curriculum/`](../curriculum/shared-rag-joint-plan.md) | **Built, not wired** (§8) |
| Adaptive Tutor | `backend/app/adaptive_tutor/` | [`docs/adaptive-tutor/`](../adaptive-tutor/controller-v1.md) | **No** (§10) |

The rules that hold for every connection are in §12.

## 2. The shared keys

### 2.1 Learner

Every component uses the shared learner UUID (`learners.id`, `app/shared/learner/model.py`). The
row holds only `grade` (4 or 5), `preferred_language`, an optional `display_name` and timestamps.
The game accepts only `grade = 5` and `preferred_language = si`
(`GRADE5_SINHALA_REQUIRED` otherwise).

There is no login yet. The app and the Knowledge Tracing practice screens both start from one
development learner, `00000000-0000-4000-8000-000000000721`, read from
`VITE_MOBILE_LEARNING_LEARNER_ID` (`frontend/src/features/papers/hooks.ts`, `SHARED_LEARNER_ID`).
`python -m scripts.seed_dev_learner` (from `backend/`) creates it. The game sends the id in the
`X-Learner-Id` header and the request body.

One exception: when every fresh item of a skill has already been shown to that learner, the
development client retries with new sessions and then plays that one game as another (or a new)
Grade 5 Sinhala-medium learner (`learningFlowClient.ts`, `PROBE_ALREADY_RESERVED_OR_EXPOSED`). The
next game starts from the configured learner again. Answers from such a game belong to the other
learner in every component.

### 2.2 Skills: four levels

| Level | Example | Count | Where it is defined | Who uses it |
|---|---|---|---|---|
| **Universal Skill Node** | `MAT-OPS` | 30 | [`docs/skill_nodes.xlsx`](../skill_nodes.xlsx) (the team taxonomy); the same 30 in `shared/feature_spec.json` | Every component. The only skill id other components accept |
| **Game label** | `MAT-DIV` | one per game | each flow class, or its content module's `UNIVERSAL_SKILL_ID` | The game's outbox, Learner State calls and Model 2's Learning State read (§3.2) |
| **Atomic skill** (Knowledge Tracing calls it "item skill") | `G5-MAT-DIV-SHARE-01` | 145 in the 37 games | each flow's `skills` mapping | Inside the game: items, Model 1's learner prior, Model 2's own-record features. Sent to Knowledge Tracing as `skill_code` |
| **Curriculum skill** | `G5-MAT-C06-L01-O01` | 548 | `data/gamification/skill-catalogue-review/v1/` | The skill catalogue and curriculum tracing. 7 of them are also atomic skills |

An area id (`G5-AREA-MAT-08`) names a game area, not a skill. Each area game has one game label.

```text
atomic skill  G5-MAT-DIV-SHARE-01 ─┐
atomic skill  G5-MAT-DIV-PLAN-01  ─┼─> game label MAT-DIV ─> Universal Skill Node MAT-OPS
… (5 in G5-AREA-MAT-08)           ─┘        (division game)       (via shared/game_skill_map.json)
```

## 3. Skill mapping

### 3.1 The 30 Universal Skill Nodes

`docs/skill_nodes.xlsx` (one sheet) defines them. `shared/feature_spec.json` repeats the same 30
for Knowledge Tracing; the two lists are identical.

| Domain | Nodes |
|---|---|
| Aptitude | `APT-PAT`, `APT-SPA`, `APT-DIR`, `APT-LOG`, `APT-REL`, `APT-VIS`, `APT-WRD` |
| Mathematics | `MAT-NUM`, `MAT-OPS`, `MAT-FRC`, `MAT-LEN`, `MAT-MAS`, `MAT-TIM`, `MAT-MON`, `MAT-GEO`, `MAT-DAT` |
| Language | `LAN-CMP`, `LAN-AGR`, `LAN-TNS`, `LAN-ORT`, `LAN-VOC`, `LAN-IDM`, `LAN-WRT`, `LAN-BIL` |
| Environment | `ENV-BIO`, `ENV-PHY`, `ENV-HLT`, `ENV-AGR`, `ENV-GEO`, `ENV-CIV` |

Learner State accepts any skill id of 1 to 16 characters and does not check it against this list
(`SKILL_ID_MAX_LENGTH`). Knowledge Tracing accepts only these 30.

### 3.2 Every playable game

The 37 games in `GAME_FLOW_TYPES` (`application/learning_flow_orchestration.py`). "Game label" is
what the game sends. "Universal node" is where Knowledge Tracing files the answer.
"Records Learner State" is the flow's `records_learner_state`.

| Area | Game (flow file in `application/`) | Atomic skills | Game label | Universal node | Records Learner State |
|---|---|---|---|---|---|
| `G5-AREA-MAT-01` | Nimo's Wacky Toybox (`number_world_flow.py`) | 4 | `MAT-NUM` | `MAT-NUM` | yes |
| `G5-AREA-MAT-02` | Nimo's Sky Adventure (`addition_adventure_flow.py`) | 3 | `MAT-OPS` | `MAT-OPS` | yes |
| `G5-AREA-MAT-03` | Number Patterns (`number_patterns_flow.py`) | 4 | `APT-PAT` | `APT-PAT` | yes |
| `G5-AREA-MAT-04` | Subtraction (`subtraction_adventure_flow.py`) | 5 | `MAT-OPS` | `MAT-OPS` | yes |
| `G5-AREA-MAT-05` | Fractions (`fraction_adventure_flow.py`) | 6 | `MAT-FRC` | `MAT-FRC` | yes |
| `G5-AREA-MAT-06` | Multiplication (`multiplication_adventure_flow.py`) | 5 | `MAT-OPS` | `MAT-OPS` | yes |
| `G5-AREA-MAT-07` | Time (`time_adventure_flow.py`) | 5 | **`MAT-TIME`** | `MAT-TIM` | yes |
| `G5-AREA-MAT-08` | Division (`division_adventure_flow.py`) | 5 | **`MAT-DIV`** | `MAT-OPS` | yes |
| `G5-AREA-MAT-09` | Distance Adventure (`distance_adventure_flow.py`) | 5 | **`MAT-LENGTH`** | `MAT-LEN` | yes |
| `G5-AREA-MAT-10` | Money Adventure (`money_adventure_flow.py`) | 5 | `MAT-MON` | `MAT-MON` | yes |
| `G5-AREA-MAT-11` | Capacity Adventure (`capacity_adventure_flow.py`) | 5 | `MAT-MAS` | `MAT-MAS` | yes |
| `G5-AREA-MAT-12` | Mass Adventure (`mass_adventure_flow.py`) | 5 | `MAT-MAS` | `MAT-MAS` | yes |
| `G5-AREA-MAT-13` | Shape Adventure (`shape_adventure_flow.py`) | 3 | **`MAT-SHP`** | `MAT-GEO` | yes |
| `G5-AREA-MAT-14` | Direction Adventure (`direction_adventure_flow.py`) | 3 | **`MAT-DIR`** | `APT-DIR` | yes |
| `G5-AREA-MAT-15` | Decimal Adventure (`decimal_adventure_flow.py`) | 4 | **`MAT-DEC`** | `MAT-FRC` | yes |
| `G5-AREA-MAT-16` | Roman Adventure (`roman_adventure_flow.py`) | 3 | **`MAT-ROM`** | `MAT-NUM` | yes |
| `G5-AREA-ENG-01` | Classroom Action Quest (`classroom_action_quest_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | **no** |
| `G5-AREA-ENG-02` | Sri Lanka Discovery (`sri_lanka_discovery_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-03` | Plant Explorer (`plant_explorer_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-04` | Wildlife Ranger (`wildlife_ranger_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-05` | Everyday Object Quest (`everyday_object_quest_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-06` | Island Food Festival (`island_food_festival_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-07` | Rainbow Wardrobe Quest (`rainbow_wardrobe_quest_flow.py`) | 1 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-08` | Water Works Adventure (`water_works_adventure_flow.py`) | 1 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-09` | Transit Terminal Quest (`transit_terminal_quest_flow.py`) | 1 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-10` | Bloom Builder Garden (`bloom_builder_garden_flow.py`) | 1 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-11` | Workplace Link City (`workplace_link_city_flow.py`) | 2 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-12` | Family Word Constellation (`family_word_constellation_flow.py`) | 1 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-13` | Earth Sky Explorer (`earth_sky_explorer_flow.py`) | 2 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-14` | Blueprint Quest (`blueprint_quest_flow.py`) | 3 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-15` | Information Station (`information_station_flow.py`) | 2 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-16` | Heritage Museum Quest (`heritage_museum_quest_flow.py`) | 2 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-17` | Classroom Language Live (`classroom_language_live_flow.py`) | 4 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-ENG-18` | Conversation Street (`conversation_street_flow.py`) | 4 | `LAN-BIL` | `LAN-BIL` | yes |
| `G5-AREA-SIN-01` | Sinhala Pillam (`sinhala_pillam_flow.py`) | 6 | `LAN-ORT` | `LAN-ORT` | **no** |
| `G5-AREA-SIN-02` | Sinhala Punctuation (`sinhala_punctuation_flow.py`) | 11 | `LAN-WRT` | `LAN-WRT` | **no** |
| `G5-AREA-SIN-03` | Sinhala Riddle (`sinhala_riddle_flow.py`) | 2 | `LAN-CMP` | `LAN-CMP` | **no** |

The seven labels in bold are not Universal Skill Nodes. Knowledge Tracing translates them with
`sub_skills` in `shared/game_skill_map.json`. Learner State stores them as they are (§13, item 1).

Games that share a Universal node: `MAT-OPS` (addition, subtraction, multiplication, division),
`MAT-NUM` (Number World, Roman), `MAT-FRC` (fractions, decimals), `MAT-MAS` (capacity, mass),
`LAN-BIL` (all 18 English games). Knowledge Tracing counts all their answers towards one mastery
value.

Games that share a game label, and so share Learner State records (§6): `MAT-OPS` (addition,
subtraction, multiplication), `MAT-MAS` (capacity, mass), `LAN-BIL` (the 17 English games that
record, read by all 18).

The atomic skill ids of every game, each with its Universal node, are in
`shared/game_skill_map.json` under `item_skills` (145 ids).

### 3.3 The mapping files

| File | Maps | Owner | Made by | Checked by |
|---|---|---|---|---|
| `shared/game_skill_map.json` | `sub_skills`: game label → node (7 rows). `item_skills`: atomic skill → node (145 rows) | Knowledge Tracing | `python -m scripts.build_game_skill_map` (from `backend/`). Reads the game flows and `areas.json`; never edit by hand | `--check`; `test_the_skill_map_file_is_up_to_date_with_the_games_current_skills` (`tests/knowledge_tracing/test_game_evidence.py`) |
| `data/gamification/grade5-playable-area-package/v1/areas.json` | area → node (`universal_skill_id`, or `no_universal_parent: true`) for 56 areas | Game | committed by hand (no builder); `manifest.json` next to it pins its SHA-256 | `tests/gamification/content/test_playable_area_package.py` |
| `data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl` | curriculum skill → node (548 rows) | Game | `PYTHONPATH=backend python3 tools/gamification/skills/build_skill_review_package.py` | validated against `docs/skill_nodes.xlsx` by the builder |

How the map builder decides a game's node: the area's `universal_skill_id` in `areas.json` wins.
When the area has none (the Sinhala games) or is not listed (the English games, since `areas.json`
covers only Mathematics, Sinhala and Environment), the game label is used if it is one of the 30.
Otherwise the build stops with an error.

**`areas.json`** has 56 rows (16 Mathematics, 24 Sinhala, 16 Environment; `G5-AREA-SIN-16` is not
in it). By node:

| Node | Areas |
|---|---|
| `MAT-OPS` | MAT-02, MAT-04, MAT-06, MAT-08 |
| `MAT-NUM` | MAT-01, MAT-16 |
| `MAT-FRC` | MAT-05, MAT-15 |
| `MAT-MAS` | MAT-11, MAT-12 |
| `MAT-TIM`, `MAT-LEN`, `MAT-MON`, `MAT-GEO` | MAT-07, MAT-09, MAT-10, MAT-13 |
| `APT-PAT`, `APT-DIR` | MAT-03, MAT-14 |
| `ENV-CIV` | ENV-01, ENV-02, ENV-11, ENV-12, ENV-14, ENV-15, ENV-16 |
| `ENV-BIO`, `ENV-HLT`, `ENV-PHY` | ENV-03 and 04, ENV-06 and 07, ENV-08 and 09 |
| `ENV-AGR`, `ENV-GEO` | ENV-10, ENV-13 |
| none (`no_universal_parent`) | all 24 Sinhala areas, and ENV-05 |

**The curriculum crosswalk** gives each of the 548 curriculum skills exactly one node. Every row is
`status: draft` with no reviewer. Confidence: 160 high, 150 medium, 238 low. Rows per node:
`ENV-CIV` 103, `LAN-BIL` 69, `LAN-CMP` 55, `ENV-PHY` 42, `LAN-WRT` 42, `MAT-OPS` 42, `ENV-HLT` 33,
`ENV-BIO` 28, `ENV-GEO` 18, `LAN-AGR` 16, `ENV-AGR` 14, `MAT-MAS` 13, `MAT-NUM` 11, `MAT-TIM` 11,
`MAT-FRC` 8, `MAT-LEN` 7, `APT-PAT` 6, `LAN-ORT` 6, `LAN-VOC` 6, `MAT-DAT` 6, `MAT-MON` 6,
`LAN-TNS` 2, `MAT-GEO` 2, `APT-DIR` 1, `LAN-IDM` 1. The five other aptitude nodes have none.

### 3.4 Nodes with no game

No playable game reaches these 16 nodes: `APT-LOG`, `APT-REL`, `APT-SPA`, `APT-VIS`, `APT-WRD`,
`MAT-DAT`, `LAN-AGR`, `LAN-IDM`, `LAN-TNS`, `LAN-VOC`, and all six `ENV-*` nodes. The Environment
areas play only as fixture rounds, which keep their records in process memory and send nothing to
another component.

## 4. Knowledge Tracing: scored answers (live)

| | |
|---|---|
| Direction | Game → Knowledge Tracing. The game never calls it; Knowledge Tracing reads the game's table |
| What | Each unsupported answer (`unsupported_before` and `unsupported_after`) of every area game, one row per answer. Help rounds and answers after Model 3 are never written |
| Where | Table `learner_evidence_outbox` (game-owned), event `gamification_item_scored`, contract `gamification-learner-evidence-v2`, key `<attempt_id>:gamification_item_scored`. Written in the same transaction as the answer by `SqlAlchemyLearningFlowEvidencePublisher` (`infrastructure/db/learning_flow_gateways.py`) |
| Columns | `skill_code` = the atomic skill; `universal_skill_id` = the game label (§3.2); `learner_id`; `payload_json`; `contract_version`; `status` (`pending`); `created_at` |
| Payload | `learner_id`, `skill_id`, `universal_skill_id`, `episode_id`, `presentation_id`, `item_revision_id`, `parallel_family_id`, `attempt_id`, `measurement_role`, `assistance_state` (`none`), `earned_score`, `maximum_score`, `scoring_version`, `correct`, `response_time_ms` (may be null), `supported` (false), `hint_count` (0), `difficulty`, `difficulty_source`, `difficulty_mapping_version` (`gamification-skill-level-v1`), `environment`, `model_ingestion_eligible`, `session_id`. The answer, prompt and chosen option are refused (`EVIDENCE_PAYLOAD_LEAKAGE`) |
| Difficulty | Each atomic skill's own level: easy → easy, medium → medium, hard → hard, and the in-between levels → medium. All 145 atomic skills declare a level (`difficulty_source: declared`) |
| Release rule | `model_ingestion_eligible` is true only when the episode ran in the `pilot` environment and the learner has a granted, unexpired `research` consent (`_model_eligible` in `engine/area_flow.py`; `consent_gate.py`). `development` and `test` answers are always false |
| Reader | `python -m scripts.ingest_game_evidence` (from `backend/`; `--dry-run`, `--include-development`). Or automatically, before "My skills" and "Make this week's paper", when `GAME_EVIDENCE_AUTO_READ=true` (and `GAME_EVIDENCE_INCLUDE_DEVELOPMENT=true` on a local database only) |
| Reader's checks | The game label is translated by `sub_skills` and must be one of the 30; the atomic skill (`skill_code`) must map to the same node in the crosswalk plus `item_skills`; difficulty must be easy, medium or hard; `correct` a plain boolean; the learner must exist with a language. A failing record is skipped and counted, never changed |
| Stored as | A Knowledge Tracing attempt keyed `game:<attempt_id>`, so a record is read once |
| If Knowledge Tracing is absent | Nothing changes for the game. Rows stay in the outbox |
| Tests | `tests/knowledge_tracing/test_game_pilot_end_to_end.py` (the real division flow, the game's publisher and the reader), `tests/knowledge_tracing/test_game_evidence.py` |

The full reader description is Knowledge Tracing's
[`GAME_INTEGRATION.md`](../bhs-kt/GAME_INTEGRATION.md). Knowledge Tracing owns the final decision on
what reaches its model; `model_ingestion_eligible` is the game's signal only.

## 5. Learner State: recording answers (live)

| | |
|---|---|
| Direction | Game → Learner State, in process |
| When | After each unsupported answer is committed, and never for a replayed request (same `Idempotency-Key`). Only in games with `records_learner_state = True` (§3.2) |
| Call | `record_scored_answer()` (`application/learner_state_answers.py`) through the game's `LearnerStateAnswerGateway` protocol (`application/session_play.py`). The adapter (`infrastructure/gateways/learner_state_answers.py`) returns Learner State's published `GameAnswerRecorder` (`app.learner_state.application.answer_recording`), which opens its own database session |
| Values sent | `session_id` = the request's `learner_state_session_id` (one per app session), or the episode's `session_id` when absent; `learner_id`; `window_id` = scoring time in milliseconds; `skill_id` = the **game label**; `observed_at`; `correct`; `response_time_ms`; `supported = false`; `hint_count = 0`; `visual` = the 11 camera numbers only with current `learner_state_camera` consent, else none |
| Learner State does | Records nothing when `response_time_ms` is null. Otherwise evaluates the window and stores the latest state per learner and skill in `learner_skill_states`. Returns `recommended_action` |
| Back to the app | `learner_state_action` on the answer response (not stored in the idempotency receipt, so a retry returns none). The app shows a prompt for `request_tutor_support` or `request_reengagement_support`, unless `VITE_LEARNER_STATE_PROMPTS=off` |
| On failure | Logged and ignored. The answer is never changed or rejected |
| Tests | `tests/learner_state/test_game_answers.py` (the recorder matches the game protocol) |

Field-level details (the 11 camera numbers, consent, behaviour fields): the game's
[`learner-state-answer-integration.md`](learner-state-answer-integration.md) and Learner State's
[`11_GAME_INTEGRATION.md`](../learner-state/11_GAME_INTEGRATION.md).

## 6. Learner State: the reading Model 2 uses (live)

| | |
|---|---|
| Direction | Learner State → game, in process |
| When | Once per episode, when the first unsupported answer is wrong and the help loop starts (`_start_support_loop` in `engine/area_flow.py`; the Sinhala flow does the same). Read in both conditions; **used and stored only in the proposed condition** (`model2.learning_state_input`) |
| Call | `ResearchLearningStateGateway` (`infrastructure/gateways/research_learning_state.py`) over `StoredSupportNeedProvider` (`app.learner_state.application.support_need`), composed in `app/shared/learning_state_provider.py` and wired in `api/learning_flow_router.py` |
| Request | `learner_id`; `skill_id` = the **game label**; `session_id` = the same learner-state session id as §5; `max_age_ms` = `RECOMMENDED_MAX_STATE_AGE_MS` (60,000) |
| Accepted | Status `AVAILABLE`, or `UNCERTAIN` with `recommended_action = request_reengagement_support`; the stored session equals the request's; the state is 0 to 60,000 ms old |
| Turned into | `disengaged` when the action is `request_reengagement_support`; else `confused` when `support_need ≥ 0.6`; else `calm` |
| Otherwise | `not_available` with a reason (`NOT_FOUND`, `STALE`, the status, or `PROVIDER_UNAVAILABLE` on any error). The game never fails because of it |
| Used for | One of the four Learning State values (`not_available`, `calm`, `confused`, `disengaged`) in the help-order bandit's context (`modeling/support_selection/game_bandit.py`) |

Because the key is the game label, a reading can come from another game with the same label in
the same app session, within 60 seconds (§3.2). The three Sinhala games read but never record, and
no other game records under `LAN-ORT`, `LAN-WRT` or `LAN-CMP`, so their reading is always
`not_available`. Classroom Action Quest reads `LAN-BIL`, which the other English games record.

## 7. Consent

Both purposes are stored by the game in `consent_decisions` (latest decision per learner and
purpose). No other component reads that table.

| Purpose | Set by | Gates |
|---|---|---|
| `learner_state_camera` | `PUT /api/v1/development/learning-flow/consents/learner-state-camera` (the guardian switch under Settings) | Whether the 11 camera numbers are passed to Learner State (§5) |
| `research` | `python -m scripts.record_research_consent --learner-id <uuid>` (`--withdraw` to stop) | Whether an answer is released to Knowledge Tracing (§4) |

Camera consent is not research consent. The camera endpoint and the research-consent script stand
in for a guardian login, which production needs.

## 8. Shared curriculum (built, not wired)

`SharedCurriculumAdapter` (`infrastructure/curriculum_adapter.py`) translates an atomic or
curriculum skill to its node with a crosswalk mapping, then calls the shared `CurriculumRetriever`
(`app.curriculum.application.retrieval`) with `purpose = "CONTENT_AUTHORING"`. A skill with no
node raises `ValueError`. It is tested (`test_curriculum_adapter_sends_the_universal_skill_id` in
`tests/gamification/test_cross_component.py`) but no running path creates it. No area game reads a
curriculum passage. The pilot API's play path returns `CURRICULUM_RETRIEVAL_UNAVAILABLE`.

The agreement between the game and the Adaptive Tutor on the shared retriever is
[`shared-rag-joint-plan.md`](../curriculum/shared-rag-joint-plan.md). Game items, answer keys,
misconceptions and helps are never indexed into it.

To wire it: build a `CurriculumRetriever` (for example `HybridCurriculumRetriever`), load the
crosswalk, create the adapter in the game's infrastructure, and pass it to the use case that needs
it. Changes inside `backend/app/curriculum/` need both owners' review.

## 9. Knowledge Tracing mastery (built, not wired)

`KnowledgeTracingMasteryGateway` (`infrastructure/gateways/knowledge_tracing_mastery.py`) asks
Knowledge Tracing's published `MasteryProvider` (`app.knowledge_tracing.application.mastery`) for
one learner and one node. It translates the skill with a crosswalk mapping, refuses a node
outside the allowed set, and records every absence as a `mastery_missing` audit event
(`MASTERY_CROSSWALK_MISSING`, `UNIVERSAL_SKILL_NOT_IN_TAXONOMY`, `MASTERY_PROVIDER_EXCEPTION`,
`MASTERY_<status>`). It never invents a value. `LearnerStateSupportNeedGateway`
(`learner_state_support_need.py`) is the same kind of adapter for the support need.

Both are tested in `tests/gamification/test_cross_component.py`, but **no running path creates
them**. The area games, Model 1 and Model 2 do not read mastery. The mastery value a node gets is
shared by every game under it.

To wire mastery: pass a `MasteryProvider` (Knowledge Tracing builds it), the crosswalk (atomic or
curriculum skill → node) and the 30 node ids into the gateway, and give the gateway to the code
that needs mastery. A model that starts using it is a new model version.

## 10. Adaptive Tutor (no connection)

The game does not call the Adaptive Tutor and the tutor does not read any game table. When Learner
State returns `request_tutor_support` after a game answer, the app shows an encouraging prompt
only. No tutor session is opened. The tutor's own inputs (skill mapper, mastery retrieval,
support need) use the same 30 nodes, so a later hand-off would pass a node, not a game label or
atomic skill.

## 11. What no other component receives

Model 1 beliefs, Model 2 help orders and decisions, the bandit's ledger, Model 3's Independence
Gain and validity, help rounds, supported answers, rewards, telemetry and the research dashboard
stay inside the game. No other component reads them, and the game publishes no contract for them.

## 12. Rules for any connection

- The game imports another component only from `infrastructure/`, and only these modules:
  `app.curriculum.application`, `app.knowledge_tracing.application.mastery`,
  `app.learner_state.application.support_need` and
  `app.learner_state.application.answer_recording`. Domain and application code import none.
  Enforced by `tests/gamification/test_architecture.py`.
- No game table has a foreign key to another component's table except `learners.id`.
- The game never writes another component's tables. Other components may read the game's outbox
  only.
- Every call to another component sends a Universal Skill Node, or, in the three live connections
  (§4 to §6), the game label of §3.2.
- An optional input that is missing is stored as an absence with a reason, never as a made-up value,
  and never fails a game.

## 13. Mismatches and open decisions

1. **Seven game labels are not Universal Skill Nodes** (§3.2). Knowledge Tracing translates them;
   Learner State does not. So Learner State holds states under `MAT-TIME`, `MAT-DIV`,
   `MAT-LENGTH`, `MAT-SHP`, `MAT-DIR`, `MAT-DEC` and `MAT-ROM`, and anyone reading it by node (for
   example `MAT-OPS` for division) will not find them. To decide (game and Learner State owners):
   send the node instead of the label (this changes which games share Model 2's reading), or
   have Learner State translate with `sub_skills`.
2. **The Sinhala games' node comes from the flow, not from `areas.json`.** `areas.json` marks
   SIN-01 to SIN-03 `no_universal_parent`; their flows send `LAN-ORT`, `LAN-WRT` and `LAN-CMP`, and
   the map builder accepts those. Knowledge Tracing's `GAME_INTEGRATION.md` still says the Sinhala
   areas have no parent. One source should be chosen.
3. **The English games are not in `areas.json`.** Their node `LAN-BIL` comes only from the code
   (`engine/english_area_flow.py`, `content/classroom_action_quest.py`).
4. **The crosswalk and the area parents are drafts.** All 548 crosswalk rows are unreviewed;
   238 are low confidence. `areas.json` parents are not reviewed either.
5. **ADR-0010**, cited as the source of the crosswalk rule, is not in the repository.
6. **Mastery and curriculum adapters are not wired** (§8, §9). Wiring either is a decision for the
   game owner, with the Knowledge Tracing or Adaptive Tutor owner.
7. **Knowledge Tracing's open item "levels for six games" is done**: every atomic skill now
   declares a level.
8. **Shared development learner** (§2.1): a game can fall back to another development learner.
9. **Learner State session history is in memory**: a backend restart starts every session afresh
   (Learner State's `07_EVALUATION_AND_LIMITATIONS.md` §4.3).
10. **No tutor hand-off** for `request_tutor_support` (§10).

## 14. How to check

From `backend/`:

```bash
python -m scripts.build_game_skill_map --check          # the skill map matches the games
.venv/bin/python -m pytest -q tests/gamification/test_architecture.py \
  tests/gamification/test_cross_component.py tests/learner_state/test_game_answers.py \
  tests/knowledge_tracing/test_game_evidence.py tests/knowledge_tracing/test_game_pilot_end_to_end.py
python -m scripts.ingest_game_evidence --dry-run        # what Knowledge Tracing would read now
```
