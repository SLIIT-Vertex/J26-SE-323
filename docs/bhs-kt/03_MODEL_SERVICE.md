# 03 — Model service (knowledge tracing)

The model is **already trained** (in Google Colab, script in `reference/mindbridge_dkt_v2_1.py`). This document describes how to **serve** it. Do not retrain inside the backend.

## 1. What the model is

`MindBridgeDKT`: a question-aware GRU knowledge-tracing network.

- The GRU reads the child's history, one step per attempt: skill embedding, whether the answer was correct, the source (digital = 1, paper = 0) and the penalty.
- A small head then takes the GRU state **plus the next question's** skill, source and difficulty, and outputs the probability that the child answers that next question correctly.
- Trained on **simulated** data (1,500 students). Test AUC ≈ 0.79 against a best-possible ≈ 0.82 on the simulation; the source feature adds ≈ +0.03. These numbers say the method works on data that behaves like the simulator. They do **not** prove accuracy on real children. Say so in any UI text, comments and the report.

## 2. Feature spec (read from `shared/feature_spec.json`)

| Item | Rule |
| --- | --- |
| Skill index | Position in `skills` list (0..29). Never reorder. |
| Source | `1` digital, `0` paper |
| Difficulty to model | `easy → 0.0`, `medium → 0.5`, `hard → 1.0` (training used `difficulty/0.30`, i.e. the same three values) |
| Penalty (digital) | `0.6 * min(hints/3, 1) + 0.4 * min(time_ms/180000, 1)`; null hints → 0 hints; null time → use 12000 ms |
| Penalty (paper) | Constant `0.08` (**DECISION D2**: paper answers have no per-question time or hints; 0.08 matches the training mean) |
| History order | Ascending `(answered_at, id)`, digital and paper mixed |
| History cap | The **last 140** attempts (the training sequences were 80–140 long; longer is untested) |
| Unknown skill | fewer than 3 attempts in that skill → `mastery = null` |
| Mastery meaning | P(correct) on a **medium paper** question of that skill |

The penalty is stored in `attempts.penalty` at insert time using this exact formula (one function `compute_penalty(source, time_ms, hints)` used everywhere).

## 3. Model class (must be identical to training)

```python
# app/ml/model.py
import torch
import torch.nn as nn

class MindBridgeDKT(nn.Module):
    def __init__(self, num_skills: int = 30, use_source: bool = True, emb: int = 32, hidden: int = 96):
        super().__init__()
        self.use_source = use_source
        self.skill_emb = nn.Embedding(num_skills, emb)
        self.gru = nn.GRU(emb + 3, hidden, num_layers=2, batch_first=True, dropout=0.3)
        self.head = nn.Sequential(nn.Linear(hidden + emb + 2, 64), nn.ReLU(),
                                  nn.Dropout(0.2), nn.Linear(64, 1))

    def forward(self, skills, corrects, sources, penalties, diffs):
        src = sources if self.use_source else torch.zeros_like(sources)
        e = self.skill_emb(skills)
        h, _ = self.gru(torch.cat([e, corrects[..., None], src[..., None], penalties[..., None]], -1))
        q = torch.cat([e[:, 1:], src[:, 1:, None], diffs[:, 1:, None]], -1)   # NEXT question's info
        return self.head(torch.cat([h[:, :-1], q], -1)).squeeze(-1)           # logits for steps 1..T-1
```

Load once at startup:

```python
state = torch.load(settings.model_weights_path, map_location="cpu", weights_only=True)
model = MindBridgeDKT(use_source=True); model.load_state_dict(state); model.eval()
```

`model_version` = `"dkt-v2.1-" + first 8 hex of the SHA-256 of the weights file`. Save it in every `mastery_snapshots` and `papers` row.

## 4. Inference

The trick used in training notebook Cell 11: append one extra "query step" to the history, set its skill to the skill being asked about, source = paper, difficulty = the level being asked about, and read the logit of that last step. Run all questions in one batch.

