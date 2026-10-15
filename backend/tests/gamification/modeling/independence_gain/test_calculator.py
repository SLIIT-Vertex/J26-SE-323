from dataclasses import replace

from app.gamification.domain.types import EvidenceSupportState
from app.gamification.modeling.independence_gain import calculate_independence_gain
from tests.gamification.modeling.fixtures import equivalence_evidence, gain_input


def test_calculator_preserves_formula_and_invalid_reasons() -> None:
    valid = calculate_independence_gain(gain_input())
    assert valid.raw_gain == 0.5
    assert not valid.invalid_reasons
    invalid = calculate_independence_gain(
        gain_input(
            verification_support_state=EvidenceSupportState.SUPPORTED,
            equivalence=replace(equivalence_evidence(), unseen_verification_item=False),
            intervening_support=True,
        )
    )
    assert invalid.raw_gain is None
    assert set(invalid.invalid_reasons) == {
        "VERIFICATION_NOT_UNSUPPORTED",
        "VERIFICATION_ITEM_PREVIOUSLY_SEEN",
        "INTERVENING_SUPPORT",
    }
