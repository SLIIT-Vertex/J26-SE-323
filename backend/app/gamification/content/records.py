from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from app.gamification.modeling.support_selection.reference_table import ReferencePolicyTable
from app.gamification.skill_catalogue.contracts import SkillReview


class ContentStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class ScaffoldType(StrEnum):
    VISUAL_GUIDANCE = "visual_guidance"
    WORKED_EXAMPLE = "worked_example"
    STEP_BY_STEP_GUIDANCE = "step_by_step_guidance"
    CONCEPT_REMINDER = "concept_reminder"


CANONICAL_SCAFFOLD_ARMS = (
    ScaffoldType.VISUAL_GUIDANCE,
    ScaffoldType.WORKED_EXAMPLE,
    ScaffoldType.STEP_BY_STEP_GUIDANCE,
)


class ResponseFormat(StrEnum):
    SINGLE_CHOICE = "single_choice"
    BINARY_SORT = "binary_sort"
    NUMERIC_CONSTRUCTION = "numeric_construction"


def _frozen(mapping: Mapping[str, object] | None) -> Mapping[str, object] | None:
    return None if mapping is None else MappingProxyType(dict(mapping))


def _require_reviewer(
    status: ContentStatus, reviewer_id: str | None, reviewed_on: str | None
) -> None:
    if status is ContentStatus.APPROVED and (not reviewer_id or not reviewed_on):
        raise ValueError("approved content requires reviewer identity and date")


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_id: str
    page: str
    curriculum_node_id: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.page or not self.curriculum_node_id:
            raise ValueError("source references require a source, page, and curriculum node")


@dataclass(frozen=True, slots=True)
class PilotSkill:
    review: SkillReview
    universal_skill_id: str
    crosswalk_version: str
    curriculum_node_ids: tuple[str, ...]
    id_status: str

    @property
    def skill_id(self) -> str:
        return self.review.skill_code


@dataclass(frozen=True, slots=True)
class MisconceptionDefinition:
    code: str
    skill_ids: tuple[str, ...]
    label_si: str
    label_en: str
    description: str
    observable_error_patterns: tuple[str, ...]
    distinguishing_evidence: tuple[str, ...]
    remediation_notes: tuple[str, ...]
    catalogue_version: str
    authoring_basis: str
    reserved: bool
    status: ContentStatus
    reviewer_id: str | None = None
    reviewed_on: str | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.skill_ids or not self.catalogue_version:
            raise ValueError("misconceptions require a code, skills, and catalogue version")
        _require_reviewer(self.status, self.reviewer_id, self.reviewed_on)


@dataclass(frozen=True, slots=True)
class AnswerOption:
    option_id: str
    text: str
    text_en: str
    misconception_code: str | None
    alternative_misconception_codes: tuple[str, ...]
    stimulus: Mapping[str, object] | None = None
    correct_group: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stimulus", _frozen(self.stimulus))


@dataclass(frozen=True, slots=True)
class ItemDefinition:
    item_id: str
    skill_id: str
    grade: int
    medium: str
    item_type: str
    response_format: ResponseFormat
    cognitive_operation: str
    question_text: str
    prompt_en: str
    stimulus: Mapping[str, object] | None
    answer_options: tuple[AnswerOption, ...]
    correct_option_id: str | None
    difficulty: int
    compatible_templates: tuple[str, ...]
    default_template: str
    available_scaffold_ids: tuple[str, ...]
    parallel_group_id: str
    source_reference: SourceReference
    content_version: str
    status: ContentStatus
    reviewer_id: str | None = None
    reviewed_on: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stimulus", _frozen(self.stimulus))
        if self.default_template not in self.compatible_templates:
            raise ValueError("default template must be one of the compatible templates")
        option_ids = {option.option_id for option in self.answer_options}
        if len(option_ids) != len(self.answer_options):
            raise ValueError("item option IDs must be unique")
        if self.response_format is ResponseFormat.BINARY_SORT:
            if self.correct_option_id is not None:
                raise ValueError("sort items have no single correct option")
            if any(option.correct_group is None for option in self.answer_options):
                raise ValueError("every sort card requires a correct group")
        else:
            if self.correct_option_id not in option_ids:
                raise ValueError("correct option must be one of the item options")
            for option in self.answer_options:
                is_correct = option.option_id == self.correct_option_id
                if not is_correct and option.misconception_code is None:
                    raise ValueError("every wrong option requires a misconception code")
        _require_reviewer(self.status, self.reviewer_id, self.reviewed_on)

    def option(self, option_id: str) -> AnswerOption:
        for option in self.answer_options:
            if option.option_id == option_id:
                return option
        raise LookupError(f"{self.item_id} has no option {option_id}")


