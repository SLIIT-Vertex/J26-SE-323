# Multi-help support rounds: Mathematics and English

Development only. Nothing here is educator-reviewed, every episode stays
`model_ingestion_eligible: false`, and Sinhala and Environmental Studies games keep their single-help
flow in this pass.

**The server chooses the help type and the help order. The phone only renders the returned
`scaffold_type`.** The phone posts the supported answer (`/support/answer`) and the end of a
demonstration (`/support/complete`); any type or order a client sends is ignored. The response
carries the current `scaffold_type`, its `english_tag_key`, whether another round was opened
(`another_round_required`), and when withdrawal is allowed (`withdrawal_allowed`). It never
carries the order or a type the server has not opened yet. The scored before and after items
never carry their answer; a help stage carries its own item's answer so the board can show it (see
"The answer inside help").

## The orders

Model 2 puts first the type that answers Model 1's reason for the difficulty. The other types follow
the subject's fallback order, skipping types already used in the episode and types this game cannot
render for this item. In the proposed condition, the type with the best record of *valid
post-withdrawal* outcomes for this learner and skill moves to the front instead. Supported
correctness is stored for audit but is never that signal. The baseline condition uses the fallback
order unchanged. Code: `backend/app/gamification/modeling/support_selection/support_order.py`
(`MATHEMATICS_ORDER`, `ENGLISH_ORDER`, `LEAD_BY_REASON`).

| Position | Mathematics | English |
|---|---|---|
| 1 | `visual_guidance` | `visual_guidance` |
| 2 | `step_by_step_guidance` | `simpler_same_game` |
| 3 | `conceptual_reexplanation` | `step_by_step_guidance` |
| 4 | `simpler_same_game` | `conceptual_reexplanation` |
| 5 | `prerequisite_repair` | `prerequisite_repair` |
| 6 | `worked_parallel_example` | `worked_parallel_example` |

**Why this Mathematics order.** The goal is the fresh item with no help, so the order starts with
help that leaves the child doing all of the reasoning on their own task, and only then changes the
task. Visual guidance shows the structure and nothing else. Guided reasoning narrows the steps with
questions, but the child still answers. A conceptual re-explanation is for a child whose cues did not
land because the idea itself is not yet in place. The simpler version keeps the same skill with
easier quantities, which changes the task, so it comes after the help that keeps the task.
Prerequisite repair leaves the skill altogether: it is slow and its effect on the failed skill is
indirect. The worked example is a complete solution to a different problem. It is the most
answer-adjacent and the most passive help, so it is the last resort before withdrawal.

**Why English differs.** The English games ask the child to recall a word's meaning and link it
among several look-alike choices (words to pictures, headings, places or turns). When pointing at
the picture has not worked, the number of choices is usually what is in the way. A successful link
with fewer choices is the same recall the fresh item will ask for, and the child then returns to
the full set. So the simpler version moves up to second. Guided questions and a re-explanation of
the meaning follow. Prerequisite repair (the area's earlier word skill) and the worked example (a
different word set linked in full) stay last, for the same reasons as in Mathematics.

**First type by Model 1's reason.** Each subject groups its Model 1 labels into five kinds of
difficulty, and each kind leads with one type. The grouping differs by subject; for example, an
English `*_word_visual_confusion` is a misread picture, while a Mathematics `*_confusion` is usually
two units or two operations treated as one.

| Kind of difficulty | First type | Mathematics example | English example |
|---|---|---|---|
| representation | `visual_guidance` | place shift, misread scale | word–picture or look-alike confusion |
| procedure | `step_by_step_guidance` | carry or exchange omitted | word or turn order, omission |
| relation | `conceptual_reexplanation` | unit or operation confusion | wrong heading, function or meaning |
| prerequisite | `prerequisite_repair` | fact recall, denomination | English–Sinhala word, plural or spelling form |
| unclear (or low-confidence Model 1) | `simpler_same_game` | unknown | unknown, several valid answers |

A test checks that every Model 1 label of every Mathematics and English area falls into one of these
five kinds.

## Shared switch rule (S) and withdrawal rule (W)

These apply to every row below.

