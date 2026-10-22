# Research Interaction Lifecycle and Transition Evidence

Status: research-only (`TUTOR_API_MODE=research-local`, adult researcher, loopback). Implements
audit task T1 (`component-progress-audit.md`). Controller V1 policy is unchanged.

## Why this exists

Controller V1 escalates, maintains and fades using two history inputs:
`previous_assistance_level` and `previous_hint_effective`. Before T1, research sessions:

- recorded only the question-time decision,
- read history only from *earlier* interactions,
- counted assistance only after verified `RESPONSE_DELIVERED`, which nothing produces, and
- never derived hint effectiveness.

So every live decision was an initial selection (max L3) or a reset to L0. T1 records what the
researcher was actually shown and what the next reviewed attempt showed, without implying learner
delivery.

## Learning sequence

One **interaction** is one question. Assessment evidence (`attempt_count`, `is_correct`,
`error_severity`) is already scoped to it, so assistance history is scoped to it too. A new
question starts a new sequence at `PRE_INTERACTION` (L0).

## Events (`tutor_interaction_events`, no migration)

| Event type | Status | Recorded when | Provenance |
|---|---|---|---|
| `ASSISTANCE_SELECTED` | — | Every Controller decision: at the question and after **each** reviewed attempt. Idempotency key `research-selection:{interaction}:{attempts so far}` | `RESEARCH_LOCAL` |
| `RESEARCH_PRESENTATION` | `PRESENTED_TO_RESEARCHER` | Only when an experimental draft was **generated** and returned to the researcher | `EXPERIMENTAL_UNVERIFIED_RESEARCH_ONLY` (reserved; enforced both ways) |
| `OUTCOME_OBSERVED` | `OBSERVED` | Each accepted researcher-reviewed attempt, linked to the latest decision | `CONTROLLED_RESEARCH_ANNOTATION` |
| `EFFECTIVENESS_STATUS_RECORDED` | `EFFECTIVE` / `INEFFECTIVE` / `INSUFFICIENT_EVIDENCE` | After an attempt that follows a presented, non-baseline decision; linked to that decision and the attempt's assessment reference | `RESEARCH_DERIVED:research-hint-effectiveness-v1` |

Event sequences are allocated from the table per interaction, so repeated attempts no longer
collide on `(session_id, interaction_sequence, event_sequence)`.

`RESEARCH_PRESENTATION` is a separate event type from `RESPONSE_DELIVERED`. It cannot carry
`DELIVERED`, and the reserved provenance cannot be used on any other event type.

## Lifecycle

```text
ask(question)
  ├─ map skill · create assessment interaction
  ├─ Controller (attempt_count=0) ─► L0 PRE_INTERACTION ─► ASSISTANCE_SELECTED
  └─ experimental draft generated? ─► RESEARCH_PRESENTATION   (baseline; not "assistance")

submit_attempt(reviewed annotation)          (repeat per attempt)
  ├─ accept attempt in assessment ledger ─► OUTCOME_OBSERVED
  ├─ latest presented decision exists and is not PRE_INTERACTION?
  │     └─ assess_hint_effectiveness(before_hint, after_hint) ─► EFFECTIVENESS_STATUS_RECORDED
  ├─ history provider (current interaction):
  │     most recent ASSISTANCE_SELECTED that has a RESEARCH_PRESENTATION and is not PRE_INTERACTION
  │       → previous_assistance_level = its level
  │       → previous_hint_effective  = EFFECTIVE→true · INEFFECTIVE→false · otherwise null
  ├─ Controller V1 (unchanged) ─► ASSISTANCE_SELECTED
  └─ experimental draft generated? ─► RESEARCH_PRESENTATION
```

If no presented, non-baseline decision exists in the interaction, the provider falls back to the
original cross-interaction logic, which still requires a verified `RESPONSE_DELIVERED`.

## Hint-effectiveness rule `research-hint-effectiveness-v1`

Source: `backend/app/adaptive_tutor/application/hint_effectiveness.py`.

- `before_hint`: the reviewed attempt that immediately preceded the presented decision.
- `after_hint`: the new reviewed attempt.

| Evidence | Result | Controller input |
|---|---|---|
| `after_hint` correct | `EFFECTIVE` | `true` |
| Same severity policy, lower severity | `EFFECTIVE` | `true` |
| Same severity policy, equal or higher severity | `INEFFECTIVE` | `false` |
| No `before_hint`, or different severity policies | `INSUFFICIENT_EVIDENCE` | `null` (unknown) |
| Nothing presented / generation failed | no event | history has no prior assistance |

Unknown is never converted to `false`. Per the transition policy, a known level with unknown
effectiveness is **maintained** on an incorrect attempt. The rule is a design assumption:
"observable progress" is operationalized as lower reviewed severity. It requires pedagogical review
before research claims.

## Exact evidence for every transition

Each Controller decision receives one immutable `TutoringContext`:

