# Review — PP1 live run `2026-10-21T154841` (gemini-3.1-flash-lite, thinking LOW)

Companion to `pp1-fractions-escalation-fading-v1-gemini-sqlite-2026-10-21T154841.{json,md}`.

**Reviewer:** AI coding assistant (Claude). This is an informal adherence reading against the
generation rubric in `backend/app/adaptive_tutor/application/generation.py`. It is not a qualified
pedagogical review and is not research evidence.

All drafts are **EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS**. Nothing was verified,
authorized or delivered to a learner.

## Run facts

| Item | Value |
|---|---|
| Real Gemini generation requests | 7 of 7 approved (cap enforced in code) |
| Drafts generated | 2: question (L0), a1 (L2) |
| Provider failures | 5: a2–a6, `ServerError` → `PROVIDER_TEMPORARILY_UNAVAILABLE` (Google HTTP 502/503 class), 1.7–4.3 s each |
| Successful provider latency | 3.22 s (L0), 4.05 s (L2) |
| End-to-end HTTP latency | 7.69 s first request (includes model loading), 4.07 s for a1 |
| Safety invariants | No delivery events, no verified text, `delivery_authorized=false` throughout |
| Earlier aborted attempt | `…HARNESS-FAILURE-no-request-sent…`: a runner bug (closed HTTP client) failed locally. Offline reproduction showed no request was sent. Not counted. |

## Controller transitions (deterministic, from recorded evidence)

| Step | Annotation | Level | Shown to researcher? | Why |
|---|---|---|---|---|
| question | — | L0 | yes | `PRE_INTERACTION` baseline |
| a1 | incorrect 0.7 | L2 | yes | Initial selection: low mastery (SYNTHETIC 0.0), high error severity |
| a2 | incorrect 0.7 | L2 | **no** (503) | Shown L2 ineffective (0.7 → 0.7); 2 < 3 attempts, so maintained |
| a3 | incorrect 0.7 | L3 | **no** | Last *shown* hint still L2; ineffective; 3 ≥ 3 attempts, so escalated |
| a4 | incorrect 0.7 | L3 (planned L4) | **no** | Last shown hint is still L2, so escalation is again L2 → L3 |
| a5 | incorrect 0.3 | L1 (planned L3) | **no** | Improvement vs. the shown L2 hint (0.7 → 0.3) is effective, so fade L2 → L1 |
| a6 | correct | L0 | **no** | Success after assistance → L0 |

The departures from the planned sequence are **correct policy behaviour**. Assistance that was never
shown does not count as previous assistance (T1 design). The run still demonstrates
maintenance, escalation (L2 → L3) and fading (L2 → L1 → L0) live. It does **not** demonstrate L4,
because the L3 drafts were never generated.

## Level adherence of the two real drafts

### Question — L0 *Independent retry*

Rubric: "Encourage one independent attempt. Do not give a hint, steps, worked example, solution, or
final answer."

> Think about what happens to a single whole object if you cut it into two equal pieces versus
> cutting it into four equal pieces. If you have one of the two pieces, how could you cut that same
> piece again to make it look like two of the four pieces? Try to draw a picture or use objects to
> show how the amount of the whole remains the same in both cases.

**Assessment: exceeds L0 (over-assistance).**
- It gives a conceptual hint (compare halves with quarters of the same whole).
- It gives a near-procedural strategy (cut the half again) and a representation suggestion
  (draw it).
- It points strongly at the key insight but does not state the final answer or the rule (multiply
  numerator and denominator by 2).
- This sits closer to L2–L3 than L0.

The deterministic structural check reported PASS because it only detects explicit answers and
numbered steps. That shows its limits for semantic over-assistance.

### a1 — L2 *Conceptual hint*

Rubric: "Give one concise conceptual hint. Do not provide procedural steps, solve the current
problem, or reveal its final answer."

> Think about how the total number of pieces in a whole changes when you slice each existing piece
> into smaller, equal sections.

**Assessment: compliant.** One concise conceptual hint, with no steps and no answer.

### Answer leakage

Neither draft states the final answer or the equivalence rule explicitly. No trusted answer was
configured, so the deterministic leakage check was `INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)`.

## Limitations

- Only 2 drafts: no adherence evidence for L1, L3, L4 or the faded levels.
- 5 of 7 calls failed with provider unavailability. Gemini reliability on this model is the main
  demonstration risk.
- The guard stopped only on authentication, missing-model or configuration errors and on repeated
  *timeouts*. It continued through repeated 502/503 responses, which used the remaining budget.
- Mastery and support need are SYNTHETIC cold-start defaults (0.0). Attempts are researcher
  annotations on a synthetic learner in SQLite.
- The adherence reading above is informal, single-rater and AI-authored. Level-adherence claims
  need blinded, qualified review (RQ3 protocol).
