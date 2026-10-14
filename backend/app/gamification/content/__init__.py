"""Typed, framework-free records and loaders for reviewed gamification content packages."""

from app.gamification.content.loader import PILOT_CONTENT_DIRECTORY, load_pilot_content_package
from app.gamification.content.records import (
    CANONICAL_SCAFFOLD_ARMS,
    AnswerOption,
    ContentAsset,
    ContentStatus,
    ItemDefinition,
    MisconceptionDefinition,
    ParallelGroup,
    PilotContentPackage,
    PilotSkill,
    ResponseFormat,
    ScaffoldDefinition,
    ScaffoldType,
    SourceReference,
    StructuredErrorMapping,
    TemplateRule,
)
from app.gamification.content.support_candidates import (
    SCAFFOLD_ACTION_TYPES,
    scaffold_support_candidate,
    skill_support_candidates,
)

__all__ = [
    "CANONICAL_SCAFFOLD_ARMS",
    "PILOT_CONTENT_DIRECTORY",
    "SCAFFOLD_ACTION_TYPES",
    "AnswerOption",
    "ContentAsset",
    "ContentStatus",
    "ItemDefinition",
    "MisconceptionDefinition",
    "ParallelGroup",
    "PilotContentPackage",
    "PilotSkill",
    "ResponseFormat",
    "ScaffoldDefinition",
    "ScaffoldType",
    "SourceReference",
    "StructuredErrorMapping",
    "TemplateRule",
    "load_pilot_content_package",
    "scaffold_support_candidate",
    "skill_support_candidates",
]