| Input | Source | Origin label |
|---|---|---|
| `mastery` | KT estimate, or the PP1 cold-start default when KT has none | Per value: REAL (`knowledge-tracing:mastery-service`) or SYNTHETIC (`…cold-start-mastery-default`) |
| `support_need` | Stored Learner State, or the PP1 default when none exists | Per value: REAL (`learner-state:stored-support-need`) or SYNTHETIC (`…missing-support-need-default`) |
| `attempt_count`, `is_correct`, `error_severity` | Assessment ledger, latest accepted attempt of this interaction. Entered in the researcher panel (`researcher-review-v1`) or by the scripted runner (`scripted-scenario-v1`); never observed student work | SYNTHETIC (controlled annotation) |
| `previous_assistance_level` | Latest presented, non-baseline `ASSISTANCE_SELECTED` of this interaction | SYNTHETIC (`adaptive-tutor:interaction-history-research-presentation`) |
| `previous_hint_effective` | Latest `EFFECTIVENESS_STATUS_RECORDED` for that decision | same as above |

Every input, its source ID, origin and status appear in `context_provenance` on the API response
and in the researcher diagnostics panel. The Controller's reason codes (`PREVIOUS_HINT_EFFECTIVE`,
`PREVIOUS_HINT_INEFFECTIVE`, `PREVIOUS_HINT_EFFECTIVENESS_UNKNOWN`, `ESCALATION_JUSTIFIED`,
`SUPPORT_MAINTAINED`, `FADING_JUSTIFIED`, …) state why each level was chosen.

### Worked example (integration test)

Settings: mastery 0.5, support need 0.5. Fake Gemini (no network); real Controller and SQLite
persistence.

| Step | Reviewed attempt | Effectiveness recorded | Level | Key reason codes |
|---|---|---|---|---|
| Question | — | — | L0 | `PRE_INTERACTION` |
| a1 | incorrect, severity 0.7 | none (baseline) | L2 | `MINIMUM_SUFFICIENT_ASSISTANCE` |
| a2 | incorrect, 0.7 | INEFFECTIVE (0.7 → 0.7) | L2 | `PREVIOUS_HINT_INEFFECTIVE`, `SUPPORT_MAINTAINED` (2 < 3 attempts) |
| a3 | incorrect, 0.7 | INEFFECTIVE | L3 | `ESCALATION_JUSTIFIED` (3 ≥ 3 attempts) |
| a4 | incorrect, 0.3 | EFFECTIVE (0.7 → 0.3) | L2 | `PREVIOUS_HINT_EFFECTIVE`, `FADING_JUSTIFIED` |
| a5 | correct | EFFECTIVE | L0 | `SUCCESS_AFTER_ASSISTANCE`, `FADING_JUSTIFIED` |

## L0 (independent retry) alignment

The first live PP1 run produced an L0 draft that gave a conceptual hint and a strategy. Changes:

- **Prompt:** the L0 instruction now allows only at most two sentences of neutral encouragement and
  lists forbidden content: concepts, comparisons, objects or drawings, strategies, method-pointing
  questions, steps, formulas, numbers, intermediate results, examples and answers. L1–L6 text is
  unchanged.
- **Experimental context:** at L0 the unreviewed curriculum is withheld (`experimental_curriculum:
  null`), so there is no teaching content to draw hints from.
- **Deterministic check** (`_check_independent_retry`, language-agnostic):
  - numbers or mathematical notation → **FAIL**
  - more than 35 words or 2 sentences → **INDETERMINATE**, which blocks approval and requires
    semantic review
- **Semantic verifier:** the payload now includes `assistance_level_definition`, so an independent
  judge rates compliance against the level's meaning rather than the bare code `L0`.

A short conceptual hint written in words (for example "Think about cutting each half again.")
still passes the deterministic check. Only semantic judgement can catch it. The semantic verifier is
not configured, and the experimental path is unverified by design.

## Safety guarantees

- No `RESPONSE_DELIVERED` or `DELIVERY_AUTHORIZED` event is written by this path.
- History built from presentations is reported with **SYNTHETIC** origin, so `execution_origin` can
  never be `REAL`. The orchestrator's verified-approval branch requires REAL evidence, a
  non-simulated verifier and an authorized provider, so presentation history cannot yield an
  `APPROVED_RESPONSE`.
- Experimental text stays in `experimental_response_text`. `response_text` and
  `delivery_authorized` are unchanged.
- Replayed attempts (same idempotency key) return the stored turn and write no events. Sessions are
  isolated by `session_id`.

## Tests

- `tests/adaptive_tutor/test_hint_effectiveness.py`: the rule, and unknown ≠ false.
- `tests/adaptive_tutor/test_tutor_history.py`: presentation is not delivery, reserved provenance,
  baseline skipped, effectiveness pass-through, SYNTHETIC source.
- `tests/adaptive_tutor/test_research_multiturn.py`:
  - escalation, maintenance and fading across five attempts
  - SYNTHETIC history and no learner delivery
  - failed generation leaves no presentation (initial selection each time)
  - cross-policy feedback recorded as insufficient evidence (level maintained)
  - duplicate attempts write nothing
  - session isolation

## Limitations

- The effectiveness rule is provisional, uses severity only (not partial credit) and is unreviewed.
- Effectiveness depends on researcher annotations. PP1 mastery and support defaults stay SYNTHETIC.
- History does not cross interactions for research presentations, by design: a new question is a
  new sequence.
- Research sessions remain in memory; events persist but a restarted server cannot resume a session.
- The verified learner path still has no `RESPONSE_DELIVERED` producer, because no verified
  delivery exists yet.
