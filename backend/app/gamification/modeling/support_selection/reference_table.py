"""Authored skill × top-misconception reference rows. The model does not read files."""

from dataclasses import dataclass

from app.gamification.domain.types import SupportActionType

TABLE_VERSION = "authored-reference-policy-v1"

# ADR-0008 names. Duplicated here so this package does not import content records.
SCAFFOLD_TYPE_TO_ACTION = {
    "visual_guidance": SupportActionType.VISUAL_GUIDANCE,
    "worked_example": SupportActionType.SIMILAR_WORKED_EXAMPLE,
    "step_by_step_guidance": SupportActionType.GUIDED_STEPS,
    "concept_reminder": SupportActionType.CONCEPTUAL_HINT,
}


@dataclass(frozen=True, slots=True)
class ReferencePolicyRow:
    skill_id: str
    top_misconception_code: str
    preferred_scaffold_type: str
    rule: str
    authoring_basis: str = "provisional_assumption"


@dataclass(frozen=True, slots=True)
class ReferencePolicyTable:
    version: str
    rows: tuple[ReferencePolicyRow, ...]

    def __post_init__(self) -> None:
        if self.version != TABLE_VERSION:
            raise ValueError("reference policy table version is not authored-reference-policy-v1")
        seen: set[tuple[str, str]] = set()
        for row in self.rows:
            key = (row.skill_id, row.top_misconception_code)
            if key in seen:
                raise ValueError(f"duplicate reference row for {key[0]} × {key[1]}")
            seen.add(key)
            if action_type_for(row.preferred_scaffold_type) is None:
                raise ValueError(f"unknown scaffold type {row.preferred_scaffold_type}")

    def preferred_type(self, skill_id: str, top_misconception_code: str) -> str | None:
        for row in self.rows:
            if row.skill_id == skill_id and row.top_misconception_code == top_misconception_code:
                return row.preferred_scaffold_type
        return None


def action_type_for(label: str) -> SupportActionType | None:
    mapped = SCAFFOLD_TYPE_TO_ACTION.get(label)
    if mapped is not None:
        return mapped
    try:
        return SupportActionType(label)
    except ValueError:
        return None
