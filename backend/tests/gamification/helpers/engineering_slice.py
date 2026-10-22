"""Synthetic approved content for the development engineering episode.

The strings are fixture labels. They are not textbook items, and production
session composition does not load this package.
"""

from app.gamification.content.records import (
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
from app.gamification.domain.types import SupportActionType
from app.gamification.modeling.support_selection.reference_table import (
    TABLE_VERSION,
    ReferencePolicyRow,
    ReferencePolicyTable,
)
from app.gamification.skill_catalogue.contracts import ReviewStatus, SkillReview, SourceCitation

SKILL = "G5-MAT-C99-L01-O01"
SOURCE = SourceReference("engineering-source", "1", "engineering-node")
REVIEWER = "engineering-fixture"
REVIEWED = "2026-10-15"


def _skill() -> PilotSkill:
    review = SkillReview(
        skill_code=SKILL,
        stable_index=99,
        taxonomy_version="engineering-taxonomy-v1",
        domain="MAT",
        grade=5,
        status=ReviewStatus.DRAFT,
        development_only=True,
        learner_medium="si",
        required_label_languages=("si",),
        deferred_languages=("en", "ta"),
        scope_note="synthetic engineering slice for the delivery API",
        definition="synthetic comparison used only by tests",
        labels={"si": "පරීක්ෂණය", "en": None, "ta": None},
        prerequisites=(),
        observable_success=("selects the labelled option",),
        misconceptions=("MAT-FRC-M06",),
        distinguishing_evidence=("option A",),
        eligible_support_action_types=(
            SupportActionType.VISUAL_GUIDANCE,
            SupportActionType.SIMILAR_WORKED_EXAMPLE,
            SupportActionType.GUIDED_STEPS,
        ),
        verification_pair_rules={"unseen": True},
        source_citations=(SourceCitation("engineering-source", "1", "1", (SKILL,)),),
    )
    return PilotSkill(
        review=review,
        universal_skill_id="MAT-FRC",
        crosswalk_version="engineering-crosswalk-v1",
        curriculum_node_ids=("engineering-node",),
        id_status="engineering",
    )


def _misconception(code: str) -> MisconceptionDefinition:
    return MisconceptionDefinition(
        code=code,
        skill_ids=(SKILL,),
        label_si="පරීක්ෂණ",
        label_en="engineering",
        description="synthetic class",
        observable_error_patterns=("option A",),
        distinguishing_evidence=("different option",),
        remediation_notes=("withdraw before verification",),
        catalogue_version="engineering-catalogue-v1",
        authoring_basis="engineering-fixture",
        reserved=False,
        status=ContentStatus.APPROVED,
        reviewer_id=REVIEWER,
        reviewed_on=REVIEWED,
    )


def _item(item_id: str, correct_text: str) -> ItemDefinition:
    return ItemDefinition(
        item_id=item_id,
        skill_id=SKILL,
        grade=5,
        medium="si",
        item_type="engineering_choice",
        response_format=ResponseFormat.SINGLE_CHOICE,
        cognitive_operation="compare",
        question_text=f"පරීක්ෂණ අයිතමය {item_id}",
        prompt_en=f"engineering item {item_id}",
        stimulus=None,
        answer_options=(
            AnswerOption("A", "වැරදි සලකුණ", "wrong mark", "MAT-FRC-M06", ()),
            AnswerOption("B", correct_text, "right mark", None, ()),
        ),
        correct_option_id="B",
        difficulty=1,
        compatible_templates=("choice_quest",),
        default_template="choice_quest",
        available_scaffold_ids=("ENG-VIS", "ENG-WRK", "ENG-STP"),
        parallel_group_id="ENG-PAIR",
        source_reference=SOURCE,
        content_version="engineering-content-v1",
        status=ContentStatus.APPROVED,
        reviewer_id=REVIEWER,
        reviewed_on=REVIEWED,
    )


def _asset(asset_id: str, scaffold_type: ScaffoldType) -> ContentAsset:
    return ContentAsset(
        content_asset_id=asset_id,
        scaffold_type=scaffold_type,
        skill_id=SKILL,
        language="si",
        title_si="උදව්",
        title_en="help",
        body_si=("පියවර පමණයි",),
        body_en=("a step only",),
        diagram=None,
        source_reference=SOURCE,
        status=ContentStatus.APPROVED,
        reviewer_id=REVIEWER,
        reviewed_on=REVIEWED,
    )


def _scaffold(scaffold_id: str, asset_id: str, scaffold_type: ScaffoldType) -> ScaffoldDefinition:
    return ScaffoldDefinition(
        scaffold_id=scaffold_id,
        scaffold_type=scaffold_type,
        skill_ids=(SKILL,),
        target_misconception_ids=("MAT-FRC-M06",),
        assistance_level=1,
        content_asset_id=asset_id,
        maximum_duration_ms=60_000,
        maximum_number_of_steps=3,
        answer_leakage_rules=("no_final_answer",),
        withdrawal_rule="remove_before_verification",
        language="si",
        version="engineering-scaffold-v1",
        limits_status="authored",
        status=ContentStatus.APPROVED,
        reviewer_id=REVIEWER,
        reviewed_on=REVIEWED,
    )


def engineering_package() -> PilotContentPackage:
    items = {
        "ENG-I1": _item("ENG-I1", "නිවැරදි එක"),
        "ENG-I2": _item("ENG-I2", "නිවැරදි දෙක"),
    }
    assets = {
        "ENG-A-VIS": _asset("ENG-A-VIS", ScaffoldType.VISUAL_GUIDANCE),
        "ENG-A-WRK": _asset("ENG-A-WRK", ScaffoldType.WORKED_EXAMPLE),
        "ENG-A-STP": _asset("ENG-A-STP", ScaffoldType.STEP_BY_STEP_GUIDANCE),
    }
    scaffolds = {
        "ENG-VIS": _scaffold("ENG-VIS", "ENG-A-VIS", ScaffoldType.VISUAL_GUIDANCE),
        "ENG-WRK": _scaffold("ENG-WRK", "ENG-A-WRK", ScaffoldType.WORKED_EXAMPLE),
        "ENG-STP": _scaffold("ENG-STP", "ENG-A-STP", ScaffoldType.STEP_BY_STEP_GUIDANCE),
    }
    codes = ("MAT-FRC-M05", "MAT-FRC-M06", "MAT-FRC-M07", "unknown/other")
    return PilotContentPackage(
        package_version="engineering-slice-v1",
        versions={
            "skill_taxonomy_version": "engineering-taxonomy-v1",
            "catalogue_version": "engineering-catalogue-v1",
            "scaffold_version": "engineering-scaffold-v1",
            "equivalence_version": "engineering-equivalence-v1",
            "template_table_version": "engineering-templates-v1",
        },
        skills={SKILL: _skill()},
        misconceptions={code: _misconception(code) for code in codes},
        items=items,
        parallel_groups={
            "ENG-PAIR": ParallelGroup(
                parallel_group_id="ENG-PAIR",
                skill_id=SKILL,
                item_type="engineering_choice",
                difficulty_band="1",
                response_format=ResponseFormat.SINGLE_CHOICE,
                cognitive_operation="compare",
                item_ids=("ENG-I1", "ENG-I2"),
                equivalence_version="engineering-equivalence-v1",
                status=ContentStatus.APPROVED,
                reviewer_id=REVIEWER,
                reviewed_on=REVIEWED,
            )
        },
        scaffolds=scaffolds,
        content_assets=assets,
        template_rules={
            "engineering_choice": TemplateRule(
                item_type="engineering_choice",
                compatible_templates=("choice_quest",),
                response_formats=(ResponseFormat.SINGLE_CHOICE,),
                table_version="engineering-templates-v1",
            )
        },
        error_mappings={
            "ENG-I1:A": StructuredErrorMapping(
                "ENG-I1:A", "MAT-FRC-M06", (), "ENG-I1", "A", None, "engineering-errors-v1"
            ),
            "ENG-I2:A": StructuredErrorMapping(
                "ENG-I2:A", "MAT-FRC-M06", (), "ENG-I2", "A", None, "engineering-errors-v1"
            ),
        },
        reference_policy=ReferencePolicyTable(
            version=TABLE_VERSION,
            rows=tuple(
                ReferencePolicyRow(SKILL, code, "visual_guidance", "engineering row")
                for code in codes
            ),
        ),
    )
