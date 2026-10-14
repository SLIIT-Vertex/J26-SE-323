"""Device-aware template choice. The seed is recorded and does not change the choice."""

import logging
from collections.abc import Collection
from dataclasses import dataclass

from app.gamification.application.errors import EpisodeFlowError
from app.gamification.content.records import ItemDefinition, PilotContentPackage, TemplateRule

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TemplateSelection:
    template_key: str
    reason_code: str
    variation_seed: int
    table_version: str


class TemplateCompatibilityTable:
    def __init__(self, rules: tuple[TemplateRule, ...], *, table_version: str) -> None:
        self.table_version = table_version
        self._rules = {rule.item_type: rule for rule in rules}

    @classmethod
    def from_package(cls, package: PilotContentPackage) -> "TemplateCompatibilityTable":
        return cls(
            tuple(package.template_rules.values()),
            table_version=str(package.versions["template_table_version"]),
        )

    def select_template(
        self,
        item: ItemDefinition,
        device_capabilities: Collection[str],
        variation_seed: int,
    ) -> TemplateSelection:
        return select_template(item, device_capabilities, variation_seed, table=self)


def select_template(
    item: ItemDefinition,
    device_capabilities: Collection[str],
    variation_seed: int,
    *,
    table: TemplateCompatibilityTable,
) -> TemplateSelection:
    """Return the default template, or the first device-compatible alternative."""

    supported_by_device = set(device_capabilities)
    allowed = [
        name
        for name in item.compatible_templates
        if _table_allows(table, item.item_type, name) and name in supported_by_device
    ]
    if item.default_template in allowed:
        chosen = item.default_template
        reason = "DEFAULT_TEMPLATE"
    elif allowed:
        chosen = allowed[0]
        reason = "DEVICE_FALLBACK"
    else:
        raise EpisodeFlowError("TEMPLATE_UNAVAILABLE")
    logger.info(
        "template %s selected for %s (%s, seed %s)",
        chosen,
        item.item_id,
        reason,
        variation_seed,
    )
    return TemplateSelection(
        template_key=chosen,
        reason_code=reason,
        variation_seed=variation_seed,
        table_version=table.table_version,
    )


def require_same_template(baseline_template: str, verification_item: ItemDefinition) -> str:
    """Baseline and verification in one episode share a template so it cannot explain gain."""

    if baseline_template not in verification_item.compatible_templates:
        raise EpisodeFlowError("TEMPLATE_MISMATCH")
    return baseline_template


def _table_allows(table: TemplateCompatibilityTable, item_type: str, template_key: str) -> bool:
    rule = table._rules.get(item_type)
    if rule is None:
        return True
    return template_key in rule.compatible_templates
