"""Check the saved knowledge model on the same simulated test students the Colab notebook used.

    python -m scripts.validate_model

What it does, in order:
  1. Rebuilds the simulated students exactly as the Colab notebook did (same generator, same seed 42,
     1500 students) and picks the same 15% test students (they were never used to train the model).
  2. Scores them with the weights saved in this repository (the ones the backend really uses).
  3. Prints the test AUC for all answers, paper answers and game answers, next to two reference points:
     "previous answer" (a very simple baseline) and the ORACLE (the true probability the simulator used,
     the best any model could do).
  4. Prints a calibration table (does "70% predicted" really come true about 70% of the time?) and what
     happens to the AUC when the source flag is hidden at prediction time.

It only reads the repository's files and needs no database. It uses simulated data, so it tells you how
well the model learned the simulator, not how it will do on real children.
"""

import argparse
import sys
from itertools import pairwise

import numpy as np
import torch

from app.config import get_settings
from app.knowledge_tracing.domain.feature_spec import get_feature_spec, resolve_path
from app.knowledge_tracing.infrastructure.ml.model import MindBridgeDKT

NUM_STUDENTS = 1500
DATA_SEED = 42
DIGITAL, PAPER = 1, 0
DIFF_LEVELS = np.array([0.0, 0.15, 0.30])  # easy / medium / hard, as in the Colab generator


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def simulate(num_students: int, num_skills: int, seed: int):
    """The Colab generator (Cell 2), line for line. One dict of arrays per student."""
    rng = np.random.default_rng(seed)
    students = []
    for _ in range(num_students):
        focus = rng.choice(num_skills, size=rng.integers(3, 6), replace=False)  # only 3 to 5 skills each
        lr = rng.uniform(0.04, 0.12)
        forget = rng.uniform(0.001, 0.006)
        mastery = {int(s): rng.uniform(0.0, 0.25) for s in focus}
        last_seen = {int(s): 0 for s in focus}
        n_steps = int(rng.integers(80, 141))
        cur = int(rng.choice(focus))
        rows = []
        for t in range(n_steps):
            if rng.random() > 0.6:
                cur = int(rng.choice(focus))
            m = mastery[cur] * np.exp(-forget * (t - last_seen[cur]))
            source = DIGITAL if rng.random() < 0.70 else PAPER
            diff = float(rng.choice(DIFF_LEVELS))
            ability = m + (0.20 if source == DIGITAL else 0.0) - diff
            guess = 0.25 if source == DIGITAL else 0.10
            slip = 0.08
            p_true = guess + (1 - guess - slip) * _sigmoid(10.0 * (ability - 0.5))
            correct = int(rng.random() < p_true)
            if source == DIGITAL:
                time_ms = rng.normal(12000, 2500)
                hints = int(rng.integers(1, 3)) if rng.random() < (1 - p_true) else 0
            else:
                time_ms = rng.normal(35000, 6000)
                hints = 0
            if correct == 0:
                time_ms *= 1.5
            time_ms = max(1000.0, float(time_ms))
            penalty = 0.6 * min(hints / 3.0, 1.0) + 0.4 * min(time_ms / 180000.0, 1.0)
            rows.append((cur, correct, source, diff, penalty, p_true))
            mastery[cur] = min(1.0, m + lr * (1 - m))
            last_seen[cur] = t
        a = np.array(rows, dtype=float)
        students.append(
            {"skills": a[:, 0].astype(int), "corrects": a[:, 1], "sources": a[:, 2], "diffs": a[:, 3],
             "penalties": a[:, 4], "p_true": a[:, 5]}
        )
    return students


def test_student_ids(n: int, seed: int) -> np.ndarray:
    """The 15% test students, chosen the way scikit-learn's train_test_split(test_size=0.15) chose them."""
    n_test = int(np.ceil(0.15 * n))
    return np.random.RandomState(seed).permutation(n)[:n_test]


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """Area under the ROC curve: the chance a random right answer is scored above a random wrong one."""
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    sorted_p = p[order]
    i = 0
    while i < len(p):  # tied scores share the average rank
        j = i
        while j + 1 < len(p) and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    positives = y == 1
    n_pos, n_neg = positives.sum(), (~positives).sum()
    return float((ranks[positives].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


@torch.no_grad()
def predict_students(model: MindBridgeDKT, students):
    """Model P(correct) for steps 1.. of every student (step 0 has no history), plus what to compare with."""
    y, p, src, oracle, prev = [], [], [], [], []
    for s in students:
        logits = model(
            torch.tensor(s["skills"], dtype=torch.long)[None],
            *(torch.tensor(s[key], dtype=torch.float32)[None] for key in ("corrects", "sources", "penalties")),
            torch.tensor(s["diffs"], dtype=torch.float32)[None] / 0.30,  # 0, 0.15, 0.30 scaled to 0, 0.5, 1
        )
        p.append(torch.sigmoid(logits)[0].numpy())
        y.append(s["corrects"][1:])
        src.append(s["sources"][1:])
        oracle.append(s["p_true"][1:])
        prev.append(s["corrects"][:-1])
    cat = np.concatenate
    return cat(y), cat(p), cat(src), cat(oracle), cat(prev)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    spec = get_feature_spec()
    model = MindBridgeDKT(num_skills=len(spec.skills), use_source=True)
    weights = resolve_path(get_settings().model_weights_path)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    model.eval()

    students = simulate(NUM_STUDENTS, len(spec.skills), DATA_SEED)
    test_ids = test_student_ids(NUM_STUDENTS, DATA_SEED)
    print(f"{len(students)} simulated students rebuilt; {len(test_ids)} test students (never used for training)")
    y, p, src, oracle, prev = predict_students(model, [students[i] for i in test_ids])
    paper, game = src == PAPER, src == DIGITAL

    print(f"\n{len(y)} test answers ({paper.sum()} paper, {game.sum()} game), correct rate {y.mean():.3f}\n")
    print(f"{'':28}{'all':>8}{'paper':>8}{'game':>8}")
    for name, scores in (("model (saved weights)", p), ("previous-answer baseline", prev), ("ORACLE (best possible)", oracle)):
        print(f"{name:28}{auc(y, scores):8.4f}{auc(y[paper], scores[paper]):8.4f}{auc(y[game], scores[game]):8.4f}")
    log_loss = float(-np.mean(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1))))
    print(f"\nlog loss of the model: {log_loss:.4f}")

    print("\ncalibration: when the model says X, how often is the answer really right?")
    print(f"{'model says':>12}{'answers':>10}{'really right':>14}")
    edges = np.linspace(0, 1, 6)
    for lo, hi in pairwise(edges):
        pick = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if pick.sum():
            print(f"{lo:5.1f} - {hi:3.1f}{pick.sum():10d}{y[pick].mean():14.3f}")

    model.use_source = False  # hide the source flag at prediction time
    _, p_hidden, *_ = predict_students(model, [students[i] for i in test_ids])
    print(f"\nwith the source flag hidden at prediction time, AUC (all) goes {auc(y, p):.4f} -> {auc(y, p_hidden):.4f}")
    print("(this shows the model uses the source; the retrained 'no source' variant A in the notebook is the real ablation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
