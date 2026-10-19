"""Provisional game support types for each mapped Grade 5 skill area.

The game model may choose only among the types listed for that area. The list is a
development assumption so missions can be built before educator review. It is not
an expert recommendation, and it does not approve a scaffold or open child delivery.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.gamification.content.draft_mission_catalog import assigned_template, mapped_area_ids
from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY

AREA_SUPPORT_CATALOG_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "grade5-area-support-catalog" / "v1"
PACKAGE_VERSION = "grade5-area-support-catalog-v1"
AUTHORING_BASIS = "provisional_development_assumption"
REVIEW_STATUS = "unreviewed"
GAME_SUPPORT_TYPES = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
VERBAL_RELATION_AREAS = frozenset(
    {
        "G5-AREA-SIN-03",
        "G5-AREA-SIN-04",
        "G5-AREA-SIN-05",
        "G5-AREA-SIN-06",
        "G5-AREA-SIN-07",
        "G5-AREA-SIN-08",
        "G5-AREA-SIN-09",
        "G5-AREA-SIN-10",
    }
)
INVITATION_AREA = "G5-AREA-SIN-13"
GameSupportType = Literal[
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
]
SupportRule = Literal[
    "visible_structure_and_procedure",
    "highlightable_form",
    "verbal_relation",
    "text_structure",
    "observable_situation",
]
_STRUCTURE_CONSTRAINT = (
    "Show the quantity, measure, or arrangement. The worked example uses different "
    "quantities. Each step pauses before the result."
)
_FORM_CONSTRAINT = (
    "Highlight the letter, sign, or slot already in the prompt. The worked example uses "
    "a different word with the same pattern. Each step pauses before the scored form."
)
_VERBAL_CONSTRAINT = (
    "Use a different saying or word pair in the worked example. Each step asks the "
    "learner to notice one clue and then pauses."
)
_TEXT_CONSTRAINT = (
    "Show the invitation parts: greeting, message, and close. The worked example uses "
    "a different event. Each step pauses before the sentence the learner must write."
)
_SITUATION_CONSTRAINT = (
    "Show the object or situation without marking the scored choice. The worked example "
    "uses a different object of the same kind. Each step pauses before the scored choice."
)
_VERBAL_TYPES = ("worked_parallel_example", "step_by_step_guidance")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SupportAssignment(FrozenModel):
    template_id: str
    eligible_support_types: tuple[GameSupportType, ...]
    rule: SupportRule
    rendering_constraint: str


def assignment(area_id: str) -> SupportAssignment:
    """Return the provisional candidate set for one mapped area.

    A blocked or unknown area raises ``ValueError`` through the template assignment.
    """
    template_id = assigned_template(area_id)
    if area_id.startswith("G5-AREA-MAT-"):
        return SupportAssignment(
            template_id=template_id,
            eligible_support_types=GAME_SUPPORT_TYPES,
            rule="visible_structure_and_procedure",
            rendering_constraint=_STRUCTURE_CONSTRAINT,
        )
    if area_id in VERBAL_RELATION_AREAS:
        return SupportAssignment(
            template_id=template_id,
            eligible_support_types=_VERBAL_TYPES,
            rule="verbal_relation",
            rendering_constraint=_VERBAL_CONSTRAINT,
        )
    if area_id == INVITATION_AREA:
        return SupportAssignment(
            template_id=template_id,
            eligible_support_types=GAME_SUPPORT_TYPES,
            rule="text_structure",
            rendering_constraint=_TEXT_CONSTRAINT,
        )
    if area_id.startswith("G5-AREA-SIN-"):
        return SupportAssignment(
            template_id=template_id,
            eligible_support_types=GAME_SUPPORT_TYPES,
            rule="highlightable_form",
            rendering_constraint=_FORM_CONSTRAINT,
        )
    return SupportAssignment(
        template_id=template_id,
        eligible_support_types=GAME_SUPPORT_TYPES,
        rule="observable_situation",
        rendering_constraint=_SITUATION_CONSTRAINT,
    )


class AreaSupportRow(FrozenModel):
    area_id: str
    name_en: str
    subject: Literal["MAT", "SIN", "ENV"]
    template_id: str
    eligible_support_types: tuple[GameSupportType, ...] = Field(min_length=2, max_length=3)
    rule: SupportRule
    rendering_constraint: str
    authoring_basis: Literal["provisional_development_assumption"]
    review_status: Literal["unreviewed"]

    @model_validator(mode="after")
    def match_the_area_rule(self) -> AreaSupportRow:
        expected = assignment(self.area_id)
        subject = self.area_id.split("-")[2]
        if self.subject != subject:
            raise ValueError(f"{self.area_id} subject does not match its id")
        if self.name_en.strip() == "":
            raise ValueError(f"{self.area_id} requires an English area name")
        if self.template_id != expected.template_id:
            raise ValueError(f"{self.area_id} template does not match the draft mission")
        if self.eligible_support_types != expected.eligible_support_types:
            raise ValueError(f"{self.area_id} support types do not match the area rule")
        if self.rule != expected.rule or self.rendering_constraint != expected.rendering_constraint:
            raise ValueError(f"{self.area_id} rule does not match the area rule")
        if tuple(sorted(set(self.eligible_support_types), key=GAME_SUPPORT_TYPES.index)) != (
            self.eligible_support_types
        ):
            raise ValueError(f"{self.area_id} support types must stay in canonical order")
        return self


class AreaSupportCatalog(FrozenModel):
    package_version: Literal["grade5-area-support-catalog-v1"]
    development_only: Literal[True]
    publication_status: Literal["blocked"]
    authoring_basis: Literal["provisional_development_assumption"]
    review_status: Literal["unreviewed"]
    rows: tuple[AreaSupportRow, ...] = Field(min_length=55, max_length=55)

    @model_validator(mode="after")
    def require_every_mapped_area(self) -> AreaSupportCatalog:
        area_ids = tuple(row.area_id for row in self.rows)
        if area_ids != mapped_area_ids():
            raise ValueError(
                "support rows must list mathematics, buildable Sinhala, then environmental studies"
            )
        return self

    def row(self, area_id: str) -> AreaSupportRow:
        for item in self.rows:
            if item.area_id == area_id:
                return item
        raise KeyError(area_id)

    def choices(self, area_id: str) -> tuple[GameSupportType, ...]:
        """Support types the game model may choose for this area."""
        return self.row(area_id).eligible_support_types


def load_area_support_catalog(
    path: Path = AREA_SUPPORT_CATALOG_DIRECTORY,
) -> AreaSupportCatalog:
    _verify_manifest(path)
    rows = tuple(
        json.loads(line)
        for line in (path / "area_support_types.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return AreaSupportCatalog.model_validate(
        {
            "package_version": PACKAGE_VERSION,
            "development_only": True,
            "publication_status": "blocked",
            "authoring_basis": AUTHORING_BASIS,
            "review_status": REVIEW_STATUS,
            "rows": rows,
        }
    )


def _verify_manifest(path: Path) -> None:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("invalid area support manifest")
    if manifest.get("package_version") != PACKAGE_VERSION:
        raise ValueError("invalid area support manifest")
    if (
        manifest.get("development_only") is not True
        or manifest.get("publication_status") != "blocked"
        or manifest.get("authoring_basis") != AUTHORING_BASIS
        or manifest.get("review_status") != REVIEW_STATUS
    ):
        raise ValueError(
            "area support manifest must stay provisional, development-only, and blocked"
        )
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {"area_support_types.jsonl"}:
        raise ValueError("area support manifest must pin area_support_types.jsonl")
    data = (path / "area_support_types.jsonl").read_bytes()
    if hashlib.sha256(data).hexdigest() != files["area_support_types.jsonl"]:
        raise ValueError("area_support_types.jsonl does not match the immutable manifest")
