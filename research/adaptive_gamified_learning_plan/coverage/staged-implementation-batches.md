# Staged batches for the 57 supplied areas

The matrix is `grade5-supplied-area-coverage-v1.jsonl`. Each batch below is finite. An execution
inside a content batch implements one atomic skill package and then stops. Category names are not
turned into game packages.

No new template is proposed. The existing templates are the half-set scene already used for
`G5-MAT-C03-L01-O01`, plus the canonical templates: Pattern Temple / Bridge Builder, Market
Mission, Parcel Workshop, Word Workshop, Story Detective, Eco Explorer, and Story Studio. A later
execution may add one template only when a verified observable action cannot use any of these,
and it must record that reason.

## Draft build and publication stop

Development missions may be built before human approval by following
[`draft-app-build-plan.md`](draft-app-build-plan.md). That build does not approve content and
does not open child-facing play.

Publication, real-child use, and release claims stay stopped. Both of these are unmet:

1. `reports/phase-07-completion.md` is **Partially completed** and **Ready for next phase? No.**
   Android and iOS installed-app evidence is still missing.
2. `reports/phase-08-completion.md` does not exist. Phase 8 requires a passing Phase 7 report
   before it can start, so there is no passing pilot-readiness report.

Until both are passing, no batch below may be described as release-ready. Draft missions from
the draft-app plan may still be added behind the development flag.
Child publication, real-child data, unapproved model activation, production deployment, and
approval claims stay blocked. The human-review gate on every batch is `HR-CUR-01`, `HR-RGT-01`,
`HR-SIN-01`, `HR-EDU-01`, `HR-ACC-01`, `HR-LEAK-01`, and `HR-REL-01`, followed by the security,
privacy, ethics, consent, protocol, model-safety, and release gates. None of those decisions
exists.

## B-ENV-VERIFY

- Categories: `G5-AREA-ENV-01` through `G5-AREA-ENV-16`.
- Atomic skills: none. Do not derive any until a named reviewer visually confirms the printed
  competency text.
- Evidence: `SRC-G5-ENV-TG-01`, printed page ranges on each matrix row. Supplementary activity
  books are not official outcome evidence. Low-confidence OCR is not an outcome.
- Prerequisite: the matrix row exists. Content work also needs the unmet gate above.
- Mechanic: Eco Explorer only after an outcome has an observable classify-or-connect action.
  Performance, drama, and movement competencies are not forced into a quiz.
- Deliverables: corrected outcome text and atomic-skill records, or a continued `NEEDS_REVIEW`
  note. No game in this batch.
- Validation: trace confidence, page locators, Sinhala exactness, and rejection of missing-page
  rows.
- Completion: every ENV row either cites a visually confirmed outcome or keeps an explicit
  `NEEDS_REVIEW` reason. Zero games.

## B-SIN-BLOCKED

- Categories: `G5-AREA-SIN-11`, `G5-AREA-SIN-12`.
- Atomic skills: none.
- Evidence checked: no `පොදුලිංග` or `ආඛ්‍යාත` node or term in the Grade 5 trace.
- Prerequisite: a Grade 5 Sinhala-medium source with a page and outcome. None is known.
- Mechanic: none.
- Deliverables: none until that source exists.
- Validation: the two rows remain present and `BLOCKED`.
- Completion: either a sourced outcome is recorded, or the rows stay `BLOCKED` without scope
  change. Zero games.

## B-SIN-ORTHOGRAPHY-REVIEW

- Categories: `G5-AREA-SIN-01`, `G5-AREA-SIN-02`, `G5-AREA-SIN-17`, `G5-AREA-SIN-18`,
  `G5-AREA-SIN-19`, `G5-AREA-SIN-20`, `G5-AREA-SIN-25`.
- Atomic skills: none until the wording conflicts in the matrix are resolved by a reviewer.
- Evidence: `SRC-G5-SIN-TG-01` content points on printed pages 6, 10, and 11, and the activities
  cited on each row. Combined `න,ණ,ල,ළ` and `ද/ත්/යි/හා/සහ` strings must not be split or rewritten
  to match the supplied names.
- Prerequisite: visual confirmation of those printed lines.
- Mechanic: Word Workshop is the candidate after an outcome exists. No new template.
- Deliverables: a confirmed outcome or a continued `NEEDS_REVIEW` / `BLOCKED` reason.
- Validation: supplied names remain exact; no invented particle list.
- Completion: each row has an adopted outcome or an updated blocker. Zero games before that.

## B-SIN-GRAMMAR-REVIEW

- Categories: `G5-AREA-SIN-14`, `G5-AREA-SIN-15`, `G5-AREA-SIN-21`, `G5-AREA-SIN-22`.
- Atomic skills: none.
- Evidence: `SRC-G5-SIN-TG-01` content points and learning outcomes on printed pages 10, 11, 129,
  and 264, as cited on each row.
