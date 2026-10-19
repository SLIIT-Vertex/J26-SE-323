"""Development-only missions for the 55 mapped Grade 5 skill areas.

Each record is keyed by a ``G5-AREA-*`` id and stores the cited curriculum node,
a reused template, ``development_only``, and ``publication_status=blocked``.
The two areas with no Grade 5 source are omitted. Mathematics missions carry
the 65 medium-confidence learning-outcome slots. Sinhala missions carry 8
high-confidence draft items and 76 held slots. Environmental Studies missions
carry 117 held slots. A held slot stores the traced string and does not create
a child question. This package does not replace the existing half-set skill.

The default call is the production loader and rejects the package. A development
or test caller may read it only when ``allow_draft`` is true.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY

DRAFT_MISSION_CATALOG_DIRECTORY = (
    GAMIFICATION_DATA_DIRECTORY / "grade5-draft-mission-catalog" / "v1"
)
PACKAGE_VERSION = "grade5-draft-mission-catalog-v1"
MISSION_COUNT = 55
MATHEMATICS_OUTCOME_SLOT_COUNT = 65
SINHALA_DRAFT_ITEM_COUNT = 8
SINHALA_HELD_SLOT_COUNT = 76
ENVIRONMENTAL_HELD_SLOT_COUNT = 117
BLOCKED_AREA_IDS = frozenset({"G5-AREA-SIN-11", "G5-AREA-SIN-12"})
# High-confidence verb outcomes that are not an area's cited node. Each traced
# sentence applies the verb, so the draft item sits on the verb area.
SINHALA_VERB_DRAFT_FILING = {
    "G5-SIN-C04-L10-O03": "G5-AREA-SIN-22",
    "G5-SIN-C04-L10-O04": "G5-AREA-SIN-22",
    "G5-SIN-C04-L10-O05": "G5-AREA-SIN-22",
}
# Speaking competency G5-SIN-C02 has no supplied area. Its low-confidence
# outcomes are held here. The traced string is stored and no question is written.
SINHALA_UNMATCHED_HELD_AREA = "G5-AREA-SIN-01"
EXISTING_HALF_SET_SKILL_ID = "G5-MAT-C03-L01-O01"
MEDIUM_CONFIDENCE_CAVEAT = (
    "Medium-confidence trace. This sentence is not an approved question."
)
AREA_ID_PATTERN = re.compile(r"^G5-AREA-(ENV|MAT|SIN)-\d{2}$")
NODE_ID_PATTERN = re.compile(r"^G5-(ENV-U\d{2}|MAT-C\d{2}|SIN-C\d{2}-L\d{2}-[KO]\d{2})$")
MATHEMATICS_OUTCOME_ID_PATTERN = re.compile(r"^G5-MAT-C\d{2}-L\d{2}-O\d{2}$")
SINHALA_OUTCOME_ID_PATTERN = re.compile(r"^G5-SIN-C\d{2}-L\d{2}-O\d{2}$")
ENVIRONMENTAL_OUTCOME_ID_PATTERN = re.compile(r"^G5-ENV-C\d{2,3}-L\d{2}-O\d{2}$")
SINHALA_LEVEL_PATTERN = re.compile(r"^(G5-SIN-C\d{2})-L\d{2}$")
# Ancestor competency cited by each mathematics area. Outcomes under any other
# competency are not a supplied-area match.
COMPETENCY_AREA = {
    "G5-MAT-C01": "G5-AREA-MAT-01",
    "G5-MAT-C06": "G5-AREA-MAT-02",
    "G5-MAT-C02": "G5-AREA-MAT-03",
    "G5-MAT-C07": "G5-AREA-MAT-04",
    "G5-MAT-C03": "G5-AREA-MAT-05",
    "G5-MAT-C08": "G5-AREA-MAT-06",
    "G5-MAT-C14": "G5-AREA-MAT-07",
    "G5-MAT-C09": "G5-AREA-MAT-08",
    "G5-MAT-C11": "G5-AREA-MAT-09",
    "G5-MAT-C15": "G5-AREA-MAT-10",
    "G5-MAT-C13": "G5-AREA-MAT-11",
    "G5-MAT-C12": "G5-AREA-MAT-12",
    "G5-MAT-C16": "G5-AREA-MAT-13",
    "G5-MAT-C18": "G5-AREA-MAT-14",
    "G5-MAT-C05": "G5-AREA-MAT-15",
    "G5-MAT-C04": "G5-AREA-MAT-16",
}
# Draft filing only. These competencies are Grade 5 mathematics outcomes and are
# not supplied areas. The slot text names the trace competency.
OUTSIDE_SUPPLIED_AREA_FILING = {
    "G5-MAT-C10": "G5-AREA-MAT-08",
    "G5-MAT-C19": "G5-AREA-MAT-14",
}
DraftTemplateId = Literal[
    "market_mission",
    "half_set",
    "pattern_temple",
    "parcel_workshop",
    "word_workshop",
    "story_studio",
    "eco_explorer",
]
_MARKET_AREAS = frozenset({1, 2, 4, 6, 8, 10, 15})
_PARCEL_AREAS = frozenset({7, 9, 11, 12})
_PATTERN_AREAS = frozenset({3, 13, 14})


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def mapped_area_ids() -> tuple[str, ...]:
    """Mathematics, then buildable Sinhala, then Environmental Studies."""
    mathematics = tuple(f"G5-AREA-MAT-{number:02d}" for number in range(1, 17))
    sinhala = tuple(
        f"G5-AREA-SIN-{number:02d}" for number in range(1, 26) if number not in {11, 12}
    )
    environmental = tuple(f"G5-AREA-ENV-{number:02d}" for number in range(1, 17))
    return mathematics + sinhala + environmental


def assigned_template(area_id: str) -> DraftTemplateId:
    """Return the reused template named for this area.

    Measurement areas use Parcel Workshop. Shapes use Pattern Temple, the
    placement mechanic named for that area. Roman numerals use Word Workshop,
    the existing symbol mechanic for that area. No new template is added.
    """
    prefix, number_text = area_id.rsplit("-", 1)
    number = int(number_text)
    if prefix == "G5-AREA-MAT":
        if number in _MARKET_AREAS:
            return "market_mission"
        if number == 5:
            return "half_set"
        if number in _PATTERN_AREAS:
            return "pattern_temple"
        if number in _PARCEL_AREAS:
            return "parcel_workshop"
        if number == 16:
            return "word_workshop"
    if prefix == "G5-AREA-SIN":
        if number in {11, 12}:
            raise ValueError(f"{area_id} has no Grade 5 source and is not a draft mission")
        if number == 13:
            return "story_studio"
        return "word_workshop"
    if prefix == "G5-AREA-ENV" and 1 <= number <= 16:
        return "eco_explorer"
    raise ValueError(f"{area_id} is not a mapped draft mission area")


def sinhala_draft_area(node_id: str, area_by_cited_node: dict[str, str]) -> tuple[str, bool]:
    """Return the buildable area for one high-confidence Sinhala outcome.

    An outcome that is an area's cited node uses that area. The three verb
    sentences that are not a cited node stay on the verb area and are marked
    as a non-match.
    """
    if node_id in area_by_cited_node:
        return area_by_cited_node[node_id], True
    filed = SINHALA_VERB_DRAFT_FILING.get(node_id)
    if filed is None:
        raise ValueError(f"{node_id} is not a high-confidence Sinhala draft item")
    return filed, False


def sinhala_held_area(
    parent_level_id: str,
    areas_by_level: dict[str, tuple[str, ...]],
    areas_by_competency: dict[str, tuple[str, ...]],
) -> str:
    """Return a buildable area that can hold one low-confidence Sinhala string.

    A level with one area uses that area. Otherwise the first area under the
    same competency is the container. Speaking has no supplied area, so those
    strings are held on the first buildable Sinhala mission. This does not
    turn the string into that area's question.
    """
    areas = areas_by_level.get(parent_level_id, ())
    if len(areas) == 1:
        return areas[0]
    match = SINHALA_LEVEL_PATTERN.fullmatch(parent_level_id)
    if match is None:
        raise ValueError(f"{parent_level_id} is not a Sinhala competency level")
    candidates = areas_by_competency.get(match.group(1), ())
    if candidates:
        return candidates[0]
    if SINHALA_UNMATCHED_HELD_AREA in BLOCKED_AREA_IDS:
        raise ValueError("held Sinhala slots cannot use a blocked area")
    return SINHALA_UNMATCHED_HELD_AREA


class MathematicsOutcomeSlot(FrozenModel):
    node_id: str
    parent_area_id: str
    trace_competency_id: str
    supplied_area_match: bool
    confidence: Literal["medium"]
    draft_item: Literal[True]
    publication_status: Literal["blocked"]
    item_text: str

    @model_validator(mode="after")
    def keep_the_medium_confidence_caveat(self) -> MathematicsOutcomeSlot:
        if not MATHEMATICS_OUTCOME_ID_PATTERN.fullmatch(self.node_id):
            raise ValueError("mathematics outcome slot node id is not a learning-outcome id")
        if not self.trace_competency_id or not self.parent_area_id.startswith("G5-AREA-MAT-"):
            raise ValueError("outcome slot requires its trace competency and a mathematics area")
        if MEDIUM_CONFIDENCE_CAVEAT not in self.item_text:
            raise ValueError("outcome item text must keep the medium-confidence caveat")
        if self.item_text.removesuffix(MEDIUM_CONFIDENCE_CAVEAT).strip() == "":
            raise ValueError("outcome item text must keep the traced sentence")
        if not self.supplied_area_match and self.trace_competency_id not in self.item_text:
            raise ValueError("a slot outside the supplied areas must name its trace competency")
        if self.publication_status != "blocked" or self.draft_item is not True:
            raise ValueError("a medium-confidence sentence is not an approved question")
        return self


class SinhalaDraftItemSlot(FrozenModel):
    node_id: str
    parent_area_id: str
    confidence: Literal["high"]
    draft_item: Literal[True]
    publication_status: Literal["blocked"]
    area_match: bool
    item_text: str

    @model_validator(mode="after")
    def keep_the_traced_sentence(self) -> SinhalaDraftItemSlot:
        if not SINHALA_OUTCOME_ID_PATTERN.fullmatch(self.node_id):
            raise ValueError("Sinhala draft item node id is not a learning-outcome id")
        if not self.parent_area_id.startswith("G5-AREA-SIN-"):
            raise ValueError("Sinhala draft item requires a Sinhala area")
        if self.parent_area_id in BLOCKED_AREA_IDS:
            raise ValueError("Sinhala draft items cannot use a blocked area")
        if self.item_text == "":
            raise ValueError("Sinhala draft item must keep the traced sentence")
        if self.publication_status != "blocked" or self.draft_item is not True:
            raise ValueError("a high-confidence sentence is not an approved question")
        return self


class HeldOutcomeSlot(FrozenModel):
    node_id: str
    parent_area_id: str
    confidence: Literal["low"]
    held: Literal[True]
    draft_item: Literal[False]
    publication_status: Literal["blocked"]
    traced_text: str
    child_question: None

    @model_validator(mode="after")
    def store_the_trace_without_a_question(self) -> HeldOutcomeSlot:
        if self.child_question is not None:
            raise ValueError("a held slot does not create a child question")
        if self.traced_text == "":
            raise ValueError("a held slot stores the traced string")
        if self.parent_area_id in BLOCKED_AREA_IDS:
            raise ValueError("held slots cannot use a blocked area")
        sinhala = SINHALA_OUTCOME_ID_PATTERN.fullmatch(self.node_id)
        environmental = ENVIRONMENTAL_OUTCOME_ID_PATTERN.fullmatch(self.node_id)
        if sinhala and self.parent_area_id.startswith("G5-AREA-SIN-"):
            return self
        if environmental and self.parent_area_id.startswith("G5-AREA-ENV-"):
            return self
        raise ValueError("held slots are Sinhala or Environmental Studies outcomes")


class DraftMissionRecord(FrozenModel):
    area_id: str
    cited_node_id: str
    template_id: DraftTemplateId
    development_only: Literal[True]
    publication_status: Literal["blocked"]
    outcome_slots: tuple[MathematicsOutcomeSlot, ...] = ()
    draft_item_slots: tuple[SinhalaDraftItemSlot, ...] = ()
    held_slots: tuple[HeldOutcomeSlot, ...] = ()

    @model_validator(mode="after")
    def require_area_key_and_cited_node(self) -> DraftMissionRecord:
        if not AREA_ID_PATTERN.fullmatch(self.area_id):
            raise ValueError("mission key must be a G5-AREA id")
        if self.area_id in BLOCKED_AREA_IDS:
            raise ValueError(f"{self.area_id} is blocked and has no draft mission")
        if not NODE_ID_PATTERN.fullmatch(self.cited_node_id):
            raise ValueError("cited node id must be the curriculum node on the coverage row")
        if (
            self.area_id == EXISTING_HALF_SET_SKILL_ID
            or self.cited_node_id == EXISTING_HALF_SET_SKILL_ID
        ):
            raise ValueError("the existing half-set skill is not rebuilt as a draft mission")
        if self.template_id != assigned_template(self.area_id):
            raise ValueError(f"{self.area_id} must use template {assigned_template(self.area_id)}")
        if self.area_id.startswith("G5-AREA-MAT-"):
            if self.draft_item_slots or self.held_slots:
                raise ValueError("mathematics missions do not carry Sinhala or environmental slots")
            for slot in self.outcome_slots:
                if slot.parent_area_id != self.area_id:
                    raise ValueError(f"{slot.node_id} is filed on the wrong mathematics mission")
                matched = slot.trace_competency_id == self.cited_node_id
                if slot.supplied_area_match != matched:
                    raise ValueError(f"{slot.node_id} misstates whether its competency is this area")
            return self
        if self.outcome_slots:
            raise ValueError("only mathematics missions carry mathematics outcome slots")
        if self.area_id.startswith("G5-AREA-SIN-"):
            for slot in (*self.draft_item_slots, *self.held_slots):
                if slot.parent_area_id != self.area_id:
                    raise ValueError(f"{slot.node_id} is filed on the wrong Sinhala mission")
            for slot in self.draft_item_slots:
                if slot.area_match != (slot.node_id == self.cited_node_id):
                    raise ValueError(f"{slot.node_id} misstates whether it is this area's cited node")
            return self
        if self.draft_item_slots:
            raise ValueError("only Sinhala missions carry high-confidence draft items")
        for slot in self.held_slots:
            if slot.parent_area_id != self.area_id:
                raise ValueError(f"{slot.node_id} is filed on the wrong environmental mission")
        return self


class DraftMissionCatalog(FrozenModel):
    package_version: Literal["grade5-draft-mission-catalog-v1"]
    development_only: Literal[True]
    publication_status: Literal["blocked"]
    missions: tuple[DraftMissionRecord, ...] = Field(
        min_length=MISSION_COUNT, max_length=MISSION_COUNT
    )

    @model_validator(mode="after")
    def require_mapped_areas_only(self) -> DraftMissionCatalog:
        area_ids = tuple(mission.area_id for mission in self.missions)
        if len(set(area_ids)) != MISSION_COUNT:
            raise ValueError("draft missions must be keyed by distinct area ids")
        if area_ids != mapped_area_ids():
            raise ValueError(
                "draft missions must list mathematics, buildable Sinhala, then environmental studies"
            )
        if BLOCKED_AREA_IDS.intersection(area_ids):
            raise ValueError("blocked areas must be absent")
        mathematics_slots = [
            slot
            for mission in self.missions
            if mission.area_id.startswith("G5-AREA-MAT-")
            for slot in mission.outcome_slots
        ]
        node_ids = [slot.node_id for slot in mathematics_slots]
        if len(mathematics_slots) != MATHEMATICS_OUTCOME_SLOT_COUNT or len(set(node_ids)) != len(
            node_ids
        ):
            raise ValueError("mathematics missions must carry 65 distinct outcome slots")
        if any(
            slot.publication_status != "blocked" or slot.draft_item is not True
            for slot in mathematics_slots
        ):
            raise ValueError("mathematics outcome slots stay draft and blocked")
        draft_items = [slot for mission in self.missions for slot in mission.draft_item_slots]
        held_slots = [slot for mission in self.missions for slot in mission.held_slots]
        sinhala_held = [slot for slot in held_slots if slot.node_id.startswith("G5-SIN-")]
        environmental_held = [slot for slot in held_slots if slot.node_id.startswith("G5-ENV-")]
        draft_ids = [slot.node_id for slot in draft_items]
        sinhala_held_ids = [slot.node_id for slot in sinhala_held]
        environmental_ids = [slot.node_id for slot in environmental_held]
        if len(draft_items) != SINHALA_DRAFT_ITEM_COUNT or len(set(draft_ids)) != len(draft_ids):
            raise ValueError("Sinhala missions must carry 8 distinct high-confidence draft items")
        if len(sinhala_held) != SINHALA_HELD_SLOT_COUNT or len(set(sinhala_held_ids)) != len(
            sinhala_held_ids
        ):
            raise ValueError("Sinhala missions must carry 76 distinct held slots")
        if len(environmental_held) != ENVIRONMENTAL_HELD_SLOT_COUNT or len(
            set(environmental_ids)
        ) != len(environmental_ids):
            raise ValueError("environmental missions must carry 117 distinct held slots")
        if set(draft_ids).intersection(sinhala_held_ids):
            raise ValueError("a Sinhala outcome cannot be both a draft item and a held slot")
        if any(slot.child_question is not None for slot in held_slots):
            raise ValueError("held slots do not create a child question")
        return self

    def mission(self, area_id: str) -> DraftMissionRecord:
        for mission in self.missions:
            if mission.area_id == area_id:
                return mission
        raise KeyError(area_id)


def load_draft_mission_catalog(
    path: Path = DRAFT_MISSION_CATALOG_DIRECTORY,
) -> DraftMissionCatalog:
    _verify_manifest(path)
    payload = json.loads((path / "missions.json").read_text(encoding="utf-8"))
    return DraftMissionCatalog.model_validate(payload)


def _verify_manifest(path: Path) -> None:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("invalid draft mission manifest")
    if manifest.get("package_version") != PACKAGE_VERSION:
        raise ValueError("invalid draft mission manifest")
    if (
        manifest.get("development_only") is not True
        or manifest.get("publication_status") != "blocked"
    ):
        raise ValueError("draft mission manifest must stay development-only and blocked")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {"missions.json"}:
        raise ValueError("draft mission manifest must pin missions.json")
    data = (path / "missions.json").read_bytes()
    if hashlib.sha256(data).hexdigest() != files["missions.json"]:
        raise ValueError("missions.json does not match the immutable manifest")
