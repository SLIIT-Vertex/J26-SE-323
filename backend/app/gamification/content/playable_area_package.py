"""One full playable loop for each Grade 5 area in the shipped package."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.gamification.content.area_support_catalog import (
    GAME_SUPPORT_TYPES,
    VERBAL_RELATION_AREAS,
    GameSupportType,
    assignment,
)
from app.gamification.content.draft_mission_catalog import (
    BLOCKED_AREA_IDS,
    DraftTemplateId,
    assigned_template,
)
from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY
from app.gamification.skill_catalogue.contracts import (
    UNIVERSAL_SKILL_ID_MAX_LENGTH,
    UNIVERSAL_SKILL_ID_PATTERN,
)

PLAYABLE_AREA_PACKAGE_DIRECTORY = (
    GAMIFICATION_DATA_DIRECTORY / "grade5-playable-area-package" / "v1"
)
PACKAGE_VERSION = "grade5-playable-area-package-v1"
AUTHORING_BASIS = "package_contract_only"
_AREA_ID_PATTERN = re.compile(r"^G5-AREA-(ENV|MAT|SIN)-\d{2}$")
_SINHALA_PATTERN = re.compile(r"[\u0D80-\u0DFF]")
_LOOP_ROLES = ("unsupported_before", "supported_practice", "unsupported_after")
_EVIDENCE_FIELDS = (
    "attempt_id",
    "correct",
    "difficulty",
    "response_time_ms",
    "supported",
    "hint_count",
    "environment",
    "model_ingestion_eligible",
    "skill_id",
    "universal_skill_id",
    "measurement_role",
    "assistance_state",
    "earned_score",
    "maximum_score",
    "scoring_version",
    "difficulty_source",
    "difficulty_mapping_version",
    "session_id",
    "episode_id",
    "presentation_id",
)
_VISUAL_FIELDS = (
    "mean_eye_openness",
    "std_eye_openness",
    "mean_gaze_ratio",
    "std_gaze_ratio",
    "mean_pitch",
    "mean_yaw",
    "mean_roll",
    "mean_abs_pitch",
    "mean_abs_yaw",
    "mean_abs_roll",
    "face_visibility_ratio",
)
_PROHIBITED_LEARNER_STATE_FIELDS = (
    "overlap_time",
    "first_action",
    "position",
    "original",
    "task_progress",
)
_ABSENCE_STATUSES = (
    "NO_RELEVANT_PASSAGES",
    "NO_APPROVED_SOURCE",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_ERROR",
)
MeasurementRoleName = Literal["unsupported_before", "supported_practice", "unsupported_after"]
SourceStatus = Literal["mapped_draft", "no_grade5_source"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_sinhala(value: str, label: str) -> None:
    if _SINHALA_PATTERN.search(value) is None:
        raise ValueError(f"{label} must be Sinhala")


class ServerRubricReference(FrozenModel):
    """Pointer to the server rubric. The scored answer is not stored here."""

    rubric_id: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    scoring_version: str = Field(min_length=1)
    maximum_score: int = Field(gt=0)
    server_authoritative: Literal[True]
    correct_only_when_every_part_correct: Literal[True]


class PlayableAreaItem(FrozenModel):
    measurement_role: MeasurementRoleName
    assistance_state: Literal["none", "scaffold_active"]
    item_revision_id: str = Field(min_length=1)
    parallel_family_id: str = Field(min_length=1)
    prompt_si: str = Field(min_length=1)
    surface_form: str = Field(min_length=1)
    correct_response: str = Field(min_length=1)
    rubric: ServerRubricReference

    @model_validator(mode="after")
    def pair_assistance_with_the_role(self) -> PlayableAreaItem:
        _require_sinhala(self.prompt_si, f"{self.measurement_role} prompt")
        unsupported = self.measurement_role in {"unsupported_before", "unsupported_after"}
        if unsupported and self.assistance_state != "none":
            raise ValueError(f"{self.measurement_role} requires assistance_state=none")
        if not unsupported and self.assistance_state != "scaffold_active":
            raise ValueError("supported_practice requires assistance_state=scaffold_active")
        return self


class PlayableAreaScaffold(FrozenModel):
    support_type: GameSupportType
    body_si: str = Field(min_length=1)
    answer_leakage_rule: Literal["no_probe_values_or_answers"]

    @model_validator(mode="after")
    def keep_the_scaffold_in_sinhala(self) -> PlayableAreaScaffold:
        _require_sinhala(self.body_si, "scaffold")
        return self


class PlayableAreaRow(FrozenModel):
    """One playable loop. Required fields have no defaults, so a gap fails."""

    area_id: str
    template_id: DraftTemplateId
    source_status: SourceStatus
    items: tuple[PlayableAreaItem, ...] = Field(min_length=1, max_length=3)
    eligible_support_types: tuple[GameSupportType, ...] = Field(min_length=2, max_length=3)
    scaffold: PlayableAreaScaffold
    universal_skill_id: str | None
    no_universal_parent: bool
    prompt_si: str = Field(min_length=1)
    curriculum_source_id: str | None

    @model_validator(mode="after")
    def require_a_complete_loop(self) -> PlayableAreaRow:
        if _AREA_ID_PATTERN.fullmatch(self.area_id) is None:
            raise ValueError(
                "area id must be a Grade 5 mathematics, Sinhala, or environmental area"
            )
        _require_sinhala(self.prompt_si, "child-facing prompt")
        roles = tuple(item.measurement_role for item in self.items)
        if len(roles) != 3 or set(roles) != set(_LOOP_ROLES):
            missing = [role for role in _LOOP_ROLES if role not in roles]
            detail = f"; missing {', '.join(missing)}" if missing else ""
            raise ValueError(
                "a loop requires unsupported_before, supported_practice, and "
                f"unsupported_after{detail}"
            )
        self._require_distinct_probes()
        self._reject_answer_leakage()
        self._require_support_choice()
        self._require_source_and_parent()
        return self

    def _require_distinct_probes(self) -> None:
        by_role = {item.measurement_role: item for item in self.items}
        before = by_role["unsupported_before"]
        after = by_role["unsupported_after"]
        if before.surface_form.strip() == after.surface_form.strip():
            raise ValueError("unsupported_before and unsupported_after must differ in surface form")
        if before.correct_response.strip() == after.correct_response.strip():
            raise ValueError("unsupported_before and unsupported_after must differ in answer")
        revisions = tuple(item.item_revision_id for item in self.items)
        if len(set(revisions)) != len(revisions):
            raise ValueError("loop items require distinct item revisions")
        families = {item.parallel_family_id for item in self.items}
        if len(families) != 1:
            raise ValueError("loop items must share one parallel family")

    def _reject_answer_leakage(self) -> None:
        for item in self.items:
            answer = item.correct_response.strip()
            if answer in self.scaffold.body_si:
                raise ValueError("a scaffold must not contain the scored answer")

    def _require_support_choice(self) -> None:
        if tuple(dict.fromkeys(self.eligible_support_types)) != self.eligible_support_types:
            raise ValueError("eligible support types must not repeat")
        ordered = tuple(sorted(self.eligible_support_types, key=GAME_SUPPORT_TYPES.index))
        if ordered != self.eligible_support_types:
            raise ValueError("eligible support types must stay in canonical order")
        if self.area_id in VERBAL_RELATION_AREAS and (
            "visual_guidance" in self.eligible_support_types
            or self.scaffold.support_type == "visual_guidance"
        ):
            raise ValueError("a verbal-relation area rejects visual_guidance")
        if self.scaffold.support_type not in self.eligible_support_types:
            raise ValueError("the scaffold must be one eligible support type")
        if self.area_id in BLOCKED_AREA_IDS:
            if self.template_id != "word_workshop":
                raise ValueError("a placeholder reuses word_workshop")
            if self.eligible_support_types != GAME_SUPPORT_TYPES:
                raise ValueError("a placeholder reuses the three game support types")
            return
        if self.template_id != assigned_template(self.area_id):
            raise ValueError(f"{self.area_id} template does not match the draft mission")
        # This package holds one fixed scaffold per area, so it lists only the original game
        # types; the multi-help types are delivered by the game flows, not by this package.
        expected = tuple(
            support
            for support in assignment(self.area_id).eligible_support_types
            if support in GAME_SUPPORT_TYPES
        )
        if self.eligible_support_types != expected:
            raise ValueError(f"{self.area_id} support types do not match the area rule")

    def _require_source_and_parent(self) -> None:
        placeholder = self.area_id in BLOCKED_AREA_IDS or self.source_status == "no_grade5_source"
        if placeholder:
            if self.area_id not in BLOCKED_AREA_IDS or self.source_status != "no_grade5_source":
                raise ValueError("a placeholder must carry no_grade5_source")
            if self.curriculum_source_id is not None:
                raise ValueError("a placeholder must not carry a curriculum source citation")
            if self.no_universal_parent is not True or self.universal_skill_id is not None:
                raise ValueError("a placeholder must carry the no-parent marker")
            return
        if self.no_universal_parent or self.universal_skill_id is None:
            unsettled_environment = (
                self.area_id == "G5-AREA-ENV-05"
                and self.no_universal_parent
                and self.universal_skill_id is None
            )
            unsettled_sinhala = (
                self.area_id.startswith("G5-AREA-SIN-")
                and self.area_id not in BLOCKED_AREA_IDS
                and self.no_universal_parent
                and self.universal_skill_id is None
            )
            if not unsettled_sinhala and not unsettled_environment:
                raise ValueError("a mapped area requires a Universal skill parent")
            return
        if (
            UNIVERSAL_SKILL_ID_PATTERN.fullmatch(self.universal_skill_id) is None
            or len(self.universal_skill_id) > UNIVERSAL_SKILL_ID_MAX_LENGTH
        ):
            raise ValueError("universal_skill_id must be a parent id of at most 16 characters")


class SharedLearnerPlace(FrozenModel):
    learner_id_column: Literal["id"] = "id"
    grade: Literal[5] = 5
    preferred_language: Literal["si"] = "si"
    curriculum_medium: Literal["si"] = "si"
    duplicates_learner_profile: Literal[False] = False


class CurriculumRetrievalPlace(FrozenModel):
    purpose: Literal["CONTENT_AUTHORING"] = "CONTENT_AUTHORING"
    skill_id_field: Literal["universal_skill_id"] = "universal_skill_id"
    missing_passage_blocks_play: Literal[False] = False
    absence_statuses: tuple[str, ...] = _ABSENCE_STATUSES
    index_as_curriculum_evidence: Literal[False] = False

    @model_validator(mode="after")
    def keep_the_absence_statuses(self) -> CurriculumRetrievalPlace:
        if self.absence_statuses != _ABSENCE_STATUSES:
            raise ValueError("curriculum absence statuses must stay the recorded set")
        return self


class KnowledgeTracingPlace(FrozenModel):
    mastery_reader: Literal["MasteryProvider"] = "MasteryProvider"
    writes_tables: Literal[False] = False
    event_type: Literal["gamification_item_scored"] = "gamification_item_scored"
    model_ingestion_eligible: Literal[False] = False
    hint_count: tuple[Literal[0, 1], ...] = (0, 1)
    evidence_fields: tuple[str, ...] = _EVIDENCE_FIELDS

    @model_validator(mode="after")
    def keep_the_evidence_shape(self) -> KnowledgeTracingPlace:
        if self.hint_count != (0, 1):
            raise ValueError("hint_count must stay 0 or 1")
        if self.evidence_fields != _EVIDENCE_FIELDS:
            raise ValueError("scored-evidence fields must stay the recorded set")
        return self


class LearnerStatePlace(FrozenModel):
    visual_fields: tuple[str, ...] = _VISUAL_FIELDS
    face_visibility_ratio_min: Literal[0] = 0
    face_visibility_ratio_max: Literal[1] = 1
    consent_purpose: Literal["learner_state_camera"] = "learner_state_camera"
    request_tutor_support: Literal["request_tutor_support"] = "request_tutor_support"
    request_reengagement_support: Literal["request_reengagement_support"] = (
        "request_reengagement_support"
    )
    missing_result_rejects_answer: Literal[False] = False
    prohibited_fields: tuple[str, ...] = _PROHIBITED_LEARNER_STATE_FIELDS

    @model_validator(mode="after")
    def keep_the_visual_snapshot(self) -> LearnerStatePlace:
        if self.visual_fields != _VISUAL_FIELDS:
            raise ValueError("visual snapshot fields must stay the recorded 11 names")
        if self.prohibited_fields != _PROHIBITED_LEARNER_STATE_FIELDS:
            raise ValueError("prohibited learner-state fields must stay the recorded set")
        return self


class AdaptiveTutorPlace(FrozenModel):
    chooses_scaffold: Literal[False] = False
    records_recommendation: Literal["request_tutor_support"] = "request_tutor_support"
    generates_tutor_text: Literal[False] = False


class ParticipationRewardPlace(FrozenModel):
    academic_mastery_evidence: Literal[False] = False
    points_field: Literal["points"] = "points"
    reason_code_field: Literal["reason_code"] = "reason_code"
    counts_toward_unsupported_score: Literal[False] = False
    counts_toward_independence_gain: Literal[False] = False


class OtherComponentPlaces(FrozenModel):
    """Field places for the other components. This package does not call them."""

    shared_learner: SharedLearnerPlace = Field(default_factory=SharedLearnerPlace)
    curriculum_retrieval: CurriculumRetrievalPlace = Field(default_factory=CurriculumRetrievalPlace)
    knowledge_tracing: KnowledgeTracingPlace = Field(default_factory=KnowledgeTracingPlace)
    learner_state: LearnerStatePlace = Field(default_factory=LearnerStatePlace)
    adaptive_tutor: AdaptiveTutorPlace = Field(default_factory=AdaptiveTutorPlace)
    participation_reward: ParticipationRewardPlace = Field(default_factory=ParticipationRewardPlace)


class PlayableAreaPackage(FrozenModel):
    package_version: Literal["grade5-playable-area-package-v1"]
    authoring_basis: Literal["package_contract_only"]
    areas: tuple[PlayableAreaRow, ...] = ()
    component_places: OtherComponentPlaces = Field(default_factory=OtherComponentPlaces)

    @model_validator(mode="after")
    def keep_area_rows_distinct(self) -> PlayableAreaPackage:
        area_ids = tuple(row.area_id for row in self.areas)
        if len(area_ids) > 56 or len(set(area_ids)) != len(area_ids):
            raise ValueError(
                "playable area rows must be distinct and at most the 56 supplied areas"
            )
        return self


def load_playable_area_package(
    path: Path = PLAYABLE_AREA_PACKAGE_DIRECTORY,
) -> PlayableAreaPackage:
    """Load the playable-area package."""
    _verify_manifest(path)
    payload = json.loads((path / "areas.json").read_text(encoding="utf-8"))
    return PlayableAreaPackage.model_validate(payload)


def _verify_manifest(path: Path) -> None:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("invalid playable area manifest")
    if (
        manifest.get("package_version") != PACKAGE_VERSION
        or manifest.get("authoring_basis") != AUTHORING_BASIS
    ):
        raise ValueError("invalid playable area manifest")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {"areas.json"}:
        raise ValueError("playable area manifest must pin areas.json")
    data = (path / "areas.json").read_bytes()
    if hashlib.sha256(data).hexdigest() != files["areas.json"]:
        raise ValueError("areas.json does not match the immutable manifest")
