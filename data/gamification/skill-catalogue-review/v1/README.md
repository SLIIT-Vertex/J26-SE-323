# Gamification-owned Grade 5 skill catalogue

This development package is generated from
`data/gamification/grade5-curriculum-game-dataset/v2/skill_candidates.jsonl`. It does not read
another component's question bank or datasets.

Every candidate has an identity binding to a gamification-owned skill ID. All records remain
draft and development-only until an authorized curriculum reviewer approves them.

`universal-skill-crosswalk.jsonl` (ADR-0010) gives every gamification skill exactly one parent
Universal Skill Node from `docs/skill_nodes.xlsx`, the shared cross-component taxonomy. The 548
rows are restored from the skill bindings pinned at commit `7033835` and are validated against
the workbook; parents are at most 16 characters so they fit Learner State. Crosswalk rows are
draft until reviewed and never replace the fine-grained gamification skill IDs.

Regenerate the package with:

```sh
PYTHONPATH=backend python3 tools/gamification/skills/build_skill_review_package.py
```