**S, the switch rule.**
1. The before item is shown with `assistance_state: none`. If the server detects no difficulty, the
   episode ends through the normal success path.
2. On a detected difficulty, Model 1 runs, then Model 2 fixes the order, then the first type opens.
3. The child works inside the help, and the server scores the supported attempt.
4. A wrong attempt closes that round and opens the next unused, renderable type in the order. A
   correct attempt stops the loop.
5. The simpler version is gated: success on the easier item returns the child to the failed item
   within the same round, and only success there stops the loop. A wrong answer on the easier item
   ends that round.
6. Prerequisite repair runs the earlier-skill item, then returns to the failed item within the same
   round.
7. No type repeats within an episode. After the last type, the loop stops whatever the outcome.

**W, the withdrawal rule.** Withdrawal is allowed only after a supported success or after the last
type. The phone must remove the support frame, any highlight, any worked solution, any leftover
answer state and every input handler. It then acknowledges `all_support_removed`,
`answer_revealing_state_cleared` and `input_handlers_cleared`, and only then does the server present
a fresh, unseen unsupported-after item. Model 3 measures that item alone. The chosen order, the
types used and that outcome are stored for Model 2's later preference.

**ACID.** Each request is one transaction. It covers the score, one `learning_flow_support_rounds`
row per delivered type, the episode state and the idempotency receipt. The episode row is locked
(`SELECT … FOR UPDATE`) and written against its expected revision. Any failure, including a failed
build of the next type, rolls back every write. A retry with the same idempotency key returns the
stored response and opens no new round. An overlapping answer that still points at a closed round's
item is rejected as stale.

## What each type shows

The help is mounted in the game's own activity component, under a small English tag at the top
right (`support-round-tag`, `lang="en"`). The type is named only by that tag; the Sinhala name of
the type is not repeated on screen. Instructions to the child stay in the game's language
(Sinhala). The tag and the activity change together when the type changes. The words are in
`backend/app/gamification/application/support_builders/cues.py`, one set for each subject.

