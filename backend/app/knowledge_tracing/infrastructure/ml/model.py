"""The knowledge tracing network. Must stay identical to the training script
(research/knowledge-tracing/mindbridge_dkt_v2.py, Cell 6), or the saved weights will not fit.
"""

import torch
from torch import nn


class MindBridgeDKT(nn.Module):
    """GRU over the answer history, then a head that sees the NEXT question's skill, source
    and difficulty. `use_source=False` hides the source from the model (training ablation)."""

    def __init__(
        self, num_skills: int = 30, use_source: bool = True, emb: int = 32, hidden: int = 96
    ) -> None:
        super().__init__()
        self.use_source = use_source
        # each of the 30 skills becomes a list of 32 numbers the network can learn
        self.skill_emb = nn.Embedding(num_skills, emb)
        # the gru reads the history one answer at a time and keeps a memory of it.
        # per answer it gets: skill (32 numbers) + correct + source + penalty = emb + 3
        self.gru = nn.GRU(emb + 3, hidden, num_layers=2, batch_first=True, dropout=0.3)
        # the head turns "memory + next question" into one number
        self.head = nn.Sequential(
            nn.Linear(hidden + emb + 2, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 1)
        )

    def forward(
        self,
        skills: torch.Tensor,
        corrects: torch.Tensor,
        sources: torch.Tensor,
        penalties: torch.Tensor,
        diffs: torch.Tensor,
    ) -> torch.Tensor:
        # use_source=False hides game/paper from the model (used for the no-source test in training)
        src = sources if self.use_source else torch.zeros_like(sources)
        e = self.skill_emb(skills)
        h, _ = self.gru(torch.cat([e, corrects[..., None], src[..., None], penalties[..., None]], -1))
        # the memory after step t is paired with the question at step t+1, so every step predicts the next answer.
        # difficulty comes in only here (for the next question), never for the past answers
        q = torch.cat([e[:, 1:], src[:, 1:, None], diffs[:, 1:, None]], -1)  # next question's info
        return self.head(torch.cat([h[:, :-1], q], -1)).squeeze(-1)  # logits for steps 1..T-1
