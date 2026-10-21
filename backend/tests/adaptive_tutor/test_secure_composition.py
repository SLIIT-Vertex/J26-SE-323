from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.adaptive_tutor.application.context_assembly import EvidenceOrigin, EvidenceSource
from app.adaptive_tutor.infrastructure.composition import (
    DenyAllShadowAuthorizer,
    TrustedShadowRequestFactory,
    build_internal_tutor_composition,
)
from app.adaptive_tutor.infrastructure.local_research import (
    build_local_research_tutor_service,
    validate_local_research_settings,
)
from app.adaptive_tutor.infrastructure.shadow_mode import StaticShadowAuthorizer
from app.config import Settings
from app.knowledge_tracing.domain.feature_spec import get_feature_spec


class _UnusedMapper:
    def map(self, request: object) -> object:
        raise AssertionError("deny-by-default composition must not map")


class _UnusedEstimator:
    version = "test"

    def mastery(self, history: object) -> object:
        raise AssertionError("deny-by-default composition must not infer")


def test_shadow_access_denies_by_default() -> None:
    principal_id, learner_id = uuid4(), uuid4()
    authority = TrustedShadowRequestFactory(DenyAllShadowAuthorizer())

    with pytest.raises(PermissionError):
        authority.start(principal_id, learner_id)


def test_live_research_composition_denies_without_explicit_enablement() -> None:
    with (
        Session(create_engine("sqlite://")) as session,
        pytest.raises(ValueError, match="COMPOSITION_ENABLED"),
    ):
        build_local_research_tutor_service(
            Settings(
                _env_file=None,
                database_url="sqlite://",
                tutor_api_mode="research-local",
                tutor_research_access_key="research-key",
                tutor_researcher_id=str(uuid4()),
            ),
            session,
        )


def test_live_research_composition_rejects_gemini_verifier_alias() -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        tutor_api_mode="research-local",
        tutor_research_composition_enabled=True,
        tutor_research_access_key="research-key",
        tutor_researcher_id=str(uuid4()),
        tutor_research_gemini_authorized=True,
        tutor_research_severity_policy_versions="controlled-v1",
        tutor_llm_provider="gemini",
        tutor_semantic_verifier_enabled=True,
        tutor_semantic_verifier_independent=True,
        tutor_semantic_verifier_provider="another-gemini-service",
    )
    with (
        Session(create_engine("sqlite://")) as session,
        pytest.raises(ValueError, match="must differ"),
    ):
        build_local_research_tutor_service(settings, session)


def test_experimental_opt_in_is_explicit_and_does_not_weaken_verified_mode() -> None:
    common = {
        "tutor_api_mode": "research-local",
        "tutor_research_composition_enabled": True,
        "tutor_research_access_key": "research-key",
        "tutor_researcher_id": str(uuid4()),
        "tutor_research_gemini_authorized": True,
        "tutor_research_severity_policy_versions": "controlled-v1",
        "tutor_llm_provider": "gemini",
    }
    with pytest.raises(ValueError, match="independent semantic verifier"):
        validate_local_research_settings(Settings(_env_file=None, **common))

    policies = validate_local_research_settings(
        Settings(_env_file=None, **common, tutor_pp1_experimental_demo_enabled=True)
    )
    assert policies == frozenset({"controlled-v1"})


def test_internal_composition_connects_real_adapters_but_defaults_to_denied() -> None:
    with Session(create_engine("sqlite://")) as session:
        composition = build_internal_tutor_composition(
            session=session,
            skill_mapper=_UnusedMapper(),  # type: ignore[arg-type]
            skill_mapper_source=EvidenceSource(
                source_id="test:real-mapper",
                origin=EvidenceOrigin.REAL,
            ),
            estimator=_UnusedEstimator(),  # type: ignore[arg-type]
            feature_spec=get_feature_spec(),
            valid_skill_ids={"MAT-FRC"},
        )

        with pytest.raises(PermissionError):
            composition.requests.start(uuid4(), uuid4())
        assert "llm" not in vars(composition.shadow)
        assert "semantic_verifier" not in vars(composition.shadow)


def test_shadow_request_identity_time_and_sequence_are_server_owned() -> None:
    principal_id, learner_id = uuid4(), uuid4()
    as_of = datetime(2026, 10, 19, 10, tzinfo=UTC)
    authority = TrustedShadowRequestFactory(
        StaticShadowAuthorizer({(principal_id, learner_id)}),
        lifetime=timedelta(minutes=5),
    )
    session_id = authority.start(principal_id, learner_id, now=as_of)

    first = authority.create_request(
        principal_id=principal_id,
        learner_id=learner_id,
        session_id=session_id,
        student_message="Help with fractions.",
        preferred_language="en",
        max_age_ms=60_000,
        now=as_of,
    )
    second = authority.create_request(
        principal_id=principal_id,
        learner_id=learner_id,
        session_id=session_id,
        student_message="One more hint.",
        preferred_language="en",
        max_age_ms=60_000,
        now=as_of + timedelta(seconds=1),
    )

    assert first.session_id == second.session_id == session_id
    assert (first.interaction_sequence, second.interaction_sequence) == (1, 2)
    assert first.interaction_id != second.interaction_id
    assert first.as_of == as_of


def test_shadow_session_rejects_cross_learner_and_expiry() -> None:
    principal_id, learner_id = uuid4(), uuid4()
    other_learner = uuid4()
    now = datetime(2026, 10, 19, 10, tzinfo=UTC)
    authority = TrustedShadowRequestFactory(
        StaticShadowAuthorizer({(principal_id, learner_id), (principal_id, other_learner)}),
        lifetime=timedelta(seconds=1),
    )
    session_id = authority.start(principal_id, learner_id, now=now)

    with pytest.raises(PermissionError):
        authority.create_request(
            principal_id=principal_id,
            learner_id=other_learner,
            session_id=session_id,
            student_message="Help.",
            preferred_language="en",
            max_age_ms=1,
            now=now,
        )
    with pytest.raises(PermissionError):
        authority.create_request(
            principal_id=principal_id,
            learner_id=learner_id,
            session_id=session_id,
            student_message="Help.",
            preferred_language="en",
            max_age_ms=1,
            now=now + timedelta(seconds=1),
        )
