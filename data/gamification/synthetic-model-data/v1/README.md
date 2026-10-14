# Synthetic model data v1

Development-only data with no real learners or experts:

This version models Sinhala-medium learners and Sinhala support. English content is present only
where English is the subject; Tamil-medium delivery and Tamil content are deferred.

- `default-prototype-episodes.json` — small generic offline-model fixture.
- `development-research-protocol.json` — example annotation, governance, reviewer, and threshold rules.
- `expert-review-simulation.json` — fictional double reviews, adjudication, and model-ready episodes.
- `classification-evaluation-example.json` — hand-authored predictions for evaluator smoke tests.
- `expert-review-simulation-manifest.json` — hashes, learner splits, simulated agreement/evaluation,
  and gate results.

Regenerate and verify the manifest from the repository root:

```bash
PYTHONPATH=backend python3 tools/gamification/datasets/freeze_synthetic_expert_review.py
```

The development gate may pass; the research and child-facing gate must remain blocked. See
`docs/adaptive-gamified-learning/development-data-replacement.md` before introducing real data.
