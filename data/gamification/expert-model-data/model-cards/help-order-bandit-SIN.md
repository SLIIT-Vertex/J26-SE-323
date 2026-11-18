# Model card: Sinhala help-order bandit

Model 2 in the Sinhala games (`SIN`, 3 games). It chooses the order of help after a
wrong unaided answer, in the proposed condition only.

## What it is

- **A LinUCB bandit run greedily (no exploration), expert-initialised, learning online from valid
  Independence Gain.** Each help type has its own ridge regression that predicts the valid
  Independence Gain of showing that help first; the help with the highest prediction comes first.
  `alpha = 0` and `epsilon_min = 0`: it never tries a help just to learn.
- **Help types:** `visual_guidance`, `worked_parallel_example`, `step_by_step_guidance`. A help the area does not offer, or cannot draw for this item, is
  skipped.
- **Context** (`area-bandit-context-v1`, 43 numbers per help): the reason family and uncertainty
  from Model 1 and the current-session Learning State reading, as one of 24 cell indicators plus
  11 main effects, and 8 numbers about this child on this skill: their own record with that help
  (credited episodes, independent-success rate, mean gain, rounds it did not help), whether their
  previous episode's first help did not transfer, and how often they needed help, with a "present"
  flag where a value can be missing.
- **Code:** `backend/app/gamification/modeling/support_selection/game_bandit.py`; used by
  `application/game_help_order.py`; stored by `infrastructure/db/game_help_bandit_store.py`.

## Evidence

**Provisional expert assumptions, not reviewed by a teacher.** The starting gains are positions in
the earlier rule-based order turned into numbers (0.60 for the first help, 0.05 less for each next
one), from `expert-model-data-v1` (`reviewed_by: null`). No child's answers were used to fit them.
Before any child has played, the bandit reproduces the earlier order exactly (tested for every
reason family, uncertainty and Learning State reading).

## How it learns

- **Shared learning:** every participant's valid proposed episode updates the Sinhala bandit
  once, whichever child played it. Baseline and invalid episodes never update it.
- **Credit rule `weighted-round-credit-v1`:** the help the support loop ended on is scored with the
  measured Independence Gain at full weight; each help that failed while shown is scored 0 at
  `failed_round_weight` 0.5; a help that was not shown, follow-up help after the measured answer,
  and an episode whose every help failed but whose after-answer was right teach nothing. Supported
  correctness is never a reward.
- **State:** the approved artifact plus an ordered ledger of applied observations. Rebuilding the
  artifact with the ledger applied in order must give exactly the stored state; each decision
  keeps a snapshot of the numbers it was scored with.

## Provisional settings

Each is reported by a sensitivity replay on the research dashboard: the stored ledger is replayed
from the expert data with that one value changed, and the decisions whose first help would change
are counted. A replay never invents the outcome of a help that was not given; at the approved
value it reproduces every stored decision.

| Setting | Value | Replayed with |
|---|---|---|
| `prior_strength` (how many episodes the expert start is worth) | 8 | 4, 8, 16 |
| `own_success_rate_gain` (weight of the child's own independent-success rate with a help) | 0.3 | 0, 0.15, 0.3 |
| `failed_round_weight` | 0.5 | 0, 0.25, 0.5, 1 |
| `uninformed_precision` (how firmly features the expert data says nothing about start at 0) | 100 | 10, 100, 1000 |
| `previous_first_not_transferred_gain` | −0.45 (a first help that did not transfer goes last next time, even a learned preference, as the earlier Sinhala packages did) | not replayed |
| Tie tolerance (gains this close count as equal; the cell's order wins) | 1e-9 | not replayed |

## Approval

The artifact is approved once, by the researcher, with
`python -m scripts.approve_game_help_bandit --subject SIN --approve <sha256> --approved-by <name>`;
after that it learns without re-approval. A change of design (the expert data, the context, the
failed-round weight, the uninformed precision or the credit rule) builds a new artifact with a new
hash, which needs its own approval; approving it retires this one, and the new one starts again at
ledger position 0. Until a subject has an approved artifact, its proposed condition gets the fixed
order and records `no_approved_policy`.

**Approval record** (development database, read on 2026-11-18):

| Field | Value |
|---|---|
| Model | `game-help-order-bandit:SIN`, `area-help-order-bandit-v1.0d057e50cdb6` |
| Artifact SHA-256 | `0d057e50cdb688c327e05f5fd055f7ae4cc2bd414006792dbba420cdc9ac2a04` |
| Approved by | `hareeshagunasekara` |
| Approved at | 2026-11-18 12:43:56 UTC |
| Built from | `expert-model-data-v1`, context `area-bandit-context-v1` |
| Ledger at approval | position 0 (no episode learned yet) |

## Limits

- Every logged choice was the bandit's best guess, so every propensity is 1 and off-policy
  evaluators cannot be used; the main test is valid Independence Gain in the proposed condition
  against the fixed order of the baseline condition.
- With history it no longer copies the earlier rules: one own independent success can outweigh a
  Learning State reading, mixed results need more evidence than before, and it never moves on to a
  help just because it has not been tried.
- Sinhala has only 3 games, so its bandit gathers evidence slowly; the research dashboard reports its evidence count on its own.
- Every Sinhala cell starts from the authored order (visual, worked example, guided questions); the lead-by-reason table the earlier rules computed but did not use is kept in the data as `unused_reference`.
