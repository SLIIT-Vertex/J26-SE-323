# Draft app build for every mapped skill area and learning outcome

This plan allows the development app to be built before human approval. It does not approve
content, open child-facing play, collect real-child data, activate an unapproved model, or
deploy to production. Those reviews remain later work. The production loader stays fail-closed
unless an explicit development flag is set.

A game here means one draft mission loaded by a shared template. It does not mean a new codebase
for each area or outcome.

## What can be built

| Target | Count | Build rule |
| --- | ---: | --- |
| Mapped skill areas | 54 | One draft mission each, using the trace locator already on the coverage row |
| Mathematics learning outcomes | 65 | One draft item slot each. The trace confidence is medium, so the item shows that caveat |
| Sinhala high-confidence learning outcomes | 8 | One draft item slot each |
| Sinhala low-confidence learning outcomes | 76 | One held slot each. The traced string is stored, and a child question is written only after the string is readable |
| Environmental Studies learning outcomes | 117 | One held slot each. All 117 outcome rows are low-confidence OCR, so they are not turned into questions yet |
| Blocked areas | 2 | No mission. `G5-AREA-SIN-11` and `G5-AREA-SIN-12` have no Grade 5 source |

English outcomes, the 2009 mathematics guide, and the prototype rows in `games.jsonl` are not
part of this build. The existing half-set mission for `G5-MAT-C03-L01-O01` is kept and not
rebuilt.

## Templates

Reuse only these mechanics:

| Areas | Template |
| --- | --- |
| `G5-AREA-MAT-01`, `02`, `04`, `06`, `08`, `10`, `15` | Market Mission |
| `G5-AREA-MAT-05` | Existing half-set scene. Reuse it for another discrete equal-part count. Do not reuse it for a continuous whole |
| `G5-AREA-MAT-03`, `G5-AREA-MAT-14` | Pattern Temple |
| `G5-AREA-MAT-07`, `09`, `11`, `12`, `13` | Parcel Workshop for measurement. Shapes use Pattern Temple if the action is placement |
| `G5-AREA-SIN-01` through `10`, `14` through `25`, except the two blocked rows | Word Workshop. Invitations (`G5-AREA-SIN-13`) use Story Studio |
| `G5-AREA-ENV-01` through `16` | Eco Explorer, using the lesson title as the draft label |

No new template is added in this plan. A later execution may add one only when a readable
outcome cannot use any template above, and it must record that reason.

## Build order

1. Add a draft mission manifest keyed by `G5-AREA-*`. Each mission records its area id, cited
   node id, template id, development-only flag, and `publication_status=blocked`.
2. Build the 16 Mathematics area missions, then the 23 buildable Sinhala area missions, then
   the 16 Environmental Studies area missions.
3. Attach the 65 Mathematics outcome slots and the 8 high-confidence Sinhala outcome slots as
   draft items inside the matching area mission.
4. Attach the 76 low-confidence Sinhala outcomes and 117 Environmental Studies outcomes as held
   slots. Do not invent a cleaned question for an unreadable string.
5. Add a development mission picker to the existing app. The production build must omit that
   picker and must keep rejecting draft packages.
6. Leave `G5-AREA-SIN-11` and `G5-AREA-SIN-12` out of the picker.

Each execution may add one area mission, or the outcome slots for one area. It stops after that
execution and does not mark the mission reviewed.

## What stays blocked

Child-facing play, real-child testing, personal or behavioral data from real children, unapproved
adaptive-model activation, production deployment, and any claim that a draft mapping is approved
stay blocked. Curriculum, Sinhala-language, educator, rubric, accessibility, answer-leakage,
usage-rights, privacy, ethics, and release review happen after a draft app exists. Passing this
build plan does not pass those reviews.

## Completion

The draft build is complete when all 54 mapped areas have a development mission, every traced
learning outcome under those areas is either a draft item or a held slot, the two blocked areas
are absent, and the default production build still refuses the draft package.
