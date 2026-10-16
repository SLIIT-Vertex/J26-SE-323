# Knowledge tracing - evaluation record

Run at 2026-10-15 18:31 UTC. Reproduce with `python -m scripts.evaluate_all --seeds 11,22,33,44,55`.

## 1. Model reproduces Colab

PASS - 17 passed, 1 warning in 0.29s

## 2. Paper selection: knapsack vs greedy

5 seed(s) (11, 22, 33, 44, 55), 100 simulated students each, question pool 328. Values are mean (sd, min to max) over the seeds.

| Measure | Knapsack (CP-SAT) | Greedy |
|---|---|---|
| total value | 6.231 (sd 0.125, 6.097 to 6.367) | 5.498 (sd 0.104, 5.371 to 5.636) |
| questions | 20.00 (sd 0.00, 19.99 to 20.00) | 18.82 (sd 0.09, 18.72 to 18.94) |
| weak + unknown share | 0.777 (sd 0.014, 0.762 to 0.797) | 0.766 (sd 0.013, 0.750 to 0.783) |
| weak skills covered | 0.470 (sd 0.023, 0.443 to 0.503) | 0.453 (sd 0.024, 0.424 to 0.490) |
| verify skills covered | 0.747 (sd 0.024, 0.725 to 0.783) | 0.742 (sd 0.025, 0.719 to 0.780) |
| minutes | 31.43 (sd 0.33, 31.06 to 31.95) | 25.80 (sd 0.36, 25.27 to 26.25) |
| run time (ms) | 64.8 (sd 8.2, 56.2 to 74.7) | 1.3 (sd 0.1, 1.2 to 1.4) |

- Value gain of knapsack over greedy: 13.33 (sd 0.63, 12.84 to 14.34) %
- Students where knapsack was better: 98.4 (sd 0.9, 97.0 to 99.0) of 100 per seed
- Students where knapsack was worse than greedy: 0 of 500 (the selector returns the better of the two, so this must be 0)
- Raw numbers per seed: `selection_eval.json`

## 3. Paper penalty sensitivity

Mastery recomputed with a paper penalty of 0.0, 0.08 and 0.12 (threshold 0.05).

3 golden histories:

```
largest change in any skill: 0.039 (threshold 0.05)
The constant paper penalty (0.08) is a safe simplification on these histories.
```

100 simulated students (30% paper answers):

```
model dkt-v2.1-e7824aaa; 100 simulated students, 1948 skill values
change in mastery when the paper penalty is 0.0 / 0.08 / 0.12: median 0.041  95th percentile 0.071  max 0.115  (threshold 0.05)
values above the threshold: 610 of 1948 (31.31%)
```

## 4. How optimistic is the model?

```
model dkt-v2.1-e7824aaa; 1000 simulated children, 1 correct out of 6 in one skill
mastery  min 0.160   median 0.261   max 0.374
```

## 5. Numbers that come from outside this repository

| Figure | Where it comes from |
|---|---|
| Model AUC / accuracy on held-out students | Colab training notebook (simulated data) |
| Handwriting accuracy, hand-over rate | benchmark_vision.py on labelled photos (not yet collected) |
| Mastery vs real paper accuracy | real children's paper results (not yet collected) |

See `docs/bhs-kt/LIMITATIONS.md` before quoting any of these.
