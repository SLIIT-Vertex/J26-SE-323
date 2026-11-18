# Expert model data

**Provisional expert assumptions, not learned from children.** Every value here was taken from
what the rule-based Model 1 and Model 2 do in the games today. No teacher has reviewed it yet
(`reviewed_by: null`), and no child's answers were used to fit it.

The research models start from this data: the Bayesian misconception model (Model 1) and the
LinUCB help-order bandit (Model 2). Nothing in the app reads it yet.

Built by `tools/gamification/datasets/build_expert_model_data.py` from the frozen reference
fixtures in `backend/tests/gamification/fixtures/`, never by calling the rules. `manifest.json`
pins the fixtures' SHA-256 and the commit that last changed them.

## Files

| File | What it holds |
|---|---|
| `misconception_tables/<area>.json` | One per game area. Its codes; a uniform class prior; one likelihood row per evidence band and error code (`__unseen__` for a code the area does not list), which is the game's belief for that answer before the learner prior; the area's evidence-band rule; interaction rewrites (Subtraction only); and whether an `unknown_or_other` top label alone makes the reading uncertain. Every skill in the area uses the area's table. |
| `misconception_settings.json` | Shared by every area: how each evidence band is detected, which bands are weak, the uncertainty rule and the learner-prior settings. |
| `reason_families.json` | Per subject, each label's reason family (`representation`, `procedure`, `relation`, `prerequisite`, `unclear`) and what decided it. Labels that no pattern matched are `unclear` with `needs_review: true`. |
| `support_gains.json` | Per subject, the expected valid Independence Gain of each help type for every reason family, Model 1 uncertainty and Learning State reading. Sorting the drawable helps by it, ties broken by the subject order, gives today's order. `prior_strength` says how many episodes of evidence this start is worth. |

## Reading the values

- **Evidence bands** replace a continuous evidence quality: `normal`, `sparse` (no response time),
  `low_quality` (no interaction summary, in the games that read one) and, for Sinhala, `motor`,
  `rendering` and `motor_and_rendering`. Sinhala ignores timing, so it is never `sparse`.
- **Uncertain** means: top probability below 0.4, or the top two within 0.1, or a `sparse` or
  `low_quality` band, or, in an area whose table says so, an answer whose own likelihood row puts
  `unknown_or_other` first (before the learner prior). Motor and rendering bands only weaken the
  row, so a clear learner history can still name a reason after a motor difficulty.
- **Expected gains** are positions in today's order turned into numbers (0.60 for the first help,
  0.05 less for each next one). They are a starting belief for the bandit, not a measurement.
  With `prior_strength` 8, shared evidence overturns them as the rules would: the first help gives
  way after two failed rounds or one helped-but-not-independent result, and another help leads
  after two independent successes. `own_success_rate_gain` (0.3) is the starting weight of a
  child's own independent-success rate with a help, enough to put that help first for that child.
  Gains within `tie_tolerance` count as equal, and the help earlier in the cell's order wins.
  `previous_first_not_transferred_gain` is the starting weight of "the child's previous episode on
  this skill began with this help and the after-answer was still wrong". It is −0.45 for Sinhala,
  which moves that help from first to last as the Sinhala packages do, even when it was the child's
  learned preference (the 0.15 that puts it below the last help, plus the 0.3 a full own success
  rate could add back), and 0 for Maths and English, whose rules do not react to it.
- **Sinhala** games deliver one authored order (visual, worked, guided) whatever the reason, so
  every Sinhala cell holds that order. The Sinhala lead-by-reason table the rules compute but do
  not use is kept under `unused_reference`.

Regenerate or check with:

```bash
PYTHONPATH=backend python3 tools/gamification/datasets/build_expert_model_data.py
PYTHONPATH=backend python3 tools/gamification/datasets/build_expert_model_data.py --check
```
