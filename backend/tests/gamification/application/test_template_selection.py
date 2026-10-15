from dataclasses import replace

import pytest

from app.gamification.application.errors import EpisodeFlowError
from app.gamification.application.template_selection import (
    TemplateCompatibilityTable,
    require_same_template,
    select_template,
)
from app.gamification.content.loader import load_pilot_content_package
from app.gamification.content.records import TemplateRule


def test_device_fallback_uses_the_first_compatible_alternative_and_ignores_the_seed() -> None:
    package = load_pilot_content_package(allow_draft=True)
    item = replace(
        package.items["G5-MAT-FRC-I010"],
        compatible_templates=("choice_quest", "sort_and_group"),
    )
    table = TemplateCompatibilityTable(
        (
            TemplateRule(
                item_type=item.item_type,
                compatible_templates=("choice_quest", "sort_and_group"),
                response_formats=(item.response_format,),
                table_version="test-templates-v1",
            ),
        ),
        table_version="test-templates-v1",
    )

    default = select_template(item, frozenset({"choice_quest"}), 1, table=table)
    fallback_a = select_template(item, frozenset({"sort_and_group"}), 1, table=table)
    fallback_b = select_template(item, frozenset({"sort_and_group"}), 99, table=table)

    assert default.template_key == "choice_quest"
    assert default.reason_code == "DEFAULT_TEMPLATE"
    assert fallback_a.template_key == fallback_b.template_key == "sort_and_group"
    assert fallback_a.reason_code == "DEVICE_FALLBACK"
    assert fallback_a.variation_seed == 1
    assert fallback_b.variation_seed == 99


def test_baseline_and_verification_must_share_a_template() -> None:
    package = load_pilot_content_package(allow_draft=True)
    item = package.items["G5-MAT-FRC-I010"]

    assert require_same_template(item.default_template, item) == "choice_quest"
    with pytest.raises(EpisodeFlowError, match="TEMPLATE_MISMATCH"):
        require_same_template("sort_and_group", item)