@dataclass(frozen=True, slots=True)
class ParallelGroup:
    parallel_group_id: str
    skill_id: str
    item_type: str
    difficulty_band: str
    response_format: ResponseFormat
    cognitive_operation: str
    item_ids: tuple[str, ...]
    equivalence_version: str
    status: ContentStatus
    reviewer_id: str | None = None
    reviewed_on: str | None = None

    def __post_init__(self) -> None:
        if len(set(self.item_ids)) != len(self.item_ids) or len(self.item_ids) < 2:
            raise ValueError("parallel groups need at least two distinct items")
        _require_reviewer(self.status, self.reviewer_id, self.reviewed_on)


@dataclass(frozen=True, slots=True)
class ContentAsset:
    content_asset_id: str
    scaffold_type: ScaffoldType
    skill_id: str
    language: str
    title_si: str
    title_en: str
    body_si: tuple[str, ...]
    body_en: tuple[str, ...]
    diagram: Mapping[str, object] | None
    source_reference: SourceReference
    status: ContentStatus
    reviewer_id: str | None = None
    reviewed_on: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagram", _frozen(self.diagram))
        if not self.body_si or len(self.body_si) != len(self.body_en):
            raise ValueError("content assets need matching Sinhala and English steps")
        _require_reviewer(self.status, self.reviewer_id, self.reviewed_on)


@dataclass(frozen=True, slots=True)
class ScaffoldDefinition:
    scaffold_id: str
    scaffold_type: ScaffoldType
    skill_ids: tuple[str, ...]
    target_misconception_ids: tuple[str, ...]
    assistance_level: int
    content_asset_id: str
    maximum_duration_ms: int
    maximum_number_of_steps: int
    answer_leakage_rules: tuple[str, ...]
    withdrawal_rule: str
    language: str
    version: str
    limits_status: str
    status: ContentStatus
    reviewer_id: str | None = None
    reviewed_on: str | None = None

    def __post_init__(self) -> None:
        if not self.skill_ids or not self.target_misconception_ids:
            raise ValueError("scaffolds require skills and target misconceptions")
        if self.maximum_duration_ms <= 0 or self.maximum_number_of_steps <= 0:
            raise ValueError("scaffold limits must be positive")
        if self.withdrawal_rule != "remove_before_verification":
            raise ValueError("scaffolds must be withdrawn before verification")
        _require_reviewer(self.status, self.reviewer_id, self.reviewed_on)


@dataclass(frozen=True, slots=True)
class TemplateRule:
    item_type: str
    compatible_templates: tuple[str, ...]
    response_formats: tuple[ResponseFormat, ...]
    table_version: str


@dataclass(frozen=True, slots=True)
class StructuredErrorMapping:
    structured_error_code: str
    misconception_code: str
    alternative_misconception_codes: tuple[str, ...]
    item_id: str | None
    option_id: str | None
    pattern_code: str | None
    mapping_version: str


@dataclass(frozen=True, slots=True)
class PilotContentPackage:
    package_version: str
    versions: Mapping[str, str]
    skills: Mapping[str, PilotSkill]
    misconceptions: Mapping[str, MisconceptionDefinition]
    items: Mapping[str, ItemDefinition]
    parallel_groups: Mapping[str, ParallelGroup]
    scaffolds: Mapping[str, ScaffoldDefinition]
    content_assets: Mapping[str, ContentAsset]
    template_rules: Mapping[str, TemplateRule]
    error_mappings: Mapping[str, StructuredErrorMapping]
    reference_policy: ReferencePolicyTable

    def __post_init__(self) -> None:
        for name in (
            "versions",
            "skills",
            "misconceptions",
            "items",
            "parallel_groups",
            "scaffolds",
            "content_assets",
            "template_rules",
            "error_mappings",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def scaffolds_for_skill(self, skill_id: str) -> tuple[ScaffoldDefinition, ...]:
        return tuple(
            scaffold for scaffold in self.scaffolds.values() if skill_id in scaffold.skill_ids
        )

    def groups_for_skill(self, skill_id: str) -> tuple[ParallelGroup, ...]:
        return tuple(group for group in self.parallel_groups.values() if group.skill_id == skill_id)

    def misconception_for(self, item_id: str, option_id: str) -> str:
        mapping = self.error_mappings.get(f"{item_id}:{option_id}")
        if mapping is None:
            raise LookupError(f"no structured error mapping for {item_id}:{option_id}")
        return mapping.misconception_code
