# Scaffolding Controller V1

## Purpose and boundary

Scaffolding Controller V1 is a pure, deterministic policy component:

```text
TutoringContext -> ScaffoldingController -> AssistanceDecision
```

It selects the lowest L0–L6 assistance level reasonably justified by the available evidence and
returns stable reason codes for auditability. It performs no I/O and does not access databases,
HTTP, Knowledge Tracing internals, Learner-State internals, the skill taxonomy file, or external
services. `skill_id` scopes the supplied mastery value but never changes a decision by identity.

## Research status

**Theoretical basis:** minimum-sufficient scaffolding, fading after progress, and escalation after
combined evidence that current support is insufficient.

**Design decisions:** the rule ordering and numeric categories below make Reference Policy V1
executable and deterministic.

**Validated findings:** none. The thresholds are not scientifically validated, scenario agreement
is not learner-outcome validation, and Controller V1 is not claimed to be pedagogically optimal.

## Contract

The input is the validated `TutoringContext`:

- `learner_id` and `skill_id`
- skill-specific `mastery`
- `support_need`
- current `attempt_count` and conditionally nullable `is_correct` and `error_severity`
- nullable `previous_assistance_level` and `previous_hint_effective`

`previous_hint_effective` may be null when there is no previous assistance or when effectiveness
is not yet known. A known effectiveness value without a previous level is invalid. When a previous
level exists but effectiveness is unknown, an incorrect response maintains that level as neutral
transition evidence.

Attempt-count semantics are:

- `0`: pre-interaction; `is_correct` and `error_severity` must both be null because no attempt has
  been completed (`PRE_INTERACTION`)
- `1`: first completed attempt (`FIRST_ATTEMPT`); correctness and error severity are required
- greater than `1`: repeated attempt history; correctness and error severity remain required

The immutable `AssistanceDecision` contains:

- `assistance_level`: one existing `AssistanceLevel` value from L0 through L6
- `reason_codes`: one or more stable `DecisionReasonCode` values

## Minimum-sufficient decision order

Rules are evaluated in this order:

1. Pre-interaction selects L0 with `PRE_INTERACTION` before any correctness or error-based rule.
2. A correct response selects L0. Correct independent work records independent success; success
   after assistance records strong fading.
3. An effective previous hint with incomplete work normally fades one level. It maintains the
   previous level when low mastery, high support need, high error severity, and sufficient repeated
   attempts jointly show substantial difficulty.
4. An ineffective previous hint may escalate one level only when the attempt requirement is met.
   High mastery plus a minor error preserves low assistance while evidence is limited, but it does
   not veto escalation once the same provisional attempt requirement is met.
5. A previous level with unknown effectiveness is neutral evidence and is maintained for an
   incorrect response.
6. Without previous assistance history, the initial evidence categories select the minimum level:

| Evidence | Initial level |
| --- | --- |
| High mastery and low-severity error | L0 |
| High mastery and high-severity error | L2 |
| Other high-mastery error | L1 |
| Low mastery, high support need, and high-severity error together | L3 |
| Any one of low mastery, high support need, or high-severity error | L2 |
| Otherwise | L1 |

The controller never selects L4–L6 without previous assistance. Escalation into those levels
requires an ineffective result and sufficient repeated attempts; unknown effectiveness may only
maintain an already selected level.

## Provisional Policy V1 thresholds

These values are executable design assumptions. They require expert review and empirical
calibration before any claim of educational validity.

| Category | Provisional boundary |
| --- | ---: |
| High mastery | `>= 0.80` |
| Low mastery | `<= 0.30` |
| High support need | `>= 0.70` |
| Low error severity | `<= 0.25` |
| High error severity | `>= 0.65` |

Escalation after an ineffective previous hint requires these attempt counts:

| Previous level | Minimum attempts for next level |
| --- | ---: |
| L0 | 2 |
| L1 | 3 |
| L2 | 3 |
| L3 | 4 |
| L4 | 5 |
| L5 | 6 |

Combined high support need and high error severity permits L1 or L2 to escalate one attempt earlier.
It does not accelerate escalation to L4–L6. L6 cannot escalate further.

The same per-level attempt boundaries determine whether substantial difficulty should prevent
fading after a known-effective hint. This introduces no additional numeric threshold. All listed
boundaries remain **Provisional Policy V1 thresholds**: design assumptions requiring later expert
review and empirical calibration, not scientifically validated findings.

## Fading and escalation

Correctness is treated as progress evidence, not proof of mastery. A correct response can fade
directly to L0 rather than moving down exactly one level. An effective hint followed by incomplete
progress normally fades one level. If low mastery, high support need, high error severity, and
sufficient attempts all remain present, the controller maintains the previous level instead. This
recognizes progress without removing support when the current difficulty is still substantial.
`FADING_JUSTIFIED` is emitted only when the selected level is lower than the previous level. When
the previous level is already L0, remaining at L0 records `SUPPORT_MAINTAINED` instead.

Incorrectness alone does not escalate assistance. Escalation requires an ineffective prior hint
and enough attempt evidence, with limited earlier escalation for combined high support need and
high error severity. The maximum change per incomplete interaction is one level.

## Reason codes

Evidence codes describe the inputs that materially characterize a decision:

- `PRE_INTERACTION`, `FIRST_ATTEMPT`, `REPEATED_DIFFICULTY`
- `HIGH_MASTERY`, `LOW_MASTERY`
- `HIGH_SUPPORT_NEED`
- `LOW_ERROR_SEVERITY`, `HIGH_ERROR_SEVERITY`
- `PREVIOUS_HINT_EFFECTIVE`, `PREVIOUS_HINT_INEFFECTIVE`
- `PREVIOUS_HINT_EFFECTIVENESS_UNKNOWN`

Outcome/transition codes describe the policy action:

- `INDEPENDENT_SUCCESS`, `SUCCESS_AFTER_ASSISTANCE`
- `ESCALATION_JUSTIFIED`, `FADING_JUSTIFIED`
- `SUPPORT_MAINTAINED`, `MINIMUM_SUFFICIENT_ASSISTANCE`

Reason codes explain policy selection only. They contain no generated tutoring response.

## Reference Policy V1 conformance

The controller regression test loads all 20 structured Reference Policy V1 scenarios and requires
the selected level to match each expected label. This verifies implementation conformance to the
current design specification. It does not measure learning effectiveness or establish scientific
accuracy.

## Limitations and future calibration

- Threshold boundaries and rule ordering are provisional.
- Inputs are currently supplied or mocked; the controller does not calculate mastery, support need,
  correctness, or error severity.
- The same policy applies to every `skill_id`; skill-specific calibration is future work.
- The controller does not generate explanations, hints, prompts, or learner-facing content.
- Expert review and empirical learner evaluation must precede claims of pedagogical effectiveness.
