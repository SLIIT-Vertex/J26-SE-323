"""Read-only view of a pilot package for the episode use cases."""

from app.gamification.content.records import (
    ContentAsset,
    ItemDefinition,
    ParallelGroup,
    PilotContentPackage,
    ScaffoldDefinition,
    TemplateRule,
)
from app.gamification.content.support_candidates import skill_support_candidates
from app.gamification.modeling.support_selection.contracts import SupportCandidate


class PilotContentCatalog:
    def __init__(self, package: PilotContentPackage) -> None:
        self._package = package

    def item(self, item_id: str) -> ItemDefinition:
        try:
            return self._package.items[item_id]
        except KeyError as error:
            raise LookupError(item_id) from error

    def scaffold(self, scaffold_id: str) -> ScaffoldDefinition:
        try:
            return self._package.scaffolds[scaffold_id]
        except KeyError as error:
            raise LookupError(scaffold_id) from error

    def scaffolds_for_skill(self, skill_id: str) -> tuple[ScaffoldDefinition, ...]:
        return self._package.scaffolds_for_skill(skill_id)

    def asset(self, asset_id: str) -> ContentAsset:
        try:
            return self._package.content_assets[asset_id]
        except KeyError as error:
            raise LookupError(asset_id) from error

    def parallel_group(self, group_id: str) -> ParallelGroup:
        try:
            return self._package.parallel_groups[group_id]
        except KeyError as error:
            raise LookupError(group_id) from error

    def items_in_group(self, group_id: str) -> tuple[ItemDefinition, ...]:
        group = self.parallel_group(group_id)
        return tuple(self.item(item_id) for item_id in group.item_ids)

    def support_candidates(self, skill_id: str) -> tuple[SupportCandidate, ...]:
        return skill_support_candidates(self._package, skill_id)

    def template_rules(self) -> tuple[TemplateRule, ...]:
        return tuple(self._package.template_rules.values())

    def misconception_catalogue_version(self) -> str:
        return str(self._package.versions["catalogue_version"])

    def support_catalogue_version(self) -> str:
        return str(self._package.versions["scaffold_version"])

    def equivalence_version(self) -> str:
        return str(self._package.versions["equivalence_version"])

    def template_table_version(self) -> str:
        return str(self._package.versions["template_table_version"])
