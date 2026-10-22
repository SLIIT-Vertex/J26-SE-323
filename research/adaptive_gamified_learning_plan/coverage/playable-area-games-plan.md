# Playable draft games for every Grade 5 skill area

This is a development plan for 56 playable draft games. It does not add games, templates, routes, or content. It does not approve content, open child delivery, collect real-child data, or activate a learned policy.

Subjects are Mathematics, Sinhala, and Environmental Studies. English and other grades stay out. Child-facing copy is Sinhala. Every round stays unreviewed. Production loaders stay fail-closed: `load_draft_mission_catalog` and `load_area_support_catalog` reject the package unless `environment` is `development` or `test` and `allow_draft` is true.

The current draft-mission catalog and area-support catalog cover the 54 mapped areas and omit `G5-AREA-SIN-11` and `G5-AREA-SIN-12`. This plan adds those two as playable placeholders. Their source status is `no_grade5_source`. Their copy says they have no Grade 5 source. This plan does not cite a source for them.

`G5-AREA-MAT-05` preserves the existing `G5-MAT-C03-L01-O01` half-set identity and durable history inside the dedicated development-only Fraction Adventure package. Provisional half-whole, quarter-whole, quarter-table, and tenths subskills are source-linked to photographed pages 69–70 without claiming official approval.

## Inventory

56 rows: 16 mathematics, 24 Sinhala, 16 environmental. Source status `mapped_draft` is the coverage status `MAPPED_DRAFT`. Source status `no_grade5_source` is the coverage status `BLOCKED`.

Template id and eligible support types for every `mapped_draft` row are the values returned by `assigned_template` and `assignment` in `backend/app/gamification/content/draft_mission_catalog.py` and `backend/app/gamification/content/area_support_catalog.py`. Support types stay in that function's order.

Round basis:

- `official trace sentence` — the draft-mission catalog already stores a learning-outcome sentence for this area, and that slot is an area match (`supplied_area_match` or `area_match` is true). Mathematics sentences are `extraction_confidence=medium`. The five Sinhala sentences are `extraction_confidence=high`. The round uses one such sentence. It is not an approved question.
- `developer draft from the title` — this area has no area-matched learning-outcome sentence that is medium or high confidence. Low-confidence held strings stay stored and are not the child question. The round is one Sinhala prompt written from the area title. The copy says it is not an official question, and the round is unreviewed.

`G5-AREA-MAT-13` has no learning outcomes. `G5-AREA-MAT-14` has no learning outcomes on its cited competency; the three sentences on its mission are marked `supplied_area_match=false` and belong to another competency. Both rounds are developer drafts from the title.

`assigned_template` and `assignment` raise `ValueError` for `G5-AREA-SIN-11` and `G5-AREA-SIN-12`. The placeholder rows below reuse `word_workshop`, the template that function already returns for the other non-invitation Sinhala areas. Their eligible set is the three game support types used by the non-verbal Sinhala branch. That branch is not reached today because the function raises first. No new mechanic is added.

