"""Number World profile on the shared area engine (:mod:`application.engine.area_flow`).

Every area game lives in ``application/<slug>_flow.py`` as a small profile class like this one.
``NumberWorldFlowError`` and ``evidence_difficulty`` stay importable here for existing callers.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import (
    PROTOCOL_VERSION,
    AreaFlowError,
    AreaGameFlow,
    evidence_difficulty,
)
from app.gamification.content.number_world import (
    AREA_ID,
    CATALOGUE_VERSION,
    EQUIVALENCE_VERSION,
    FEATURE_VERSION,
    MAPPING_VERSION,
    MODEL_VERSION,
    PACKAGE_VERSION,
    POLICY_VERSION,
    SCORING_VERSION,
    SKILLS,
    UNIVERSAL_SKILL_ID,
    NumberWorldItem,
    construct_extreme,
    expanded_form,
    generate_item,
    generate_simpler_item,
    infer_belief,
    order_numbers,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
)

CONTRACT_VERSION = "number-world-learning-flow-v1"

# Older name of the engine's error, kept for existing imports.
NumberWorldFlowError = AreaFlowError

__all__ = [
    "CONTRACT_VERSION",
    "PROTOCOL_VERSION",
    "NumberWorldFlow",
    "NumberWorldFlowError",
    "evidence_difficulty",
    "is_number_world_state",
]


class NumberWorldFlow(AreaGameFlow):
    """Number World (G5-AREA-MAT-01): place value, abacus, expanded form, ordering."""

    area_id = AREA_ID
    experience_id = "number_world"
    universal_skill_id = UNIVERSAL_SKILL_ID
    contract_version = CONTRACT_VERSION
    context_version = "g5-mat-number-world-context-v1"
    measurement_version = "number-world-independence-measurement-v1"
    item_schema_version = "number-world-item-v1"
    support_schema_version = "number-world-support-v1"
    package_version = PACKAGE_VERSION
    catalogue_version = CATALOGUE_VERSION
    feature_version = FEATURE_VERSION
    mapping_version = MAPPING_VERSION
    model_version = MODEL_VERSION
    policy_version = POLICY_VERSION
    scoring_version = SCORING_VERSION
    equivalence_version = EQUIVALENCE_VERSION
    skills = SKILLS
    generate_item = staticmethod(generate_item)
    generate_simpler_item = staticmethod(generate_simpler_item)
    infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision)
    package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "NUMBER_WORLD_SKILL_NOT_FOUND"
    episode_type_error = "NUMBER_WORLD_EPISODE_REQUIRED"
    operation_prefix = "number_world"

    @staticmethod
    def _public_game_data(item: NumberWorldItem) -> dict[str, object]:
        """Expose only task givens; scoring targets remain server-side."""

        game = item.game_data
        public: dict[str, object] = {"chapter": item.chapter}
        if item.skill_id.endswith(("POSITION-01", "REPRESENTED-01")):
            public.update(number=game["number"], digit=game["digit"])
        elif item.skill_id.endswith("100000-01"):
            # The givens of the milestone ladder: the number one below the milestone and the
            # choices. Both are already in the prompt and the options.
            public.update(
                milestone=True,
                milestone_base=int(game["number"]) - 1,
                milestone_choices=list(game["milestone_choices"]),
            )
        elif item.skill_id.endswith(("ABACUS-01", "EXPAND-01")):
            public["number"] = game["number"]
        elif item.skill_id.endswith(("EXTREME-01", "LEADING-ZERO-01")):
            public.update(digits=game["digits"], greatest=game["greatest"])
        else:
            public.update(values=game["values"], ascending=game["ascending"])
        return public

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        """Build an answer-bearing demonstration for the exact failed item."""

        skill_id = str(item["skill_id"])
        game = dict(item["game_data"])  # type: ignore[arg-type]
        if skill_id.endswith("POSITION-01"):
            response: dict[str, object] = {
                "kind": "drag_to_slot",
                "selected_place": int(game["place"]),
            }
            steps = (
                "අසන ඉලක්කම සංඛ්‍යාවේ සොයා ගනිමු.",
                "දකුණෙන් එකක තැන සිට එහි ස්ථානය ගණන් කරමු.",
                "ඉලක්කම තිබෙන නිවැරදි ස්ථානය පෙන්වමු.",
            )
        elif skill_id.endswith("REPRESENTED-01"):
            represented = int(game["digit"]) * 10 ** int(game["place"])
            response = {"kind": "drag_to_slot", "represented_value": represented}
            steps = (
                "අසන ඉලක්කම සංඛ්‍යාවේ සොයා ගනිමු.",
                "එය තිබෙන ස්ථානයේ අගය බලමු.",
                "ඉලක්කම × ස්ථානීය අගය ගණනය කරමු.",
            )
        elif skill_id.endswith("100000-01"):
            response = {"kind": "constructed_number", "constructed_number": int(game["number"])}
            target = int(game["number"])
            spaced = f"{target - 1:,}".replace(",", " ")
            steps = (
                f"{spaced} හි එකක තැනට එකක් එකතු කරමු.",
                "සෑම 9ක්ම 0 වී ඊළඟ තැනට එකක් ගෙන යමු.",
                f"එවිට {target:,} ලැබේ.".replace(",", " "),
            )
        elif skill_id.endswith("ABACUS-01"):
            rods = [int(value) for value in game["rods"]]  # type: ignore[union-attr]
            response = {"kind": "bead_placement", "rods": rods}
            steps = (
                "දඬු හයේ ස්ථාන වම් සිට දකුණට හඳුනා ගනිමු.",
                "සෑම ඉලක්කමකටම එම දඬුවේ පබළු තබමු.",
                "පබළු ගණන් කර සම්පූර්ණ සංඛ්‍යාව නැවත බලමු.",
            )
        elif skill_id.endswith("EXPAND-01"):
            terms = [int(part) for part in expanded_form(int(game["number"])).split(" + ")]
            response = {"kind": "expanded_form", "terms": terms}
            steps = (
                "සංඛ්‍යාවේ ඉලක්කම් ස්ථාන වගුවේ තබමු.",
                "සෑම ඉලක්කමක්ම එහි ස්ථානීය අගයෙන් විහිදුවමු.",
                "ශූන්‍ය ස්ථාන හැර විහිදුණු එකතුව පරීක්ෂා කරමු.",
            )
        elif skill_id.endswith(("EXTREME-01", "LEADING-ZERO-01")):
            supplied = tuple(int(value) for value in game["digits"])  # type: ignore[union-attr]
            result = construct_extreme(supplied, greatest=bool(game["greatest"]))
            digits = [int(value) for value in str(result)]
            response = {"kind": "digit_order", "digits": digits}
            steps = (
                "දී ඇති ඉලක්කම් සියල්ල හඳුනා ගනිමු.",
                "අවශ්‍ය දිශාවට ඉලක්කම් එකින් එක සකස් කරමු.",
                "මුලට 0 නොතබා සම්පූර්ණ සංඛ්‍යාව පරීක්ෂා කරමු.",
            )
        else:
            supplied_values = tuple(int(value) for value in game["values"])  # type: ignore[union-attr]
            ordered = list(order_numbers(supplied_values, ascending=bool(game["ascending"])))
            response = {"kind": "number_order", "order": ordered}
            steps = (
                "සංඛ්‍යාවල වම්පස ඉලක්කම් මුලින් සසඳමු.",
                "අවශ්‍ය දිශාවට ඊළඟ සංඛ්‍යාව තෝරමු.",
                "සියලු සංඛ්‍යා යොදා ඇතිදැයි මාර්ගය පරීක්ෂා කරමු.",
            )
        if scaffold_type == "visual_guidance":
            steps = (
                "අදාළ නිරූපණය හොඳින් බලමු.",
                "වෙනස් වන ස්ථානය හෝ ඉලක්කම ඉස්මතු කර බලමු.",
                "උදව් නැතිව එම ක්‍රියාව ඔබම කරන්න.",
            )
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {
                "schema_version": "number-world-item-v1",
                "skill_id": skill_id,
                **game,
            },
            "correct_response": response,
            "steps_si": list(steps),
        }


def is_number_world_state(state: Mapping[str, object]) -> bool:
    return state.get("experience_id") == "number_world"
