# Skill catalogue review v1

This Phase 5A development package inventories the 30 stable Knowledge Tracing skills and every
current question mapping. It provides draft development mappings for all 548 Grade 5 curriculum
candidates and draft review records for the 25 stable skills used by those mappings. No record is
approved for research or child-facing use.

Version 1 is scoped to Sinhala-medium learners: instructions and adaptive support are Sinhala,
while English remains valid as subject content. Tamil-medium delivery, Tamil content, Tamil labels,
and Tamil evaluation are deliberately deferred to a later version.

Files:

- `skill-inventory.jsonl` — stable codes, indices, labels, and question counts.
- `question-skill-mappings.jsonl` — normalized primary and secondary mappings from the current bank.
- `pilot-skill-reviews.jsonl` and `pilot-skill-bindings.jsonl` — hand-authored detailed examples
  and overrides retained as builder inputs.
- `development-skill-reviews.jsonl` — complete generated draft reviews for referenced stable skills.
- `grade5-candidate-skill-bindings.jsonl` — complete generated mapping of all 548 candidates.
- `MAPPING_RULES.md` — concise, reviewable rules and confidence policy used to generate coverage.
- `model-slice-evaluation.json` — synthetic Phase 4 evaluation grouped by bound skill and content
  language, with learner medium recorded separately.
- `change-impact-report.json` — compatibility assessment before any code/index change.
- `schema.json` and `manifest.json` — import contract, hashes, counts, and gates.

Regenerate derived files from the repository root:

```bash
PYTHONPATH=backend python3 tools/gamification/skills/build_skill_review_package.py
```

This package passes the internal development gate and may be used to build Phase 5B for the
Sinhala-medium Grade 5 application. External review is a future validation activity, not a blocker
for the current development phase. Keep generated records visibly marked as development drafts.