| Area | English name | Subject | Template | Source status | Eligible support types | Round |
| --- | --- | --- | --- | --- | --- | --- |
| `G5-AREA-MAT-01` | Numbers | Mathematics | `market_mission` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-02` | Addition | Mathematics | `addition_adventure` | mapped_draft | activity-specific visual_guidance, exact worked_parallel_example, step_by_step_guidance | textbook-derived draft package; human review pending |
| `G5-AREA-MAT-03` | Number Patterns | Mathematics | `number_pattern_adventure` (dedicated draft; `pattern_temple` fallback) | mapped_draft | activity-specific deterministic visual_guidance / exact worked visual / step_by_step_guidance paths | official trace sentence plus photographed +2/+4, −2/−4, ×2/×3/×4/×5 evidence; provisional internal skills remain unreviewed |
| `G5-AREA-MAT-04` | Subtraction | Mathematics | `subtraction_adventure` (dedicated mapped-draft package; `market_mission` remains the catalogue fallback) | mapped_draft | activity-specific visual guidance, exact worked visual, step-by-step guidance | photographed column, expanded, and difference structures plus repository-draft two-regroup outcome; human review pending |
| `G5-AREA-MAT-05` | Fractions | Mathematics | `fraction_adventure` | implemented_unreviewed | visual_guidance, worked_parallel_example, step_by_step_guidance | photographed pages 69–70 plus existing official trace |
| `G5-AREA-MAT-06` | Multiplication | Mathematics | `market_mission` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-07` | Time | Mathematics | `parcel_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-08` | Division | Mathematics | `market_mission` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-09` | Length and Distance | Mathematics | `parcel_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-10` | Money | Mathematics | `market_mission` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-11` | Volume and Capacity | Mathematics | `parcel_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-12` | Measuring Weight | Mathematics | `parcel_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-13` | Shapes and Solid Objects | Mathematics | `pattern_temple` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-MAT-14` | Directions | Mathematics | `pattern_temple` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-MAT-15` | Decimals | Mathematics | `market_mission` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-MAT-16` | Roman Numerals | Mathematics | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-SIN-01` | Identifying Vowel Signs | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-02` | Identifying Punctuation Marks | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-03` | Riddles | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-04` | Synonyms | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-05` | Antonyms | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-06` | Paired Words | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-07` | Proverbs | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-08` | Idiomatic Expressions | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-09` | Wise Sayings and Maxims | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-10` | Similes | Sinhala | `word_workshop` | mapped_draft | worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-11` | Common-Gender Terms | Sinhala | `word_workshop` | no_grade5_source | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-12` | Verbs and Predicates | Sinhala | `word_workshop` | no_grade5_source | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-13` | Invitation Letters | Sinhala | `story_studio` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-14` | Feminine and Masculine Nouns | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-15` | Singular and Plural Words | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-17` | Usage of න and ණ | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-18` | Usage of ල and ළ | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-19` | Usage of ස, ශ and ෂ | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-20` | Unaspirated and Aspirated Consonants | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-21` | Nouns | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-SIN-22` | Verbs | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-SIN-23` | Subject and Non-subject Forms | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-SIN-24` | Simple Sentences | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-SIN-25` | Sentence Patterns Using ද, ත, ස, හා and සහ | Sinhala | `word_workshop` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | official trace sentence |
| `G5-AREA-ENV-01` | Our Well-being | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-02` | We Are Sri Lankans | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-03` | Plants and Trees | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-04` | Animals Around Us | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-05` | Things We Use | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-06` | Our Food | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-07` | Safety and Care | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-08` | Water | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-09` | Ways to Make Work Easier | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-10` | Home Garden | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-11` | Transportation | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-12` | Human Behaviour | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-13` | Earth and Sky | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-14` | Changes We Can Make | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-15` | Humans and Information | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |
| `G5-AREA-ENV-16` | Stories from Our Past | Environmental Studies | `eco_explorer` | mapped_draft | visual_guidance, worked_parallel_example, step_by_step_guidance | developer draft from the title |

## Full-loop contract

Each of the 56 games is one development episode:

1. `unsupported_before` — one item, `assistance_state=none`.
2. One support type chosen from that area's eligible set, shown only during `supported_practice`.
3. `unsupported_after` — a fresh parallel item, `assistance_state=none`.

`MeasurementRole` in `backend/app/gamification/domain/types.py` names the roles `unsupported_before`, `supported_practice`, and `unsupported_after`. `PresentationContract` in `backend/app/gamification/api/research_contracts.py` requires `assistance_state=none` for `unsupported_before`, `unsupported_after`, and `retention`, and rejects `assistance_state=none` on `supported_practice`. `AssistanceState.NONE` is the string `none`.

Parallel-item rule. The before item, the supported item, and the after item share one `parallel_family_id` and one skill, and they use distinct `item_revision_id` values. `calculate_measurement` in `backend/app/gamification/modeling/independence_gain/measurement.py` rejects a reused revision (`REUSED_ITEM_OR_REVISION`), more than one family (`INCOMPATIBLE_PARALLEL_FAMILY`), and a scaffold whose `answer_revealing` flag is true (`SCAFFOLD_ANSWER_LEAKAGE`). The after item is unseen: `IndependenceGainInput.unseen_verification_item` must stay true, and a probe reservation that was already used is `PRIOR_PROBE_EXPOSURE`. The existing half-set family states the same surface rule in `equivalence_constraints`: object, total, correct answer, and revision are distinct, and unsupported probes do not expose scaffolds.

Server-owned rubric. `ServerAuthoritativeScorer.score` reads `ItemRubric` (`item_revision_id`, `rubric_version`, `scoring_version`, `maximum_score`, `correct_response`) and ignores `client_claimed_score`. The scored attempt's `server_authoritative` flag stays true.

Answer-leakage rule. Scaffold records use `answer_leakage_rule=no_probe_values_or_answers`. The half-set package validator rejects a scaffold `worked_values` set that intersects the probe totals or numeric option text. A worked example uses different numbers, words, or objects. A step stops before the result. Visual guidance does not mark the scored choice. Verbal-relation areas have no visual guidance, because a picture of the relation would state the scored answer. The evidence publisher rejects a payload that contains `answer`, `prompt`, or `selected_option_id`.

Development episodes must not train the learned policy. The learning-flow publisher writes `model_ingestion_eligible=false`. These games stay `publication_status=blocked` and `development_only=true`. They must not call the learned-policy reward link. `RewardLinker.link` accepts a reward only when `experiment_mode` is proposed, the decision mode is `proposed_shadow` or `proposed_offline`, the measurement is valid, and `policy_update_status` is `authorized_delayed`. A development area game must not produce that link.

Conflict. `calculate_measurement` sets `policy_update_status` to `authorized_delayed` for every valid proposed episode. It does not read `environment` or `model_ingestion_eligible`. The development game must not treat that status as permission to update the learned policy.

Conflict. The child learning-flow manifest types `assistance_state` as `none`, `active`, `adult`, `tutor`, or `unknown` (`backend/app/gamification/api/learning_flow_router.py`). The domain enum is `none`, `scaffold_active`, `tutor_active`, `adult_reported`, or `unknown`. The episode contract uses the domain enum. The game scaffold is `scaffold_active` during `supported_practice`, not `tutor_active`.

## Other components

A new area game supplies the fields named here and does not copy another module's tables. Conflicts are recorded where the current code does not agree. No missing name below was filled in.

### Shared learner

Owning module: `shared/learner`.

Fields found in `backend/app/shared/learner/model.py` on table `learners`: `id` (UUID primary key), `grade` (`ck_learners_grade` allows 4 or 5), `preferred_language` (`String(10)`), `created_at`, `updated_at`. The domain object in `backend/app/shared/learner/domain.py` uses the same names. Other modules reference `learners.id` as `learner_id`.

The learning-flow open path in `backend/app/gamification/api/learning_flow_router.py` loads that row and rejects the episode with `GRADE5_SINHALA_REQUIRED` unless `grade == 5` and `preferred_language == "si"`.

A new area game supplies the existing learner UUID. It checks grade 5 and Sinhala medium on that row. It does not insert a second learner profile and does not copy `grade` or `preferred_language` into a gamification-owned learner table.

Conflict. There is no `curriculum_medium` column on `learners`. Gamification uses `curriculum_medium: Literal["si"]` on `EligibilityEvidence` (`backend/app/gamification/application/ownership_ports.py`) and on `PresentationContract` (`backend/app/gamification/api/research_contracts.py`). Sinhala medium for the shared profile is `preferred_language == "si"`. The game must not invent a second medium field on the learner row.

### Curriculum retrieval

Owning module: `app.curriculum`, read by gamification only through `SharedCurriculumAdapter` in `backend/app/gamification/infrastructure/curriculum_adapter.py`.

The adapter method is `retrieve(learner_question, skill_id, grade, requested_language, limit)`. It maps `skill_id` through its crosswalk and sends `CurriculumRetrievalRequest.skill_id` as that Universal id, with `purpose="CONTENT_AUTHORING"`. Request fields are `learner_question`, `skill_id`, `grade`, `requested_language`, `subject`, `required_language`, `unit_id`, `purpose`, and `limit` (`backend/app/curriculum/application/retrieval.py`). The result is `CurriculumRetrievalResult` with `status` and `passages`. Status values include `FOUND`, `NO_RELEVANT_PASSAGES`, `NO_APPROVED_SOURCE`, `PROVIDER_UNAVAILABLE`, and `PROVIDER_ERROR`.

A missing passage must not block play. The game stores `NO_RELEVANT_PASSAGES`, `NO_APPROVED_SOURCE`, `PROVIDER_UNAVAILABLE`, or `PROVIDER_ERROR` as an absence and continues the episode.

Conflict. `SharedCurriculumAdapter.retrieve` raises `ValueError` when the crosswalk has no Universal id. `SessionPlayService._present` raises `PlayError("CURRICULUM_RETRIEVAL_UNAVAILABLE")` when approved content is not injected (`backend/app/gamification/application/session_play.py`). Those current failures block the caller. An area game must not use either failure as a reason to reject play when the passage is missing. A missing Universal parent is the crosswalk conflict in the next section, not a reason to invent a passage.

Game items, rubrics, answer keys, and scaffolds are not curriculum evidence. `docs/curriculum/shared-rag-joint-plan.md` forbids indexing the gamification question bank. `backend/scripts/build_curriculum_chunks.py` does not read game items, answer keys, or scaffolds. A new area game must not add those records to the curriculum chunk index.

### Universal skill crosswalk

Owning module: the gamification skill catalogue, checked against the shared taxonomy.

`UniversalSkillLink` in `backend/app/gamification/skill_catalogue/contracts.py` has `gamification_skill_id`, `universal_skill_id`, `crosswalk_version`, `confidence`, `status`, `reviewer_id`, and `reviewed_on`. `UNIVERSAL_SKILL_ID_MAX_LENGTH` is 16. `UNIVERSAL_SKILL_ID_PATTERN` is `^[A-Z]{3}-[A-Z]{3}$`. The rows are in `data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl`. Existing node ids come from `docs/skill_nodes.xlsx` (`Skill ID`, loaded as `skill_id`). The coverage field is `related_universal_skill_ids`.

A parent is settled only when `related_universal_skill_ids` has exactly one id, that id is in the taxonomy workbook, and its length is at most 16. The game sends that id as `universal_skill_id` on retrieval, mastery, and the scored-evidence event. It does not create a node. Placeholders have no parent yet: their coverage list is empty, they have no cited node, and they have no crosswalk row.

Settled parents:

| Area | Parent |
| --- | --- |
| `G5-AREA-MAT-01` | `MAT-NUM` |
| `G5-AREA-MAT-02` | `MAT-OPS` |
| `G5-AREA-MAT-03` | `APT-PAT` |
| `G5-AREA-MAT-04` | `MAT-OPS` |
| `G5-AREA-MAT-05` | `MAT-FRC` |
| `G5-AREA-MAT-06` | `MAT-OPS` |
| `G5-AREA-MAT-07` | `MAT-TIM` |
| `G5-AREA-MAT-08` | `MAT-OPS` |
| `G5-AREA-MAT-09` | `MAT-LEN` |
| `G5-AREA-MAT-10` | `MAT-MON` |
| `G5-AREA-MAT-11` | `MAT-MAS` |
| `G5-AREA-MAT-12` | `MAT-MAS` |
| `G5-AREA-MAT-13` | `MAT-GEO` |
| `G5-AREA-MAT-14` | `APT-DIR` |
| `G5-AREA-MAT-15` | `MAT-FRC` |
| `G5-AREA-MAT-16` | `MAT-NUM` |
| `G5-AREA-ENV-01` | `ENV-CIV` |
| `G5-AREA-ENV-02` | `ENV-CIV` |
| `G5-AREA-ENV-03` | `ENV-BIO` |
| `G5-AREA-ENV-04` | `ENV-BIO` |
| `G5-AREA-ENV-06` | `ENV-HLT` |
| `G5-AREA-ENV-07` | `ENV-HLT` |
| `G5-AREA-ENV-08` | `ENV-PHY` |
| `G5-AREA-ENV-09` | `ENV-PHY` |
| `G5-AREA-ENV-10` | `ENV-AGR` |
| `G5-AREA-ENV-11` | `ENV-CIV` |
| `G5-AREA-ENV-12` | `ENV-CIV` |
| `G5-AREA-ENV-13` | `ENV-GEO` |
| `G5-AREA-ENV-14` | `ENV-CIV` |
| `G5-AREA-ENV-15` | `ENV-CIV` |
| `G5-AREA-ENV-16` | `ENV-CIV` |

Conflict. `G5-AREA-ENV-05` lists `ENV-PHY` and `ENV-CIV`. Both exist and both are at most 16 characters. Outcome links under that area resolve only to `ENV-PHY`. The lesson id has no crosswalk row. This plan does not pick one parent.

Conflict. `G5-AREA-MAT-14`'s coverage list and its cited competency both say `APT-DIR`. The three outcome slots on its draft mission are `supplied_area_match=false` and crosswalk to `MAT-DAT`. Those slots are not this area's parent. The directions game uses `APT-DIR` and does not use those slots as its round.


There is no field named `canonical_skill_id`. The evidence row stores `skill_code` and `universal_skill_id` (`LearnerEvidenceOutboxModel` in `backend/app/gamification/infrastructure/db/models.py`, `universal_skill_id` is `String(16)`). The learning-flow publisher currently writes `universal_skill_id="MAT-FRC"` for every score (`backend/app/gamification/application/learning_flow_orchestration.py`). An area game must send its own settled parent, not that hardcoded fractions id.

### Knowledge tracing

Owning module: `knowledge_tracing`. Gamification reads mastery only through `MasteryProvider`.

`MasteryProvider.get_mastery` takes `MasteryRetrievalRequest` with `learner_id` and `skill_id`, and returns `MasteryResult` with `learner_id`, `skill_id`, `status`, and `mastery` (`backend/app/knowledge_tracing/application/mastery.py`). `KnowledgeTracingMasteryGateway` in `backend/app/gamification/infrastructure/gateways/knowledge_tracing_mastery.py` translates the gamification skill through the crosswalk, calls that provider with the Universal id, and returns `SkillMasteryEvidence` (`learner_id`, `skill_id`, `universal_skill_id`, `mastery_probability`, `model_version`, `contract_version`) or `None`. `uncertainty` and `observed_at` stay empty because `MasteryResult` does not carry them. A missing crosswalk, an id outside the taxonomy, a provider exception, or a status other than `AVAILABLE` is a recorded absence. It does not reject the episode.

A scored attempt emits one `gamification_item_scored` event. `SqlAlchemyLearningFlowEvidencePublisher.publish` in `backend/app/gamification/infrastructure/db/learning_flow_gateways.py` sets `event_type="gamification_item_scored"` and the idempotency key `<attempt_id>:gamification_item_scored`. The learning-flow payload fields are `attempt_id`, `correct`, `difficulty`, `response_time_ms` (nullable), `supported`, `hint_count`, `environment`, and `model_ingestion_eligible`, plus `learner_id`, `skill_id`, `universal_skill_id`, `episode_id`, `presentation_id`, `measurement_role`, `assistance_state`, `earned_score`, `maximum_score`, `scoring_version`, `difficulty_source`, `difficulty_mapping_version`, and `session_id`.

`correct` is the server result. Development and test set `model_ingestion_eligible` false; the learning-flow publisher hardcodes `false`. `environment` is the runtime environment. Normalized difficulty on this path is `difficulty="easy"` with `difficulty_mapping_version="learning_flow-introductory-v1"` when the source band is `introductory`. The v2 contract also names `difficulty_numeric` and the mapping `1→easy`, `2→medium`, `3→hard` under `pilot-difficulty-v1` (`LearnerEvidenceContract` in `backend/app/gamification/api/contracts.py`).

One attempt is correct only when every part is correct. That rule is `combine_parts` in `backend/app/knowledge_tracing/application/grading/combine.py`: status `correct` only when every part status is `correct`. The same sentence is in `backend/app/knowledge_tracing/application/submissions.py`. A new area game's server rubric follows that rule. The game does not write Knowledge Tracing tables.

Conflict. `ServerAuthoritativeScorer` compares one `response` string with one `correct_response` and sets the full `maximum_score` or zero. The learning-flow payload sets `correct` from `earned_score == maximum_score`. That matches the every-part rule for a one-part item. It is not a multi-part combiner. A multi-part area item must be correct only when every part is correct; a partial part score must not set `correct` true.

Conflict. `LearnerEvidenceContract.event_type` allows `attempt_summary`, not `gamification_item_scored`. The outbox publisher uses `gamification_item_scored` and does not validate the payload as that contract. The v2 `attempt_summary` payload requires `difficulty_numeric`; the learning-flow publisher does not send `difficulty_numeric`. The area game emits `gamification_item_scored` with the learning-flow fields above, including a normalized `difficulty`.

Conflict. `hint_count` on the integration contract is 0 or 1. The episode store writes 1 when `learner_requested_help` is true and 0 otherwise. The learning-flow scorer currently writes `hint_count` 0. The `item_responses` check is only `hint_count >= 0`. The area game sends 0 or 1.

### Learner state

Owning module: `learner_state`, read at answer time through the gamification gateway.

The optional visual snapshot is `VisualFeatureWindow` in `backend/app/gamification/api/router.py` and `VisualFeatures` in `backend/app/learner_state/api/schemas.py`. The 11 fields are `mean_eye_openness`, `std_eye_openness`, `mean_gaze_ratio`, `std_gaze_ratio`, `mean_pitch`, `mean_yaw`, `mean_roll`, `mean_abs_pitch`, `mean_abs_yaw`, `mean_abs_roll`, and `face_visibility_ratio`. `face_visibility_ratio` is `ge=0` and `le=1`. The gamification window sets `allow_inf_nan=False` on every value. The snapshot is sent only after a current consent row for purpose `learner_state_camera` (`session_play.py` calls `get_consent(learner_id, purpose="learner_state_camera")`). No raw image, video, landmarks, or biometric id is accepted.

`recommended_action` in `LearnerStateResponse` is `none`, `monitor`, `request_tutor_support`, `request_reengagement_support`, or `collect_more_evidence`. `StruggleTrigger` records `LEARNER_STATE_TUTOR_SUPPORT` and `LEARNER_STATE_REENGAGEMENT_SUPPORT` as different reasons (`backend/app/gamification/application/struggle_trigger.py`). Those two recommendations stay distinct.

A missing learner-state result must not reject the answer. `ResponseRequest` drops an invalid `visual` object and continues. `_record_learner_state` returns `None` when consent, the gateway, or the call fails, and the score is already stored.

The game must not fabricate `overlap_time`, `first_action`, `position`, `original`, or `task_progress`.

Conflict. `BehaviourFeatures` in `backend/app/learner_state/api/schemas.py` requires `overlap_time` and `original`, and `extra="forbid"` rejects `first_action` and `position`. `task_progress` is optional. `behaviour_from_game_answer` in `backend/app/learner_state/infrastructure/game_answers.py` sets `overlap_time` from `response_time_ms` and `original` to `1.0`. `GameAnswerRecorder` sets `task_progress=None`. The integration note says those behaviour fields are not agreed and must not be fabricated. An area game must not call that mapping. It must not send invented values for those five names. `first_action` and `position` are not fields on `BehaviourFeatures`.

Conflict. The integration note names the non-request recommendation `collect_more`. The code literal is `collect_more_evidence`.

### Adaptive tutor

Owning module: `adaptive_tutor`. Architecture lists it as not consumed by gamification (`docs/architecture.md`).

The area game does not call the tutor to choose a scaffold. The support type comes from that area's eligible set. `request_tutor_support` is recorded as `LEARNER_STATE_TUTOR_SUPPORT`. That record does not generate tutor text inside the game, and it does not set `assistance_state` to `tutor_active`.

Conflict. `AuthoringDesk.build_feature_snapshot` in `backend/app/gamification/application/delivery.py` calls `tutor.latest_outcome(learner_id, skill_id, as_of)` and stores whether a token was present. `LocalTutorGateway.latest_outcome` returns a stored token, not generated tutor text, and it does not choose a scaffold. An area game must not extend that call into tutor text or into scaffold selection.

### Area support catalog

Owning module: gamification content. `assignment` and `AreaSupportCatalog.choices` in `backend/app/gamification/content/area_support_catalog.py`. The machine copy is `data/gamification/grade5-area-support-catalog/v1/area_support_types.jsonl` (54 rows). `load_area_support_catalog` is fail-closed in production.

The model may choose only `eligible_support_types` for that area. The legal game types are `visual_guidance`, `worked_parallel_example`, and `step_by_step_guidance`. Verbal-relation areas `G5-AREA-SIN-03` through `G5-AREA-SIN-10` receive only `worked_parallel_example` and `step_by_step_guidance`. `visual_guidance` is absent there. Tutor-only types (`independent_retry`, `metacognitive_prompt`, `conceptual_hint`, `targeted_hint`, `full_explanation`) and `concept_reminder` stay outside the set.

A new mapped area game supplies one chosen type from that tuple and renders it under the area's `rendering_constraint`. It does not add a type.

Conflict. The catalog has no row for `G5-AREA-SIN-11` or `G5-AREA-SIN-12`, and `assignment` raises before the Sinhala branch. The placeholder games still need a playable eligible set, so this plan reuses the three-type non-verbal Sinhala set. The current function does not return that set.

### Participation rewards

Owning module: gamification. Participation rewards stay separate from unsupported scores and Independence Gain.

`ParticipationRewardContract` in `backend/app/gamification/api/research_contracts.py` has `reward_id`, `learner_id`, `episode_id`, `reward_type`, `amount`, `academic_mastery_evidence` fixed to false, and `awarded_at`. `IndependentEvidenceContract` is a different record: `measurement_role` is an unsupported or retention role, and `assistance_state` is `none`. Independence Gain is `raw_independence_gain` from unsupported-after proportion minus unsupported-before proportion. Supported correctness is not that reward.

The stored participation row is `LearningRewardEntryModel` (`learning_reward_entries`): `id`, `learner_id`, `episode_id`, `points`, `reason_code`, `created_at`. It has no score column. The child response `ParticipationReward` has `points` and `reason` (`backend/app/gamification/api/learning_flow_router.py`).

A new area game may award `points` with a `reason` or `reason_code` for participation. It must leave `academic_mastery_evidence` false. It must not add those points to `earned_score`, `unsupported_before`, `unsupported_after`, or `raw_independence_gain`.

Conflict. The research contract uses `reward_type` and `amount`. The table and the child response use `points` with `reason_code` or `reason`. An area game uses the stored `points` and `reason_code` and does not treat `amount` as a second balance.
