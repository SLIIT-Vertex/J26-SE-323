from app.gamification.domain.types import EvidenceSupportState
from app.gamification.modeling.independence_gain.contracts import IndependenceGainInput


def invalid_reason_codes(data: IndependenceGainInput) -> tuple[str, ...]:
    """Return stable protocol failures without calculating or hiding a raw outcome."""

    reasons: list[str] = []
    if data.baseline_support_state is not EvidenceSupportState.UNSUPPORTED:
        reasons.append("BASELINE_NOT_UNSUPPORTED")
    if data.verification_support_state is not EvidenceSupportState.UNSUPPORTED:
        reasons.append("VERIFICATION_NOT_UNSUPPORTED")
    checks = {
        "PAIR_NOT_APPROVED": data.equivalence.approved,
        "PRIMARY_SKILL_MISMATCH": data.equivalence.primary_skill_match,
        "COGNITIVE_OPERATION_MISMATCH": data.equivalence.cognitive_operation_match,
        "DIFFICULTY_BAND_MISMATCH": data.equivalence.difficulty_band_match,
        "RESPONSE_FORMAT_MISMATCH": data.equivalence.response_format_match,
        "LANGUAGE_NOT_REVIEWED": data.equivalence.language_reviewed,
        "EXPECTED_TIME_MISMATCH": data.equivalence.expected_time_match,
        "VERIFICATION_ITEM_PREVIOUSLY_SEEN": data.equivalence.unseen_verification_item,
        "ANSWER_CLUE_OVERLAP": data.equivalence.answer_overlap_acceptable,
    }
    reasons.extend(reason for reason, passed in checks.items() if not passed)
    if not data.support_delivered:
        reasons.append("SUPPORT_NOT_DELIVERED")
    if not data.support_completed:
        reasons.append("SUPPORT_NOT_COMPLETED")
    if data.support_withdrawn_at is None:
        reasons.append("SUPPORT_NOT_WITHDRAWN")
    elif data.support_withdrawn_at > data.verification_started_at:
        reasons.append("SUPPORT_VISIBLE_DURING_VERIFICATION")
    if data.idle_time_ms > data.maximum_idle_time_ms:
        reasons.append("IDLE_THRESHOLD_EXCEEDED")
    if not data.ordering_valid:
        reasons.append("CLIENT_ORDERING_CORRUPT")
    if data.intervening_support:
        reasons.append("INTERVENING_SUPPORT")
    return tuple(reasons)
