> **NO LIVE DRAFT**: the first Gemini call returned HTTP 503 (temporarily unavailable); the run stopped by rule after 1 of 7 approved calls. No retry, no model switch. Recorded after the L0 fix and the consecutive-unavailability stop rule.

# PP1 multi-turn demonstration — pp1-fractions-escalation-fading-v1

- Run: 2026-10-21T16:04:03+00:00 · Provider: **google-gemini gemini-3.1-flash-lite** · Thinking: LOW · Database: sqlite (synthetic demo learner)
- Question (en): “Why is 1/2 equal to 2/4?”
- All drafts: **EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS**. No draft was verified or delivered to a learner.
- Provider calls: 1 (limit 7)
- Stopped early: first Gemini call did not generate a draft (PROVIDER_TEMPORARILY_UNAVAILABLE)

- Expected levels assume every draft is generated and shown; a failed draft is not previous assistance, so later levels legitimately differ.

| Step | Annotation | Level (plan) | Controller reasons | Draft status | Shown | Provider s |
|---|---|---|---|---|---|---|
| question | — | L0 (L0) | PRE_INTERACTION | PROVIDER_UNAVAILABLE / PROVIDER_TEMPORARILY_UNAVAILABLE | no | 1.414 |

## Drafts

### question — L0

> (no draft)

Deterministic checks (diagnostic only): None

## Invariants

- no_learner_delivery_events: **PASS**
- no_verified_response_text: **PASS**
- no_delivery_authorized: **PASS**
- presentation_only_for_generated_drafts: **PASS**
- levels_match_full_presentation_plan: **PASS**
- scenario_completed: **FAIL**

## Context provenance (last step)

- SKILL_MAPPING: REAL/MATCHED (skill-mapper:e5:d829207ab28e6a5fb3aafb5d4c44111b8146db32:canonical-taxonomy)
- LEARNER: REAL/AVAILABLE (shared-learner:learner-service)
- MASTERY: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-cold-start-mastery-default)
- SUPPORT_NEED: SYNTHETIC/AVAILABLE (adaptive-tutor:experimental-missing-support-need-default)
- ASSESSMENT: REAL/NOT_YET_OBSERVED (adaptive-tutor:assessment-ledger-empty-snapshot)
- ASSISTANCE_HISTORY: REAL/NOT_YET_OBSERVED (adaptive-tutor:interaction-history)
