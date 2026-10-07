# Reference learner scenarios

The canonical structured scenarios are stored in
`backend/app/adaptive_tutor/application/reference_scenarios.json`.

These are **Reference Policy V1 labels**: initial expert-informed, design-defined expectations for
controller development and evaluation planning. They are not experimentally validated ground
truth, learner diagnoses, or proven optimal interventions. Numeric values illustrate evidence
combinations and are not policy thresholds.

Each `skill_id` is a valid Universal Skill Node from the shared taxonomy. It scopes the mastery
estimate and supplies context only; Policy V1 does not select assistance from skill identity.

| ID | Skill | Mastery | Support need | Attempts | Correct | Error severity | Previous level | Effective | Expected | Rationale |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- |
| AT-V1-001 | MAT-FRC | 0.92 | 0.12 | 1 | No | 0.10 | — | — | L0 | First minor error with strong mastery evidence permits self-correction. |
| AT-V1-002 | MAT-OPS | 0.90 | 0.20 | 2 | No | 0.25 | L0 | No | L1 | An independent retry failed, so prompt strategy reflection. |
| AT-V1-003 | MAT-TIM | 0.86 | 0.25 | 3 | No | 0.40 | L1 | No | L2 | Repeated difficulty after reflection supports concept recall. |
| AT-V1-004 | APT-LOG | 0.58 | 0.18 | 1 | No | 0.35 | — | — | L1 | Medium mastery and low support need favor metacognitive support first. |
| AT-V1-005 | MAT-FRC | 0.60 | 0.82 | 1 | No | 0.45 | — | — | L2 | A concise concept cue may meet elevated support need without over-helping. |
| AT-V1-006 | MAT-OPS | 0.55 | 0.78 | 3 | No | 0.55 | L2 | No | L3 | An ineffective concept hint supports focused direction. |
| AT-V1-007 | MAT-TIM | 0.64 | 0.20 | 3 | Yes | 0.00 | L3 | Yes | L0 | Recovery permits a direct return to independent work. |
| AT-V1-008 | APT-LOG | 0.22 | 0.30 | 1 | No | 0.20 | — | — | L2 | Low mastery makes concept activation more useful than an unsupported retry. |
| AT-V1-009 | MAT-FRC | 0.18 | 0.88 | 1 | No | 0.86 | — | — | L3 | Strong combined evidence warrants targeting the barrier, but not solving. |
| AT-V1-010 | MAT-OPS | 0.20 | 0.90 | 4 | No | 0.80 | L3 | No | L4 | Repeated failure after a targeted hint supports guided participation. |
| AT-V1-011 | MAT-TIM | 0.15 | 0.92 | 5 | No | 0.82 | L4 | No | L5 | An analogous worked example follows ineffective guided steps. |
| AT-V1-012 | APT-LOG | 0.12 | 0.95 | 6 | No | 0.90 | L5 | No | L6 | Persistent difficulty after L5 can justify the full current explanation. |
| AT-V1-013 | MAT-FRC | 0.52 | 0.38 | 3 | No | 0.25 | L3 | Yes | L2 | Partial progress supports fading while retaining conceptual support. |
| AT-V1-014 | MAT-OPS | 0.48 | 0.70 | 2 | No | 0.68 | L2 | No | L3 | A substantial unresolved error calls for problem-specific direction. |
| AT-V1-015 | MAT-TIM | 0.84 | 0.16 | 2 | No | 0.08 | L1 | No | L1 | A likely slip does not require stronger content support yet. |
| AT-V1-016 | APT-LOG | 0.87 | 0.32 | 1 | No | 0.88 | — | — | L2 | Check the governing concept before assuming extensive need. |
| AT-V1-017 | MAT-FRC | 0.30 | 0.58 | 4 | Yes | 0.00 | L4 | Yes | L0 | Correct recovery restores an independent opportunity. |
| AT-V1-018 | MAT-OPS | 0.38 | 0.86 | 5 | No | 0.72 | L4 | No | L5 | Continued difficulty after guidance supports analogous modeling. |
| AT-V1-019 | MAT-TIM | 0.72 | 0.10 | 1 | Yes | 0.00 | — | — | L0 | Correct independent performance needs no additional scaffold. |
| AT-V1-020 | APT-LOG | 0.24 | 0.76 | 6 | No | 0.30 | L5 | Yes | L4 | Progress after an example supports fading to guided participation. |

## Coverage intent

The set intentionally covers high, medium, and low mastery; low and high support need; first and
repeated errors; low and high error severity; effective and ineffective prior hints; successful
recovery; progressive escalation; fading that skips levels; maintaining the same level; and all
seven expected assistance labels.

Future expert review may revise any label, rationale, example value, or scenario composition.
Version changes should preserve prior scenario files or record a clear mapping so evaluation
results remain reproducible.
