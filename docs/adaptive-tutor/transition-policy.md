# Scaffolding Controller input and transition policy

## Research status

This conceptual specification governs Scaffolding Controller V1. It defines the evidence the
controller may consume and the constraints that guide fading or escalation. It is not a
scoring algorithm, trained model, causal theory, or experimentally validated decision rule.

## Controller input contract

The executable contract is `TutoringContext` in
`backend/app/adaptive_tutor/application/contracts.py`.

| Field | Type | Constraint | Meaning and source |
| --- | --- | --- | --- |
| `learner_id` | UUID | Required | Shared learner identifier; it links evidence without duplicating the learner profile. |
| `skill_id` | string | Non-empty | Relevant Universal Skill Node identifier from the shared taxonomy; supplied or mocked rather than inferred by Adaptive Tutor. |
| `mastery` | float | Inclusive `0.0–1.0` | Knowledge Tracing output for this learner and `skill_id`. Mocked during independent Adaptive Tutor development. |
| `support_need` | float | Inclusive `0.0–1.0` | Learner-State output representing its current support-need estimate. Mocked during independent Adaptive Tutor development. |
| `attempt_count` | integer | `>= 0` | Number of attempts recorded for the current item. Zero means pre-interaction with no completed attempt; one means the first completed attempt. |
| `is_correct` | boolean or null | Null only at zero attempts; otherwise required | Whether the most recently evaluated response is correct. |
| `error_severity` | float or null | Null only at zero attempts; otherwise inclusive `0.0–1.0` | Normalized evidence about the educational significance of the current error. Its future derivation and calibration remain undefined. |
| `previous_assistance_level` | `L0–L6` or null | Valid enum value | Most recent assistance level for this learning sequence; null when no assistance has been delivered. |
| `previous_hint_effective` | boolean or null | Required but nullable | Whether the previous assistance produced observable progress; null when there was no previous assistance or effectiveness has not been assessed. |

Unknown fields are rejected. The contract is immutable after validation so that one controller
decision refers to one evidence snapshot.

At `attempt_count = 0`, no attempt has been completed, so both `is_correct` and `error_severity`
must be null. At one or more attempts, both outcome fields are required.

The contract deliberately does not define numeric selection thresholds. Values in the reference
scenarios are examples of evidence combinations, not cutoff points.

## Component boundary

```text
Learner message -> [Future Skill Mapper - not implemented] -> skill_id
learner_id + skill_id -> Knowledge Tracing -> mastery
Learner State -> support_need
Current interaction -> attempts, correctness, error evidence

learner_id + skill_id + mastery + support_need + interaction evidence
                              |
                              v
                       TutoringContext
                              |
                              v
                   Scaffolding Controller
                              |
                              v
                    AssistanceLevel (L0–L6)
```

Adaptive Tutor consumes values through this contract. It does not import Knowledge Tracing or
Learner-State implementations and does not store their outputs in the shared learner profile.
It neither owns the Universal Skill Node taxonomy nor loads the spreadsheet at runtime. Automatic
skill identification remains future work outside this phase.

## Decision principles

Controller V1 evaluates the evidence as a whole rather than mapping one field to one level.

1. **Start from independence.** Consider L0 first, then add only the information needed to make
   progress plausible.
2. **Treat correctness as progress evidence, not proof of mastery.** A correct response commonly
   supports returning to L0, but should not overwrite longer-term mastery evidence.
3. **Distinguish slips from conceptual difficulty.** Low-severity errors can justify repeating or
   maintaining light support even after an ineffective prompt.
4. **Use mastery as context.** Lower mastery can justify earlier conceptual support, but must not
   automatically trigger guided solutions or answer revelation.
5. **Use support need as context, not ability.** Higher support need may justify clearer structure
   or reassurance, but is not evidence that the learner cannot reason independently.
6. **Use history to evaluate assistance.** The effect of the previous hint is stronger transition
   evidence than its level alone.
