"""Research-consent gate shared by the policy update and outbound learner evidence."""

from datetime import datetime
from uuid import UUID

from app.gamification.application.ports import ConsentStore

RESEARCH_CONSENT_PURPOSE = "research"


def research_consent_granted(store: ConsentStore, learner_id: UUID, at: datetime) -> bool:
    """Missing, denied, and expired decisions are all out of scope.

    ``ConsentStore.get_consent`` raises ``LookupError`` when no decision exists.
    That is missing consent, not an episode failure.
    """

    try:
        decision = store.get_consent(learner_id=learner_id, purpose=RESEARCH_CONSENT_PURPOSE)
    except LookupError:
        return False
    if not decision.granted:
        return False
    return decision.expires_at is None or decision.expires_at > at
