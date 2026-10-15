"""Runtime guards for one scaffold and the unsupported verification that follows it."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from app.gamification.application.errors import EpisodeFlowError
from app.gamification.content.records import (
    ContentAsset,
    ContentStatus,
    ItemDefinition,
    ScaffoldDefinition,
)
from app.gamification.domain.episode import AdaptiveEpisode
from app.gamification.domain.types import EpisodePhase

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_COMPLETED = frozenset({"completed", "completed_over_budget"})


@dataclass(frozen=True, slots=True)
class ExposureBudget:
    maximum_duration_ms: int
    maximum_number_of_steps: int


class ScaffoldController:
    def __init__(self, *, allow_draft: bool) -> None:
        self.allow_draft = allow_draft

    def assert_no_active_scaffold(self, exposure_count: int) -> None:
        if exposure_count:
            raise EpisodeFlowError("SCAFFOLD_ALREADY_ACTIVE")

    def accept_for_delivery(self, scaffold: ScaffoldDefinition, *, selected_action_id: str) -> None:
        if scaffold.scaffold_id != selected_action_id:
            raise EpisodeFlowError("SCAFFOLD_NOT_SELECTED")
        if scaffold.status is ContentStatus.APPROVED:
            return
        if self.allow_draft and scaffold.status is ContentStatus.DRAFT:
            return
        raise EpisodeFlowError("CONTENT_NOT_APPROVED")

    def leakage_failures(
        self,
        scaffold: ScaffoldDefinition,
        asset: ContentAsset,
        item: ItemDefinition,
    ) -> tuple[str, ...]:
        correct = _correct_text(item)
        asset_text = "\n".join((*asset.body_si, *asset.body_en))
        failures: list[str] = []
        rules = set(scaffold.answer_leakage_rules)
        if "different_values_required" in rules and _values_overlap(asset_text, correct):
            failures.append("different_values_required")
        if "no_final_answer" in rules and _contains_final_answer(asset_text, correct):
            failures.append("no_final_answer")
        return tuple(failures)

    def budget_for(self, scaffold: ScaffoldDefinition) -> ExposureBudget:
        return ExposureBudget(
            maximum_duration_ms=scaffold.maximum_duration_ms,
            maximum_number_of_steps=scaffold.maximum_number_of_steps,
        )

    def completion_status(
        self, budget: ExposureBudget, *, duration_ms: int, step_count: int
    ) -> str:
        over_budget = (
            duration_ms > budget.maximum_duration_ms or step_count > budget.maximum_number_of_steps
        )
        return "completed_over_budget" if over_budget else "completed"

    def deliver(self, episode: AdaptiveEpisode, *, at: datetime) -> AdaptiveEpisode:
        return episode.transition_to(EpisodePhase.SUPPORT_ACTIVE, at=at)

    def withdraw(self, episode: AdaptiveEpisode, *, at: datetime) -> AdaptiveEpisode:
        completed = episode.transition_to(EpisodePhase.SUPPORTED_PRACTICE_COMPLETE, at=at)
        return completed.transition_to(EpisodePhase.SUPPORT_WITHDRAWN, at=at)

    def assert_withdrawn(self, withdrawn_at: datetime | None) -> None:
        if withdrawn_at is None:
            raise EpisodeFlowError("SUPPORT_NOT_WITHDRAWN")

    def schedule(self, episode: AdaptiveEpisode, *, at: datetime) -> AdaptiveEpisode:
        return episode.transition_to(EpisodePhase.INDEPENDENT_CHECK_ACTIVE, at=at)

    def choose_verification_item(
        self,
        items: tuple[ItemDefinition, ...],
        *,
        baseline_item_id: str,
        seen_item_ids: Collection[str],
        required_template: str,
    ) -> ItemDefinition:
        blocked = set(seen_item_ids) | {baseline_item_id}
        for item in items:
            if item.item_id in blocked:
                continue
            if required_template not in item.compatible_templates:
                continue
            return item
        raise EpisodeFlowError("VERIFICATION_PAIR_UNAVAILABLE")


def answer_overlap(baseline: ItemDefinition, verification: ItemDefinition) -> float:
    """1 when the correct answers share a number or the same answer text, otherwise 0."""

    left = _answer_tokens(baseline)
    right = _answer_tokens(verification)
    if left and right and left & right:
        return 1.0
    return 0.0


def exposure_counts_as_completed(delivery_status: str) -> bool:
    return delivery_status in _COMPLETED


def _correct_text(item: ItemDefinition) -> str:
    if item.correct_option_id is None:
        return ""
    return item.option(item.correct_option_id).text.strip()


def _answer_tokens(item: ItemDefinition) -> set[str]:
    text = _correct_text(item)
    tokens = set(_NUMBER.findall(text))
    if text:
        tokens.add(text)
    return tokens


def _values_overlap(asset_text: str, correct: str) -> bool:
    if not correct:
        return False
    asset_numbers = set(_NUMBER.findall(asset_text))
    answer_numbers = set(_NUMBER.findall(correct))
    if answer_numbers and answer_numbers & asset_numbers:
        return True
    return not correct.isdigit() and correct in asset_text


def _contains_final_answer(asset_text: str, correct: str) -> bool:
    if not correct:
        return False
    if correct.isdigit():
        return correct in set(_NUMBER.findall(asset_text))
    return correct in asset_text