7. **Protect the answer boundary.** L0–L5 must not reveal the current answer. L6 requires explicit
   accumulated justification.

## Fading policy

Fading means selecting less assistance after evidence of progress.

- A correct response after assistance should usually reopen an independent opportunity. The next
  level may fall directly to L0 rather than decreasing exactly one level.
- An effective hint followed by partial but incomplete progress can justify a smaller fade, such as
  moving from targeted help to a conceptual reminder.
- `FADING_JUSTIFIED` is recorded only when the selected level is lower than the previous level. L0
  cannot fade further, so remaining at L0 records maintained support instead.
- An effective hint does not force fading. When the learner remains incorrect and low mastery,
  high support need, severe error, and sufficient repeated attempts jointly indicate substantial
  difficulty, the controller maintains the previous level.
- Assistance may remain at the same level when progress is real but fragile and removing support
  would likely interrupt the learner's next meaningful action.
- The controller should not repeat worked examples or full explanations merely because they were
  previously used.
- Fading does not change the stored mastery or support-need estimates; their owning components
  remain responsible for those values.

## Escalation policy

Escalation means increasing assistance after evidence that the current support is insufficient.

- A wrong response does not automatically increase assistance by one level.
- A first, low-severity error can remain at L0 or L1 when self-correction is plausible.
- An ineffective previous hint, repeated attempts, and a persistent or severe error jointly provide
  stronger evidence for escalation than any one factor alone.
- High mastery and a minor error protect independence only while attempt evidence remains limited;
  they do not permanently veto escalation after repeated ineffective assistance.
- Escalation should target the identified barrier: reflection, concept recall, a specific next step,
  guided organization, or transfer from an analogous example.
- The controller may skip a level when the intervening level cannot reasonably address the observed
  barrier, but the justification should be inspectable.
- A jump to L4 or higher requires stronger evidence than a single incorrect response.
- L5 should model a different but analogous item only after lower support appears insufficient.
- L6 should be reserved for persistent difficulty after appropriate lower assistance, including L5
  when a similar worked example is suitable.

## Interpreting previous-hint effectiveness

`previous_hint_effective = true` means that observable behavior indicated progress after the prior
assistance. It does not require a fully correct answer and does not prove causation. It normally
supports maintaining or fading assistance.

`previous_hint_effective = false` means that the expected progress was not observed. Before
escalating, the controller should consider whether the hint was relevant, understandable, and
policy-conformant. An ineffective hint is evidence about the interaction, not simply a deficit in
the learner.

The nullable fields have these Controller V1 semantics:

- Both fields null means there is no relevant previous assistance history.
- A previous level with effectiveness true or false means its result is known.
- A previous level with null effectiveness means its result is unknown. This is neutral evidence,
  so an incorrect response maintains the known previous level rather than resetting to initial
  selection.
- Non-null effectiveness without a previous level is invalid and rejected by `TutoringContext`.

An unknown value is not silently treated as false and does not erase known assistance history.

## Provisional transition examples

| Evidence pattern | Permitted policy direction | Not justified by this evidence alone |
| --- | --- | --- |
| Correct after effective L3 or L4 support | Fade, potentially directly to L0 | Assuming mastery is now complete |
| Partial progress after effective L3 | Maintain L3 or fade to L2 | Automatic escalation because the answer remains incorrect |
| First minor error with strong mastery evidence | L0 or L1 | Immediate targeted steps or a solution |
| Conceptual hint ineffective across repeated attempts | Consider L3 | Mechanical escalation regardless of the diagnosed barrier |
| Guided steps ineffective and transfer seems useful | Consider L5 | Revealing the current answer |
| Similar example ineffective after persistent difficulty | Consider L6 with documented justification | Keeping all future items at L6 |

These examples constrain later controller design but do not determine an algorithm. Reference
Policy V1 labels must be reviewed by education/domain experts and calibrated with empirical data
before being treated as validated targets.