- Prerequisite: a reviewer selects which outcome sentence, if any, belongs to the supplied name.
- Mechanic: Word Workshop after that selection.
- Deliverables: one adopted outcome per area, or a continued review note.
- Validation: no category-wide outcome is inferred from a narrower agreement outcome.
- Completion: same as B-SIN-ORTHOGRAPHY-REVIEW. Zero games before adoption.

## B-MAT-SHAPES-REVIEW

- Category: `G5-AREA-MAT-13`.
- Atomic skills: none.
- Evidence: `SRC-G5-MAT-TG-01` lesson `G5-MAT-U016` printed pages 84–91 and competency
  `G5-MAT-C16`. `G5-MAT-C17` stays outside this area.
- Prerequisite: a reviewer accepts or rejects the title mismatch recorded on the row.
- Mechanic: Pattern Temple only if the confirmed action is spatial placement. Otherwise stop
  before adding a template.
- Deliverables: an adopted competency/outcome or a continued `NEEDS_REVIEW` note.
- Validation: the adjacent angle competency is not silently included.
- Completion: the row is either `MAPPED_DRAFT` from confirmed text or still `NEEDS_REVIEW`.
  Zero games.

## B-SIN-VOCABULARY

- Categories: `G5-AREA-SIN-03` through `G5-AREA-SIN-10`.
- Atomic skills: none yet. Candidate content-point IDs are on the matrix rows and are not skills.
- Evidence: `SRC-G5-SIN-TG-01` printed pages 8 and 64–81. Low-confidence bundled outcome
  `G5-SIN-C01-L05-O03` is not an outcome for any single area.
- Prerequisite: B-ENV-VERIFY is independent. This batch needs visually confirmed outcome
  sentences and the unmet Phase 7/8 gate before content.
- Mechanic: Word Workshop.
- Deliverables, after the gates: one atomic skill package at a time, with misconception
  catalogue, three scaffolds, role-specific items, a parallel family, and server-only rubrics.
- Validation: the Phase 2 content checks and the Phase 9 per-skill checks.
- Completion: each included area has at least one reviewed-ready atomic skill, or an explicit
  reason that no observable item can be written. Not started.

## B-SIN-WRITING

- Category: `G5-AREA-SIN-13`.
- Atomic skills: none.
- Evidence: invitation content points on printed page 9 and activity printed page 95.
  Low-confidence outcomes are not adopted.
- Prerequisite: a confirmed outcome sentence, then the Phase 7/8 gate.
- Mechanic: Story Studio, because the observable action is a short reviewed written response.
  Word Workshop remains the fallback if the confirmed task is selection rather than production.
- Deliverables: one skill package after the gates.
- Validation: rubric review and answer isolation. Free-text drafts are not logged beyond the
  existing Story Studio rule.
- Completion: one review-ready invitation skill, or a continued `NEEDS_REVIEW` note. Not started.

## B-SIN-SPELLING

- Category: `G5-AREA-SIN-16`.
- Atomic skills: none. Draft outcome `G5-SIN-C04-L10-O08` is not a skill package.
- Evidence: printed page 264 of `SRC-G5-SIN-TG-01`.
- Prerequisite: atomic decomposition of that outcome, then the Phase 7/8 gate.
- Mechanic: Word Workshop.
- Deliverables: one spelling skill package. It must not claim the whole orthography category.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: one review-ready skill whose content limits quote the adopted sentence. Not started.

## B-SIN-SENTENCES

- Categories: `G5-AREA-SIN-23`, `G5-AREA-SIN-24`.
- Atomic skills: none. Draft outcomes `G5-SIN-C04-L10-O06` and `G5-SIN-C04-L10-O01` are not
  skill packages.
- Evidence: printed page 264 of `SRC-G5-SIN-TG-01`.
- Prerequisite: one atomic skill defined from one outcome, then the Phase 7/8 gate.
- Mechanic: Word Workshop.
- Deliverables: one skill package per execution.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: each adopted outcome has its own skill package. Not started.

## B-MAT-FRACTIONS-REMAINDER

- Category: `G5-AREA-MAT-05`.
- Atomic skills already implemented: `G5-MAT-C03-L01-O01` only. Sibling nodes
  `G5-MAT-C03-L01-O02` and `G5-MAT-C03-L01-O03` are not skills.
- Evidence: `SRC-G5-MAT-TG-01` printed page 31, PDF page 50, and the existing curriculum slice.
  Trace text for the sibling outcomes is medium confidence.
- Prerequisite: visual confirmation of O02 before any new package, then the Phase 7/8 gate.
  O03 (tenths of a whole) needs a separate mechanic decision.
- Mechanic: reuse the half-set template for another equal-part count of a discrete set. Do not
  reuse it for tenths of a continuous whole unless the interaction is still a count in a set.
  No new template in this plan.
- Deliverables: at most one new skill package per execution. Retention items only if a fresh
  reserved comparison is valid.