| Type | Tag | On the phone |
|---|---|---|
| `visual_guidance` | Visual guidance | The failed item again in the same activity, with the game's own visual cues for that item. Any cue line that carries the scored answer is removed. |
| `step_by_step_guidance` | Guided reasoning | The failed item again, with five short questions plus one aimed at Model 1's reason, each answered for this game: the first by the game's prompt, the middle ones by the game's solving steps, the last by the real answer. |
| `conceptual_reexplanation` | Conceptual re-explanation | The failed item again, after the idea is said another way (an analogy chosen by Model 1's reason). |
| `simpler_same_game` | Simpler version | An easier, unseen item of the same skill in the same activity, then the failed item (gated, see S5). |
| `prerequisite_repair` | Prerequisite repair | An item of the area's previous skill in that skill's own activity, then the failed item. |
| `worked_parallel_example` | Worked example | A different item of the same skill, shown already solved in the same activity: its answer is marked on the board, the board cannot be touched, and the solution and steps are listed. The child does nothing but watch. Its answer is never the failed item's answer. The child then tries the failed item. |

**The answer inside help.** Every stage the child plays inside help (all types but the worked
example's demonstration) carries `activity.answer` with `mode: "tint"`: the item's real answer as
readable `lines` and as `marks`, the labels on the board that make up the answer. The phone tints
those labels faintly on the board and shows the lines in a faint strip below it. The worked example
carries the same with `mode: "filled"`, drawn strongly. The lines and marks are built from the
game's own solution by `support_builders/answer_reveal.py`: board tokens become the words or
picture names the child sees, and values the board already states (the two numbers to multiply)
are left out. A board element is tinted when its visible label equals a mark, so a picture card
with no words is not tinted itself; its answer is still in the lines.

`simpler_same_game` and `prerequisite_repair` are different. The first stays on the failed skill
and makes it easier. The second leaves for the previous skill and comes back.

**How a simpler version is made.** Each content module has `generate_simpler_item`, which builds a
fresh-seed item of the same skill at its easiest setting. The English modules also receive the
failed game and keep fewer pairs than it had. If the module has no simpler form for that item, the
builder looks for an ordinary item of the same skill with fewer objects or smaller numbers. If there
is none, the type is not renderable for that episode and is skipped. In the tables below, "none"
means the skill is already the smallest task of its kind.

**Prerequisite repair** uses the skill just before the failed one in the area's teaching order. The
first skill of each area, and every skill of a one-skill area, has no earlier skill, so the type is
skipped there.

**The order used in a row** is always: Model 1's lead type, then the subject order, minus the types
the row marks as not renderable.

---

## Mathematics (16 areas)

Eligible types for every area: all six (`MATHEMATICS_SUPPORT_TYPES`). Order: `MATHEMATICS_ORDER`,
led by Model 1's reason. Switch rule S, withdrawal rule W. Every screen mounts its game component
inside `SupportRoundFrame` and uses `answerSupported` / `completeSupport` / `withdrawSupport` /
`presentAfter` from the learning-flow client.

### G5-AREA-MAT-01 · `NumberWorldFlow` · `NumberWorldJourney`
Visual, guided and conceptual help: the place-value harbour, abacus, expanded table, kite or river
activity again, with the place or route cues.

| Skill | Simpler version | Prerequisite repair | Not renderable |
|---|---|---|---|
| NUM-POSITION | 3-digit number | none (first) | prerequisite |
| NUM-REPRESENTED | 4-digit number | NUM-POSITION | — |
| NUM-100000 | 999 + 1 on a shorter ladder | NUM-REPRESENTED | worked example (one fixed item) |
| NUM-ABACUS | 3-digit number with a zero | NUM-100000 | — |
| NUM-EXPAND | 3-digit number with a zero | NUM-ABACUS | — |
| NUM-EXTREME | 3 digits (none if the failed item had 3) | NUM-EXPAND | — |
| NUM-LEADING-ZERO | 3 digits (none if the failed item had 3) | NUM-EXTREME | — |
| NUM-ORDER | 3 numbers to order instead of 4 | NUM-LEADING-ZERO | — |

### G5-AREA-MAT-02 · `AdditionAdventureFlow` · `AdditionAdventureJourney`
Visual, guided and conceptual help: the fruit groups, tuk-tuk trail, carrying columns, delivery or
festival table again.

| Skill | Simpler version | Prerequisite repair | Not renderable |
|---|---|---|---|
| ADD-MENTAL | a fact within ten, smaller than every textbook fact | none (first) | prerequisite |
| C06-L01-O01 / O02 / O03 | same addend count with one carry | the previous column skill | — |
| ADD-RUNNING-TOTAL | 4 stops instead of 7 | C06-L01-O03 | — |
| ADD-CONTEXT | three two-digit groups | ADD-RUNNING-TOTAL | — |
| ADD-TABLE-TOTAL / DIFFERENCE / MAX | same table with two-digit counts | the previous table skill | — |

### G5-AREA-MAT-03 · `NumberPatternsFlow` · `NumberPatternJourney`
Visual, guided and conceptual help: the step trail, bridge or power machine with the rule
highlighted. Simpler version for every skill: the same rule and operation, 4 small terms, one blank.
Prerequisite repair: the previous pattern skill (none for PAT-DIFF-ASC). This area now runs the loop:
before this pass it was keyed by the wrong experience id and silently kept single help.

### G5-AREA-MAT-04 · `SubtractionAdventureFlow` · `SubtractionAdventureJourney`
Visual, guided and conceptual help: the place-value board, exchange workshop or difference story.

| Skill | Simpler version | Prerequisite repair |
|---|---|---|
| SUB-NO-REGROUP | 2 columns | none (first) |
| SUB-EXPANDED | 3 columns, no zero | SUB-NO-REGROUP |
| C07-L01-O01 | 3 columns, one exchange into ones | SUB-EXPANDED |
| C07-L01-O02 | 3 columns, the two exchanges it needs | C07-L01-O01 |
| SUB-DIFF-BETWEEN / HOW-MANY-MORE | 3-column story, no exchange | the previous skill |

### G5-AREA-MAT-05 · `FractionAdventureFlow` · `FractionAdventureJourney`
The existing fraction flow. `G5-MAT-C03-L01-O01` stays its one halves-of-a-set skill; no second
fractions skill was added. Visual, guided and conceptual help: the equal-share studio, quarter
orchard or tenths mosaic.

| Skill | Simpler version | Prerequisite repair | Not renderable |
|---|---|---|---|
| FRC-HALF-WHOLE | none (one half of a whole) | none (first) | simpler, prerequisite |
| C03-L01-O01 | 4 or 6 apples to halve | FRC-HALF-WHOLE | — |
| FRC-QUARTER-WHOLE | none (one quarter of a whole) | C03-L01-O01 | simpler |
| C03-L01-O02 | 4 or 8 apples in quarters | FRC-QUARTER-WHOLE | — |
| FRC-QUARTER-TABLE | table for 4 or 8 | C03-L01-O02 | — |
| FRC-TENTHS-BUILD | shade 1 or 2 tenths | FRC-QUARTER-TABLE | — |
| FRC-TENTHS-READ | 1 to 3 tenths shaded in a row | FRC-TENTHS-BUILD | — |

Fixed in this pass: the worked solution for a tenths-build item used to shade nothing.

### G5-AREA-MAT-06 · `MultiplicationAdventureFlow` · `MultiplicationAdventureJourney`
Visual, guided and conceptual help: the table explorer, column workshop or story mission. Simpler
version: facts within 5 × 5; written skills keep their multipliers with a two-digit multiplicand;
the story uses 2–5 per group and 2–4 groups. Prerequisite repair: the previous skill (none for
MUL-TABLE).

### G5-AREA-MAT-07 · `TimeAdventureFlow` · `TimeAdventureJourney`
Visual, guided and conceptual help: the unit matcher, clock, 24-hour board or journey timeline.
Simpler version: 2 unit pairs instead of 4; o'clock or half past; a whole afternoon hour to convert;
a one-hour or one-and-a-half-hour journey from the hour; arithmetic with one regroup and smaller
times. Prerequisite repair: the previous skill (none for TIME-UNITS).

### G5-AREA-MAT-08 · `DivisionAdventureFlow` · `DivisionAdventureJourney`
Visual, guided and conceptual help: the equal-share objects, paper-division workbench or basket
story. Simpler version: 6–10 objects shared by 2; divisor 2 or 3 with a two-digit quotient; a
basket story of 3 per basket with 3–4 baskets. Prerequisite repair: the previous skill (none for
DIV-SHARE).

### G5-AREA-MAT-09 · `DistanceAdventureFlow` · `DistanceAdventureJourney`

| Skill | Simpler version | Prerequisite repair | Not renderable |
|---|---|---|---|
| LENGTH-RELATION | none (one fixed km–m fact) | none (first) | simpler, prerequisite, worked example |
| LENGTH-CONVERT | whole kilometres (1000, 2000, 3000 m) | LENGTH-RELATION | — |
| LENGTH-ADD / SUBTRACT / PROBLEM | km and m with no exchange | the previous skill | — |

### G5-AREA-MAT-10 · `MoneyAdventureFlow` · `MoneyAdventureJourney`
Simpler version: 4 coins and notes to sort instead of 10 (scoring now follows the item's own
tokens); Rs 15–30 to make; whole-rupee sums with no carrying; one of each of two products and no
change. Prerequisite repair: the previous skill. MONEY-DENOMINATION has no prerequisite and no
worked example (it has one fixed layout).

### G5-AREA-MAT-11 · `CapacityAdventureFlow` · `CapacityAdventureJourney`
Simpler version: 200 or 500 ml to read; make 500 ml from 100, 250 and 500 ml portions; whole litres
to convert; no-regroup arithmetic; deliver 1 or 1.5 l. Prerequisite repair: the previous skill.
CAPACITY-READ has no prerequisite; CAPACITY-COMPOSE has no worked example (one fixed target).

### G5-AREA-MAT-12 · `MassAdventureFlow` · `MassAdventureJourney`
Simpler version: 2 instruments to choose between instead of 5; balance 500 g, 1 kg or 2 kg; whole
kilograms to convert; no-regroup arithmetic; a 1 kg and a 500 g parcel in a 2 kg cart.
Prerequisite repair: the previous skill (none for MASS-INSTRUMENT).

### G5-AREA-MAT-13 · `ShapeAdventureFlow` · `ShapeAdventureJourney`
Simpler version: the property table, or net matching, for a cube and a cylinder only; one horizontal
and one vertical picture. Prerequisite repair: the previous skill (none for SHAPE-TABLE). There is
no worked example for SHAPE-TABLE or SOLID-NET (one fixed set of solids).

### G5-AREA-MAT-14 · `DirectionAdventureFlow` · `DirectionAdventureJourney`
Simpler version: 2 compass positions instead of 4; in the scene, all eight places stay but the child
names only the four in the main directions (the scene validator now accepts a subset of
statements). Prerequisite repair: the previous skill (none for DIRECTION-MAIN). There is no worked
example (one fixed compass or scene per role).

### G5-AREA-MAT-15 · `DecimalAdventureFlow` · `DecimalAdventureJourney`
Simpler version: 2 readings to match instead of 4; 1 or 2 tenths to shade, convert or write.
Prerequisite repair: the previous skill (none for DECIMAL-READ).

### G5-AREA-MAT-16 · `RomanAdventureFlow` · `RomanAdventureJourney`
Simpler version: 3 values up to V to match; 2–4 emoji to count; sums no larger than III. Prerequisite
repair: the previous skill (none for ROMAN-MATCH).

---

## English (18 areas)

Eligible types for every area: all six (`ENGLISH_SUPPORT_TYPES`, rule `word_meaning_link`). Order:
`ENGLISH_ORDER`, led by Model 1's reason read with the English grouping. Switch rule S, withdrawal
rule W. Every screen mounts its game board inside `SupportRoundPlay` (the shared frame plus the
game's own check button) and uses the shared `useSupportRound` hook for the supported answer, the
end of a demonstration and the withdrawal handoff. `chooseMission` in `MobileLearningApp.tsx` opens
the screen whose own `area_id` matches.

In every English row, visual guidance repeats the game's own picture and word cues; guided reasoning
asks what the picture shows, which word names it, and checks each link, plus one question aimed at
Model 1's reason; the conceptual re-explanation restates the meaning or category through an everyday
analogy; and the worked example links a different word set in full.

**The English simpler version (the "fewer pairs" rule).** The child gets a fresh item from the same
game with about half as many links as the failed one, and always fewer.
- Sorting games keep at least one entry under every heading.
- When only one link is left, one other target stays on screen, so it is still a choice.
- Linking to that distractor scores as wrong. The validators now accept any shown target instead of
  rejecting it as a forged token.

Code: `backend/app/gamification/content/simpler_items.py`.

| Area | Flow | Screen | Skills (teaching order) | Simpler version | Prerequisite repair | Not renderable |
|---|---|---|---|---|---|---|
| ENG-01 | `ClassroomActionQuestFlow` | `ClassroomActionQuest` | BEH-POSTURE → DESTINATION → RETURN | 2 choices: the commanded pose or place and one other (the classroom shows only the allowed places) | previous skill | prerequisite for POSTURE |
| ENG-02 | `SriLankaDiscoveryFlow` | `SriLankaDiscovery` | SL-VOCAB-RECOGNITION → NATIONAL-PAIR → CULTURAL-GROUP | fewer labels or pairs; fewer members in each group | previous skill | prerequisite for VOCAB |
| ENG-03 | `PlantExplorerFlow` | `PlantExplorerQuest` | PLANT-VOCAB → PARTS → NUMBER | fewer words, parts or singular–plural pairs | previous skill | prerequisite for VOCAB |
| ENG-04 | `WildlifeRangerFlow` | `WildlifeRangerQuest` | ANIMAL-VOCAB → GROUP → PARTS | fewer animals, entries (every heading kept) or parts | previous skill | prerequisite for VOCAB |
| ENG-05 | `EverydayObjectQuestFlow` | `EverydayObjectQuest` | OBJECT-VOCAB → PLACE → NAME | fewer objects; fewer entries (both places kept); for NAME a shorter name if one exists | previous skill | prerequisite for VOCAB; simpler for a 2-chunk NAME |
| ENG-06 | `IslandFoodFestivalFlow` | `IslandFoodFestival` | FOOD-VOCAB → GROUP → NAME | fewer foods; fewer entries (every stall kept); for NAME a 2-chunk name when the failed one had 3 | previous skill | prerequisite for VOCAB; simpler for a 2-chunk NAME |
| ENG-07 | `RainbowWardrobeQuestFlow` | `RainbowWardrobeQuest` | CLOTHES-VOCAB | fewer garments | none (one skill) | prerequisite |
| ENG-08 | `WaterWorksAdventureFlow` | `WaterWorksAdventure` | WATER-ACTION | fewer action–scene links | none (one skill) | prerequisite |
| ENG-09 | `TransitTerminalQuestFlow` | `TransitTerminalQuest` | TRANSPORT-VOCAB | fewer vehicles | none (one skill) | prerequisite |
| ENG-10 | `BloomBuilderGardenFlow` | `BloomBuilderGarden` | FLOWER-VOCAB | fewer flowers | none (one skill) | prerequisite |
| ENG-11 | `WorkplaceLinkCityFlow` | `WorkplaceLinkCity` | WORK-VOCAB → WORK-PLACE | fewer words; fewer occupation–place links | previous skill | prerequisite for VOCAB |
| ENG-12 | `FamilyWordConstellationFlow` | `FamilyWordConstellation` | FAMILY-BILINGUAL | fewer English–Sinhala links | none (one skill) | prerequisite |
| ENG-13 | `EarthSkyExplorerFlow` | `EarthSkyExplorer` | EARTHSKY-BILINGUAL → VISUAL | fewer links or scenes | previous skill | prerequisite for BILINGUAL |
| ENG-14 | `BlueprintQuestFlow` | `SchoolHomeBlueprintQuest` | PLACE-VOCAB → GROUP → NAME | fewer places; fewer entries (every heading kept); NAME as ENG-05 | previous skill | prerequisite for VOCAB; simpler for a 2-chunk NAME |
| ENG-15 | `InformationStationFlow` | `InformationStation` | INFO-BILINGUAL → VISUAL | fewer links; one link with a distractor when the failed item had two | previous skill | prerequisite for BILINGUAL |
| ENG-16 | `HeritageMuseumQuestFlow` | `HeritageMuseumQuest` | PAST-BILINGUAL → VISUAL | fewer links or exhibits | previous skill | prerequisite for BILINGUAL |
| ENG-17 | `ClassroomLanguageLiveFlow` | `ClassroomLanguageLive` | CLASS-FUNCTION → COMMAND → CONTEXT → QUESTION | fewer expressions (every heading kept); fewer situation links; QUESTION a shorter question if one exists | previous skill | prerequisite for FUNCTION; simpler for COMMAND (two actions already) |
| ENG-18 | `ConversationStreetFlow` | `ConversationStreet` | CONV-PAIR → TURN → FRAME → DESCRIBE | one question with two replies; the dialogue without its last turn; DESCRIBE a shorter reply if one exists | previous skill | prerequisite for PAIR; simpler for FRAME (a reply sentence cannot be cut) |

Sentence chunks are never cut to make a simpler version, because a cut sentence is no longer
English. Whole dialogue turns can be dropped, so CONV-TURN uses the dialogue's opening turns.

## Evidence

- Backend: `backend/tests/gamification/test_multi_help_support_loop.py` (escalation, idempotency,
  rollback, Model 3 and history on one game) and `test_multi_help_subjects.py`. The second file
  checks:
  - every Mathematics and English flow runs the loop with its own simpler generator;
  - every skill's designed simpler item is the same skill, scoreable, and (for English) smaller;
  - the full wrong-answer order on four games, including ENG-01, 06 and 17;
  - English withdrawal and Model 3;
  - stale overlapping answers;
  - simpler versus prerequisite;
  - the fewer-pairs rule, the English reason grouping and order, and the history preference.
- Phone: `SupportRoundFrame.test.tsx` checks all six English tags and the hidden check button during
  a demonstration. `IslandFoodFestivalSupportRound.test.tsx` takes ENG-06 from a miss through
  visual guidance (real food board) to the simpler version (fewer words, tag changed) and on to
  withdrawal and the fresh item.
