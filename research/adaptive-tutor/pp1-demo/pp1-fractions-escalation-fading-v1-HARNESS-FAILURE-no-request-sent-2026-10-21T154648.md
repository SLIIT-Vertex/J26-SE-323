# PP1 multi-turn demonstration — pp1-fractions-escalation-fading-v1

- Run: 2026-10-21T15:46:48+00:00 · Provider: **google-gemini gemini-3.1-flash-lite** · Thinking: LOW · Database: sqlite (synthetic demo learner)
- Question (en): “Why is 1/2 equal to 2/4?”
- All drafts: **EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS**. No draft was verified or delivered to a learner.
- Provider calls: 1 (limit 7)
- Stopped early: first Gemini call did not generate a draft (UNEXPECTED_PROVIDER_FAILURE)

| Step | Annotation | Level (expected) | Controller reasons | Draft status | Provider s |
|---|---|---|---|---|---|
| question | — | L0 (L0) | PRE_INTERACTION | PROVIDER_ERROR / UNEXPECTED_PROVIDER_FAILURE | 0.012 |

## Drafts

### question — L0

> (no draft)

Deterministic checks (diagnostic only): None

## Invariants

- no_learner_delivery_events: **PASS**
- no_verified_response_text: **PASS**
- no_delivery_authorized: **PASS**
- presentations_match_generated_drafts: **PASS**
- levels_match_expected: **PASS**
- scenario_completed: **FAIL**

## Context provenance (last step)

- SKILL_MAPPING: REAL/MATCHED (skill-mapper:e5:d829207ab28e6a5fb3aafb5d4c44111b8146db32:canonical-taxonomy)
- LEARNER: REAL/AVAILABLE (shared-learner:learner-service)
- MASTERY: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-cold-start-mastery-default)
- SUPPORT_NEED: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-missing-support-need-default)
- ASSESSMENT: REAL/NOT_YET_OBSERVED (adaptive-tutor:assessment-ledger-empty-snapshot)
- ASSISTANCE_HISTORY: REAL/NOT_YET_OBSERVED (adaptive-tutor:interaction-history)
