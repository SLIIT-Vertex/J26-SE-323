"""Typed, framework-free records and loaders for reviewed gamification content packages."""

from app.gamification.content.curriculum_registry import (
    CURRICULUM_CONTENT_DIRECTORY,
    CURRICULUM_PACKAGE_VERSION,
    PublicCurriculumPackage,
    load_curriculum_public_package,
    load_curriculum_server_answer_keys,
)
from app.gamification.content.draft_mission_catalog import (
    DraftMissionCatalog,
    DraftMissionRecord,
    load_draft_mission_catalog,
)
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
    "CURRICULUM_CONTENT_DIRECTORY",
    "CURRICULUM_PACKAGE_VERSION",
    "PILOT_CONTENT_DIRECTORY",
    "SCAFFOLD_ACTION_TYPES",
    "AnswerOption",
    "ContentAsset",
    "ContentStatus",
    "DraftMissionCatalog",
    "DraftMissionRecord",
    "ItemDefinition",
    "MisconceptionDefinition",
    "ParallelGroup",
    "PilotContentPackage",
    "PilotSkill",
    "PublicCurriculumPackage",
    "ResponseFormat",
    "ScaffoldDefinition",
    "ScaffoldType",
    "SourceReference",
    "StructuredErrorMapping",
    "TemplateRule",
    "load_curriculum_public_package",
    "load_curriculum_server_answer_keys",
    "load_draft_mission_catalog",
    "load_pilot_content_package",
    "scaffold_support_candidate",
    "skill_support_candidates",
]
