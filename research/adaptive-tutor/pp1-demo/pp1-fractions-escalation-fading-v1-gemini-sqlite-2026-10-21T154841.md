> **PARTIAL LIVE EVIDENCE**: 2 of 7 Gemini drafts generated; 5 provider-unavailable failures. Recorded before the L0 instruction change and the two-consecutive-503 stop rule; its deterministic checks predate the L0 structure rule.

# PP1 multi-turn demonstration — pp1-fractions-escalation-fading-v1

- Run: 2026-10-21T15:48:41+00:00 · Provider: **google-gemini gemini-3.1-flash-lite** · Thinking: LOW · Database: sqlite (synthetic demo learner)
- Question (en): “Why is 1/2 equal to 2/4?”
- All drafts: **EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS**. No draft was verified or delivered to a learner.
- Provider calls: 7 (limit 7)
- Stopped early: no

| Step | Annotation | Level (expected) | Controller reasons | Draft status | Provider s |
|---|---|---|---|---|---|
| question | — | L0 (L0) | PRE_INTERACTION | GENERATED | 3.224 |
| a1 | incorrect, severity 0.7 | L2 (L2) | FIRST_ATTEMPT, LOW_MASTERY, HIGH_ERROR_SEVERITY, MINIMUM_SUFFICIENT_ASSISTANCE | GENERATED | 4.054 |
| a2 | incorrect, severity 0.7 | L2 (L2) | REPEATED_DIFFICULTY, LOW_MASTERY, HIGH_ERROR_SEVERITY, PREVIOUS_HINT_INEFFECTIVE, SUPPORT_MAINTAINED | PROVIDER_UNAVAILABLE / PROVIDER_TEMPORARILY_UNAVAILABLE | 4.294 |
| a3 | incorrect, severity 0.7 | L3 (L3) | REPEATED_DIFFICULTY, LOW_MASTERY, HIGH_ERROR_SEVERITY, PREVIOUS_HINT_INEFFECTIVE, ESCALATION_JUSTIFIED | PROVIDER_UNAVAILABLE / PROVIDER_TEMPORARILY_UNAVAILABLE | 2.668 |
| a4 | incorrect, severity 0.7 | L3 (L4) | REPEATED_DIFFICULTY, LOW_MASTERY, HIGH_ERROR_SEVERITY, PREVIOUS_HINT_INEFFECTIVE, ESCALATION_JUSTIFIED | PROVIDER_UNAVAILABLE / PROVIDER_TEMPORARILY_UNAVAILABLE | 3.118 |
| a5 | incorrect, severity 0.3 | L1 (L3) | REPEATED_DIFFICULTY, LOW_MASTERY, PREVIOUS_HINT_EFFECTIVE, FADING_JUSTIFIED | PROVIDER_UNAVAILABLE / PROVIDER_TEMPORARILY_UNAVAILABLE | 1.717 |
| a6 | correct | L0 (L0) | LOW_MASTERY, LOW_ERROR_SEVERITY, PREVIOUS_HINT_EFFECTIVE, SUCCESS_AFTER_ASSISTANCE, FADING_JUSTIFIED | PROVIDER_UNAVAILABLE / PROVIDER_TEMPORARILY_UNAVAILABLE | 2.965 |

## Drafts

### question — L0

> Think about what happens to a single whole object if you cut it into two equal pieces versus cutting it into four equal pieces. If you have one of the two pieces, how could you cut that same piece again to make it look like two of the four pieces? Try to draw a picture or use objects to show how the amount of the whole remains the same in both cases.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a1 — L2

> Think about how the total number of pieces in a whole changes when you slice each existing piece into smaller, equal sections.

Deterministic checks (diagnostic only): {'RESPONSE_STRUCTURE': 'PASS (RESPONSE_WELL_FORMED)', 'LEVEL_STRUCTURE': 'PASS (LEVEL_STRUCTURE_COMPATIBLE)', 'ANSWER_LEAKAGE': 'INDETERMINATE (TRUSTED_ANSWER_NOT_AVAILABLE)', 'LANGUAGE_SCRIPT': 'PASS (LANGUAGE_SIGNAL_COMPATIBLE)', 'CHILD_SAFETY': 'PASS (NO_OBVIOUS_UNSAFE_CONTENT)'}

### a2 — L2

> (no draft)

Deterministic checks (diagnostic only): None

### a3 — L3

> (no draft)

Deterministic checks (diagnostic only): None

### a4 — L3

> (no draft)

Deterministic checks (diagnostic only): None

### a5 — L1

> (no draft)

Deterministic checks (diagnostic only): None

### a6 — L0

> (no draft)

Deterministic checks (diagnostic only): None

## Invariants

- no_learner_delivery_events: **PASS**
- no_verified_response_text: **PASS**
- no_delivery_authorized: **PASS**
- presentations_match_generated_drafts: **PASS**
- levels_match_expected: **FAIL**
- scenario_completed: **PASS**

## Context provenance (last step)

- SKILL_MAPPING: REAL/MATCHED (skill-mapper:e5:d829207ab28e6a5fb3aafb5d4c44111b8146db32:canonical-taxonomy)
- LEARNER: REAL/AVAILABLE (shared-learner:learner-service)
- MASTERY: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-cold-start-mastery-default)
- SUPPORT_NEED: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-missing-support-need-default)
- ASSESSMENT: SYNTHETIC/AVAILABLE (adaptive-tutor:assessment-ledger-controlled)
- ASSISTANCE_HISTORY: SYNTHETIC/AVAILABLE (adaptive-tutor:interaction-history-research-presentation)
