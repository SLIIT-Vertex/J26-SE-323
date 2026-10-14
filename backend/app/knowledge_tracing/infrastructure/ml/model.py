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
        self.skill_emb = nn.Embedding(num_skills, emb)
        self.gru = nn.GRU(emb + 3, hidden, num_layers=2, batch_first=True, dropout=0.3)
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
        src = sources if self.use_source else torch.zeros_like(sources)
        e = self.skill_emb(skills)
        h, _ = self.gru(torch.cat([e, corrects[..., None], src[..., None], penalties[..., None]], -1))
        q = torch.cat([e[:, 1:], src[:, 1:, None], diffs[:, 1:, None]], -1)  # next question's info
        return self.head(torch.cat([h[:, :-1], q], -1)).squeeze(-1)  # logits for steps 1..T-1
