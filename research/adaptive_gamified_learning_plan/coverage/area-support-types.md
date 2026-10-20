# Support types for each Grade 5 skill area

This catalog tells the game model which support types it may choose for each mapped skill area. It is a development assumption so the missions can be built before an educator reviews them. It is not an expert recommendation, and it does not approve a scaffold or open child delivery.

The machine copy is `data/gamification/grade5-area-support-catalog/v1/`. Production refuses that package. A development or test caller can read it only with `allow_draft=True`.

## Support types the game can show

Model 2 and the phone client accept these three types:

| Type | What the game shows |
| --- | --- |
| `visual_guidance` | A diagram, highlight, grouping, or picture of the structure. The scored answer stays hidden. |
| `worked_parallel_example` | A solved example of the same kind of task, with different numbers, words, or objects. |
| `step_by_step_guidance` | Short prompts. The learner does the next step, and the prompt stops before the result. |

The game model chooses only those three types. `independent_retry`, `metacognitive_prompt`, `conceptual_hint`, `targeted_hint`, and `full_explanation` belong to the tutor. `concept_reminder` is stored on some content records, and the phone client rejects it, so it stays outside this set.

## How an area gets its set

Every mapped area receives at least two types, so the model still has a choice.

| Rule | Areas | Candidate set | How the support stays off the scored answer |
| --- | --- | --- | --- |
| Quantity, measure, or arrangement | All 16 mathematics areas | All three | The picture shows the structure. The worked example uses different quantities. Each step pauses before the result. |
| Letter, sign, or grammatical form | Sinhala areas whose observable is a mark, letter, word form, or sentence slot | All three | Highlight the mark already in the prompt. The worked example uses a different word with the same pattern. |
| Verbal relation | Riddles, synonyms, antonyms, paired words, proverbs, idioms, maxims, and similes | Worked parallel example and step-by-step guidance | Visual guidance stays out of this set because a picture of the relation would state the scored answer. The worked example uses a different saying or word pair. |
| Invitation structure | Invitation letters | All three | The picture shows greeting, message, and close. The worked example uses a different event. |
| Observable situation | All 16 Environmental Studies areas | All three | The picture shows the object or situation and does not mark the scored choice. |

`G5-AREA-SIN-11` and `G5-AREA-SIN-12` have no Grade 5 source, so they have no row.

## The 55 mapped areas

| Area | Name | Game | Rule | Support types the model may choose |
| --- | --- | --- | --- | --- |
| `G5-AREA-MAT-01` | Numbers | `market_mission` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-02` | Addition | `addition_adventure` (five textbook-derived games) | Quantity, measure, or arrangement | activity-specific deterministic visual guidance, exact worked visual, step-by-step guidance |
| `G5-AREA-MAT-03` | Number Patterns | `number_pattern_adventure` (dedicated mapped-draft package; `pattern_temple` remains catalogue fallback) | Six code-rendered +2/+4, −2/−4, ×2, ×3, ×4, and ×5 sequence-construction challenges | increasing/×2: visual guidance → exact worked visual → explicit guided steps; decreasing/×3/×4/×5: exact worked visual → visual guidance → explicit guided steps |
| `G5-AREA-MAT-04` | Subtraction | `subtraction_adventure` (dedicated mapped-draft package; `market_mission` remains the catalogue fallback) | Place-aligned subtraction, expanded form, one regroup, repository-draft two regroups, and two non-equivalent story relationships | no-regroup, expanded, and both stories: visual guidance → exact worked visual → explicit guided steps; one and two regroups: exact worked visual → visual guidance → explicit guided steps |
| `G5-AREA-MAT-05` | Fractions | `half_set` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-06` | Multiplication | `market_mission` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-07` | Time | `parcel_workshop` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-08` | Division | `market_mission` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-09` | Length and Distance | `parcel_workshop` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-10` | Money | `market_mission` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-11` | Volume and Capacity | `parcel_workshop` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-12` | Measuring Weight | `parcel_workshop` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-13` | Shapes and Solid Objects | `pattern_temple` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-14` | Directions | `pattern_temple` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-15` | Decimals | `market_mission` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-MAT-16` | Roman Numerals | `word_workshop` | Quantity, measure, or arrangement | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-01` | Identifying Vowel Signs | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-02` | Identifying Punctuation Marks | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-03` | Riddles | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-04` | Synonyms | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-05` | Antonyms | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-06` | Paired Words | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-07` | Proverbs | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-08` | Idiomatic Expressions | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-09` | Wise Sayings and Maxims | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-10` | Similes | `word_workshop` | Verbal relation | worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-13` | Invitation Letters | `story_studio` | Invitation structure | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-14` | Feminine and Masculine Nouns | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-15` | Singular and Plural Words | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-16` | Spelling and Orthography | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-17` | Usage of න and ණ | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-18` | Usage of ල and ළ | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-19` | Usage of ස, ශ and ෂ | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-20` | Unaspirated and Aspirated Consonants | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-21` | Nouns | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-22` | Verbs | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-23` | Subject and Non-subject Forms | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-24` | Simple Sentences | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-SIN-25` | Sentence Patterns Using ද, ත, ස, හා and සහ | `word_workshop` | Letter, sign, or grammatical form | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-01` | Our Well-being | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-02` | We Are Sri Lankans | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-03` | Plants and Trees | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-04` | Animals Around Us | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-05` | Things We Use | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-06` | Our Food | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-07` | Safety and Care | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-08` | Water | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-09` | Ways to Make Work Easier | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-10` | Home Garden | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-11` | Transportation | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-12` | Human Behaviour | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-13` | Earth and Sky | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-14` | Changes We Can Make | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-15` | Humans and Information | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
| `G5-AREA-ENV-16` | Stories from Our Past | `eco_explorer` | Observable situation | visual guidance, worked parallel example, step-by-step guidance |
