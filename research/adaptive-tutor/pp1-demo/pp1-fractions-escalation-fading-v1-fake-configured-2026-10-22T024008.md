# PP1 multi-turn demonstration — pp1-fractions-escalation-fading-v1

- Run: 2026-10-22T02:40:08+00:00 · Provider: **FAKE PROVIDER REHEARSAL — not Gemini output** · Thinking: (provider default) · Database: configured (configured learner (id withheld))
- Question (en): “Why is 1/2 equal to 2/4?”
- All drafts: **EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS**. No draft was verified or delivered to a learner.
- Provider calls: 7 (limit n/a)
- Stopped early: no

- Expected levels assume every draft is generated and shown; a failed draft is not previous assistance, so later levels legitimately differ.

| Step | Annotation | Level (plan) | Controller reasons | Draft status | Shown | Provider s |
|---|---|---|---|---|---|---|
| question | — | L0 (L0) | PRE_INTERACTION | GENERATED | yes | 0.0 |
| a1 | incorrect, severity 0.7 | L2 (L2) | FIRST_ATTEMPT, LOW_MASTERY, HIGH_ERROR_SEVERITY, MINIMUM_SUFFICIENT_ASSISTANCE | GENERATED | yes | 0.0 |
| a2 | incorrect, severity 0.7 | L2 (L2) | REPEATED_DIFFICULTY, LOW_MASTERY, HIGH_ERROR_SEVERITY, PREVIOUS_HINT_INEFFECTIVE, SUPPORT_MAINTAINED | GENERATED | yes | 0.0 |
| a3 | incorrect, severity 0.7 | L3 (L3) | REPEATED_DIFFICULTY, LOW_MASTERY, HIGH_ERROR_SEVERITY, PREVIOUS_HINT_INEFFECTIVE, ESCALATION_JUSTIFIED | GENERATED | yes | 0.0 |
| a4 | incorrect, severity 0.7 | L4 (L4) | REPEATED_DIFFICULTY, LOW_MASTERY, HIGH_ERROR_SEVERITY, PREVIOUS_HINT_INEFFECTIVE, ESCALATION_JUSTIFIED | GENERATED | yes | 0.0 |
| a5 | incorrect, severity 0.3 | L3 (L3) | REPEATED_DIFFICULTY, LOW_MASTERY, PREVIOUS_HINT_EFFECTIVE, FADING_JUSTIFIED | GENERATED | yes | 0.0 |
| a6 | correct | L0 (L0) | LOW_MASTERY, LOW_ERROR_SEVERITY, PREVIOUS_HINT_EFFECTIVE, SUCCESS_AFTER_ASSISTANCE, FADING_JUSTIFIED | GENERATED | yes | 0.0 |

## Drafts

### question — L0

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L0.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'FAIL (LEVEL_STRUCTURE_VIOLATION)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a1 — L2

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L2.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a2 — L2

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L2.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a3 — L3

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L3.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a4 — L4

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L4.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a5 — L3

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L3.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a6 — L0

> [FAKE PROVIDER — NOT GEMINI] Rehearsal draft for L0.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'FAIL (LEVEL_STRUCTURE_VIOLATION)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

## Invariants

- no_learner_delivery_events: **PASS**
- no_verified_response_text: **PASS**
- no_delivery_authorized: **PASS**
- presentation_only_for_generated_drafts: **PASS**
- levels_match_full_presentation_plan: **PASS**
- scenario_completed: **PASS**

## Context provenance (last step)

- SKILL_MAPPING: REAL/MATCHED (skill-mapper:e5:d829207ab28e6a5fb3aafb5d4c44111b8146db32:canonical-taxonomy)
- LEARNER: REAL/AVAILABLE (shared-learner:learner-service)
- MASTERY: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-cold-start-mastery-default)
- SUPPORT_NEED: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-missing-support-need-default)
- ASSESSMENT: SYNTHETIC/AVAILABLE (adaptive-tutor:assessment-ledger-controlled)
- ASSISTANCE_HISTORY: SYNTHETIC/AVAILABLE (adaptive-tutor:interaction-history-research-presentation)