```python
# app/ml/inference.py  (equivalent to knowledge_state() in the training script)
import numpy as np, torch

PAPER = 0
NUM_SKILLS = 30

@torch.no_grad()
def _predict(model, skills, corrects, sources, penalties, query_skills, query_diffs, query_source=PAPER):
    """History arrays (length T >= 1). Returns P(correct) for each (query_skill, query_diff) pair."""
    n = len(query_skills)
    def rep(a, extra, dtype):
        base = torch.tensor(a, dtype=dtype)[None].repeat(n, 1)
        return torch.cat([base, torch.as_tensor(extra, dtype=dtype)[:, None]], 1)
    sk = torch.cat([torch.tensor(skills, dtype=torch.long)[None].repeat(n, 1),
                    torch.as_tensor(query_skills, dtype=torch.long)[:, None]], 1)
    co = rep(corrects, np.zeros(n), torch.float32)
    so = rep(sources, np.full(n, float(query_source)), torch.float32)
    pe = rep(penalties, np.zeros(n), torch.float32)
    di = rep(np.zeros(len(skills)), np.asarray(query_diffs, dtype=float), torch.float32)
    logits = model(sk, co, so, pe, di)
    return torch.sigmoid(logits[:, -1]).numpy()

def compute_mastery(model, skills, corrects, sources, penalties, min_attempts=3, difficulty=0.5):
    if len(skills) == 0:
        return {i: {"mastery": None, "attempts": 0} for i in range(NUM_SKILLS)}
    q_sk = np.arange(NUM_SKILLS)
    p = _predict(model, skills, corrects, sources, penalties, q_sk, np.full(NUM_SKILLS, difficulty))
    counts = np.bincount(np.asarray(skills, dtype=int), minlength=NUM_SKILLS)
    return {int(i): {"mastery": round(float(p[i]), 3) if counts[i] >= min_attempts else None,
                     "attempts": int(counts[i])} for i in range(NUM_SKILLS)}

def predict_item_probs(model, skills, corrects, sources, penalties):
    """For the paper generator: P(correct) on a PAPER question for every (skill, difficulty) pair.
    Returns array shape (30, 3) for difficulty values 0.0 / 0.5 / 1.0. Always computed, even for unknown
    skills; the generator decides how to treat unknown skills."""
    if len(skills) == 0:
        return None            # brand-new child: no history, the generator uses diagnostic mode
    q_sk = np.repeat(np.arange(NUM_SKILLS), 3)
    q_df = np.tile([0.0, 0.5, 1.0], NUM_SKILLS)
    return _predict(model, skills, corrects, sources, penalties, q_sk, q_df).reshape(NUM_SKILLS, 3)
```

Translate to the API as skill **codes** (via `shared/feature_spec.json`), not indices.

### Service function

`mastery.recompute(student_id)`:
1. Load history (`attempts` for the student ordered by `answered_at, id`), keep the last 140.
2. Build arrays with `features.build_arrays`.
3. Call `compute_mastery`; write a `mastery_snapshots` row; return it.
4. Run it after every grading confirmation and after each digital session (debounce: at most once every 30 seconds per student).

Models are small; one call takes well under a second on CPU. Set `torch.set_num_threads(1)` in the web process to avoid thread fights with the server.

## 5. Golden test (the most important test of this component)

Goal: prove the backend reproduces the Colab results exactly, so there is no training/serving mismatch.

**Step A — the user exports fixtures from Colab** (run after Cell 11 of the training notebook):

```python
import json
fixtures = []
for uid in test_ids[:3]:
    g = df[df.user_id == int(uid)]
    ks = knowledge_state(demo_model, g['skill_id'].values, g['correct'].values,
                         g['source'].values, g['penalty'].values)
    fixtures.append({
        "skills":   g['skill_id'].astype(int).tolist(),
        "corrects": g['correct'].astype(int).tolist(),
        "sources":  g['source'].astype(int).tolist(),
        "penalties": g['penalty'].astype(float).tolist(),
        "expected": {name: v["mastery"] for name, v in ks.items()},   # None where unknown
    })
json.dump(fixtures, open("golden_history.json", "w"))
```

Download `golden_history.json` and `mindbridge_dkt_v2_best.pt` from Colab and put them in `backend/tests/fixtures/` and `backend/app/ml/weights/`.

**Step B — the test:**

```python
def test_matches_colab():
    for f in json.load(open("tests/fixtures/golden_history.json")):
        out = compute_mastery(model, f["skills"], f["corrects"], f["sources"], f["penalties"])
        for i, code in enumerate(SKILLS):
            exp = f["expected"][code]
            got = out[i]["mastery"]
            assert (exp is None) == (got is None)
            if exp is not None:
                assert abs(exp - got) < 1e-3
```

If this fails, stop and fix before building anything on top (usual causes: wrong skill order, `eval()` not called, difficulty scale, extra query step missing).

## 6. Sensitivity check for the paper penalty (decision D2)

Write `scripts/penalty_sensitivity.py`: take the golden histories, set every **paper** attempt's penalty to 0.0, 0.08 and 0.12, recompute mastery, and print the largest absolute change per skill. If the change is above 0.05 anywhere, report it to the user (it means the missing paper time/hints matter and the group should decide whether to collect them).

## 7. Cold start

- A child with no history → all skills `null`; the generator builds a **diagnostic** paper (see `04`).
- A skill with 1–2 attempts is `null` but the attempts count is still returned, so the UI can show "needs a few more questions".
- Never show a number for a `null` skill, and never fill it with 0.5.

## 8. Retraining later (outside this repo's runtime)

If real data arrives, retraining happens in Colab with the same feature spec; copy the new weights and a new golden fixture, bump the version, rerun the golden test. Real-data retraining is future work and must not change `shared/feature_spec.json` without bumping its `version`.
