"""Typed, framework-free records and loaders for reviewed gamification content packages."""

from app.gamification.content.loader import PILOT_CONTENT_DIRECTORY, load_pilot_content_package
from app.gamification.content.phase2_registry import (
    PHASE2_CONTENT_DIRECTORY,
    PHASE2_PACKAGE_VERSION,
    PublicPhase2Package,
    load_phase2_public_package,
    load_phase2_server_answer_keys,
)
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
    "PHASE2_CONTENT_DIRECTORY",
    "PHASE2_PACKAGE_VERSION",
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
    "PublicPhase2Package",
    "ResponseFormat",
    "ScaffoldDefinition",
    "ScaffoldType",
    "SourceReference",
    "StructuredErrorMapping",
    "TemplateRule",
    "load_phase2_public_package",
    "load_phase2_server_answer_keys",
    "load_pilot_content_package",
    "scaffold_support_candidate",
    "skill_support_candidates",
]