- Validation: parallel-family, leakage, and the existing half-set contract tests.
- Completion: O02 and O03 are each either a review-ready skill or an explicit exclusion. The
  existing half skill remains `IMPLEMENTED_UNREVIEWED`. Not started.

## B-MAT-NUMBER-OPS

- Categories: `G5-AREA-MAT-01`, `G5-AREA-MAT-02`, `G5-AREA-MAT-04`, `G5-AREA-MAT-06`,
  `G5-AREA-MAT-08`, `G5-AREA-MAT-10`.
- Atomic skills: none. Draft competencies on the matrix rows are not skills.
- Evidence: `SRC-G5-MAT-TG-01` competency pages xiv–xvi and the 2020 lesson nodes on each row.
  The 2009 guide is not a source for new items.
- Prerequisite: lesson-page outcomes visually confirmed and decomposed into atomic skills, then
  the Phase 7/8 gate.
- Mechanic: Market Mission.
- Deliverables: one skill package per execution.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: each category has its confirmed atomic skills implemented as separate packages,
  or a recorded exclusion. Not started.

## B-MAT-PATTERNS

- Category: `G5-AREA-MAT-03`.
- Atomic skills: none. Competency `G5-MAT-C02` is a draft mapping.
- Evidence: printed page xiv and lessons `G5-MAT-U004`, `G5-MAT-U031`.
- Prerequisite: atomic decomposition, then the Phase 7/8 gate.
- Mechanic: Pattern Temple / Bridge Builder.
- Deliverables: one pattern skill package per execution.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: confirmed pattern skills are review-ready packages. Not started.

## B-MAT-MEASURE

- Categories: `G5-AREA-MAT-07`, `G5-AREA-MAT-09`, `G5-AREA-MAT-11`, `G5-AREA-MAT-12`.
- Atomic skills: none.
- Evidence: competencies `G5-MAT-C14`, `G5-MAT-C11`, `G5-MAT-C13`, and `G5-MAT-C12` with the
  lesson nodes on each row. The draft `MAT-MAS` parent on volume is rejected.
- Prerequisite: atomic decomposition, then the Phase 7/8 gate.
- Mechanic: Parcel Workshop.
- Deliverables: one measurement skill package per execution.
- Validation: Phase 2 and Phase 9 per-skill checks, including unit-conversion content limits.
- Completion: confirmed measurement skills are review-ready packages. Not started.

## B-MAT-DIRECTIONS

- Category: `G5-AREA-MAT-14`.
- Atomic skills: none. Competency `G5-MAT-C18` is a draft mapping.
- Evidence: printed page xvi and lesson `G5-MAT-U025`, printed pages 127–131.
- Prerequisite: an observable action is confirmed, then the Phase 7/8 gate.
- Mechanic: Pattern Temple for a spatial relationship. If the confirmed action is orientation on
  a map and that interaction is materially different, stop and document the gap before adding a
  template.
- Deliverables: one skill package, or a mechanic-gap note.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: one review-ready skill or an explicit mechanic block. Not started.

## B-MAT-DECIMALS

- Category: `G5-AREA-MAT-15`.
- Atomic skills: none. Competency `G5-MAT-C05` is a draft mapping. `MAT-FRC` is not coverage.
- Evidence: printed page xiv and lesson `G5-MAT-U018`, printed pages 98–101.
- Prerequisite: atomic decomposition that keeps decimals distinct from fractions, then the
  Phase 7/8 gate.
- Mechanic: Market Mission for tenths as quantities. Do not reuse the half-set template unless
  the action is still a discrete equal-part count.
- Deliverables: one decimals skill package per execution.
- Validation: content limits exclude the existing half-set family.
- Completion: decimals skills are separate review-ready packages. Not started.

## B-MAT-SYMBOLS

- Category: `G5-AREA-MAT-16`.
- Atomic skills: none. Competency `G5-MAT-C04` is a draft mapping. `MAT-NUM` is not coverage of
  both numbers and Roman numerals.
- Evidence: printed page xiv and lesson `G5-MAT-U029`, printed pages 147–150.
- Prerequisite: atomic decomposition, then the Phase 7/8 gate.
- Mechanic: Word Workshop for symbol recognition and transcription.
- Deliverables: one Roman-numeral skill package per execution.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: the confirmed I–XX skill or skills are review-ready packages. Not started.

## B-ENV-CONTENT

- Categories: only ENV areas whose B-ENV-VERIFY outcome has an observable classify-or-connect
  action.
- Atomic skills: none until that verification names them.
- Evidence: the verified pages from B-ENV-VERIFY.
- Prerequisite: B-ENV-VERIFY completion and the Phase 7/8 gate.
- Mechanic: Eco Explorer.
- Deliverables: one skill package per execution.
- Validation: Phase 2 and Phase 9 per-skill checks.
- Completion: each verified observable outcome has a review-ready package. Areas without an
  observable scored action stay `NEEDS_REVIEW`. Not started.
