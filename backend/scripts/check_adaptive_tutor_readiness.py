"""Read-only AT-24 readiness checks. No external provider call is made."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adaptive_tutor.infrastructure.embeddings import SentenceTransformerE5EmbeddingModel
from app.adaptive_tutor.infrastructure.gemini import GeminiGenerationConfig
from app.adaptive_tutor.infrastructure.local_research import (
    EXPERIMENTAL_CURRICULUM_PATH,
    build_local_research_tutor_service,
    configured_research_trusted_answer,
)
from app.adaptive_tutor.infrastructure.semantic_verifier import (
    SemanticVerifierProviderConfig,
)
from app.config import Settings, get_settings
from app.curriculum.application import CurriculumRetrievalRequest
from app.curriculum.infrastructure.embeddings import E5_MODEL_NAME, E5_MODEL_REVISION
from app.curriculum.infrastructure.models import CurriculumChunkEmbeddingModel
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.shared.learner.repository import SqlAlchemyLearnerRepository


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ready: bool
    reason: str


def _check(name: str, action: Callable[[], object]) -> Check:
    try:
        reason = action()
        return Check(name, True, str(reason))
    except ValueError as error:
        return Check(name, False, str(error))
    except Exception as error:  # noqa: BLE001 - every prerequisite becomes a safe report row
        return Check(name, False, f"{type(error).__name__}; prerequisite check failed")


def _migrations(engine: object) -> str:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:  # type: ignore[attr-defined]
        current = set(MigrationContext.configure(connection).get_current_heads())
    if current != expected:
        raise ValueError(
            "database heads do not match repository heads; run `alembic upgrade heads`"
        )
    return f"all {len(expected)} migration heads are applied"


def _authorization(settings: Settings) -> str:
    if settings.tutor_api_mode != "research-local":
        raise ValueError("TUTOR_API_MODE must be research-local")
    if not settings.tutor_research_composition_enabled:
        raise ValueError("TUTOR_RESEARCH_COMPOSITION_ENABLED must be true")
    if not settings.tutor_research_access_key.strip():
        raise ValueError("TUTOR_RESEARCH_ACCESS_KEY is required")
    try:
        UUID(settings.tutor_researcher_id)
    except ValueError as error:
        raise ValueError("TUTOR_RESEARCHER_ID must be a UUID") from error
    return "local composition, access key and researcher UUID are configured"


def _e5() -> str:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    try:
        vectors = SentenceTransformerE5EmbeddingModel(local_files_only=True).embed_queries(
            ("fractions readiness check",)
        )
    except Exception as error:
        raise ValueError(f"pinned E5 model unavailable ({type(error).__name__})") from error
    if len(vectors) != 1 or not vectors[0]:
        raise ValueError("cached E5 model returned no embedding")
    return "pinned E5 model is available from the local cache"


def _gemini(settings: Settings) -> str:
    config = GeminiGenerationConfig.from_settings(settings)
    if settings.tutor_llm_provider.strip().casefold() != "gemini":
        raise ValueError("TUTOR_LLM_PROVIDER must be gemini")
    if not config.api_key or not config.model:
        raise ValueError("Gemini API key and pinned model are required")
    if not settings.tutor_research_gemini_authorized:
        raise ValueError("Gemini is not authorized for adult research")
    return "Gemini credentials, pinned model, controls and research authorization are configured"


def _verifier(settings: Settings) -> str:
    if settings.tutor_pp1_experimental_demo_enabled:
        return "not used; PP1 drafts remain explicitly unverified"
    if not settings.tutor_semantic_verifier_enabled:
        raise ValueError("semantic verifier is disabled")
    config = SemanticVerifierProviderConfig.from_settings(settings)
    if not settings.tutor_semantic_verifier_independent:
        raise ValueError("independent verifier assertion is false")
    if "gemini" in config.provider_name.casefold():
        raise ValueError("verifier provider must be operationally separate from Gemini")
    return "structured verifier credentials, model, version and independence are configured"


def _policies(settings: Settings) -> str:
    policies = {
        value.strip()
        for value in settings.tutor_research_severity_policy_versions.split(",")
        if value.strip()
    }
    if not policies:
        raise ValueError("TUTOR_RESEARCH_SEVERITY_POLICY_VERSIONS is required")
    return f"{len(policies)} controlled reviewer policy version(s) configured"


def _trusted_answer(settings: Settings) -> str:
    if settings.tutor_pp1_experimental_demo_enabled:
        return "not used; PP1 drafts cannot enter the verified response field"
    configured_research_trusted_answer(settings)
    return "exact MAT-FRC question, accepted answers, and provenance are configured"


def run_checks(
    settings: Settings,
    *,
    learner_id: UUID | None,
    session_id: UUID | None,
    language: str,
    max_age_ms: int,
    now: datetime | None = None,
) -> tuple[Check, ...]:
    current = now or datetime.now(UTC)
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    checks: list[Check] = []

    def postgres() -> str:
        if engine.dialect.name != "postgresql":
            raise ValueError(f"PostgreSQL required; configured dialect is {engine.dialect.name}")
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:
            raise ValueError(
                f"PostgreSQL connection failed ({type(error).__name__}); check DATABASE_URL and start it"
            ) from error
        return "PostgreSQL connection succeeded"

    def migrations() -> str:
        try:
            return _migrations(engine)
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(
                f"migration heads could not be read ({type(error).__name__}); PostgreSQL must be available"
            ) from error

    checks.append(_check("POSTGRESQL", postgres))
    checks.append(_check("MIGRATIONS", migrations))
    checks.append(_check("RESEARCH_AUTHORIZATION", lambda: _authorization(settings)))
    checks.append(_check("E5_MODEL", _e5))
    checks.append(_check("GEMINI", lambda: _gemini(settings)))
    checks.append(_check("INDEPENDENT_VERIFIER", lambda: _verifier(settings)))
    checks.append(_check("CONTROLLED_SEVERITY_POLICY", lambda: _policies(settings)))
    checks.append(_check("TRUSTED_ANSWER", lambda: _trusted_answer(settings)))

    with Session(engine) as session:
        learner = None

        def learner_check() -> str:
            nonlocal learner
            if learner_id is None:
                raise ValueError("provide --learner-id or AT24_LEARNER_ID")
            learner = SqlAlchemyLearnerRepository(session).get(learner_id)
            if learner is None:
                raise ValueError("learner does not exist")
            return f"learner exists with grade {learner.grade}"

        checks.append(_check("LEARNER", learner_check))

        def mastery_check() -> str:
            if learner_id is None:
                raise ValueError("learner ID is required")
            repository = SqlAlchemyMasteryRepository(session)
            snapshot = repository.latest_snapshot(learner_id)
            if snapshot is None:
                raise ValueError("no persisted KT mastery snapshot exists")
            skill = next((item for item in snapshot.skills if item.code == "MAT-FRC"), None)
            if skill is None or skill.mastery is None:
                raise ValueError("KT mastery for MAT-FRC is not available")
            attempts = repository.count_attempts(learner_id)
            if attempts != snapshot.n_attempts:
                raise ValueError("KT snapshot is behind stored attempts; recompute mastery")
            return "persisted MAT-FRC mastery is available and current"

        checks.append(_check("KT_MASTERY", mastery_check))

        def learner_state_check() -> str:
            if learner_id is None or session_id is None:
                raise ValueError(
                    "provide learner and trusted research session IDs after starting the smoke run"
                )
            state = SqlAlchemyLearnerSkillStateRepository(session).get(learner_id, "MAT-FRC")
            if state is None:
                raise ValueError("no Learner State observation exists for MAT-FRC")
            if state.session_id != str(session_id):
                raise ValueError("latest Learner State observation belongs to another session")
            observed = (
                state.observed_at.astimezone(UTC)
                if state.observed_at.tzinfo
                else state.observed_at.replace(tzinfo=UTC)
            )
            age = current - observed
            if age < timedelta(0):
                raise ValueError("Learner State observation is in the future")
            if age > timedelta(milliseconds=max_age_ms):
                raise ValueError(
                    f"Learner State observation is stale; record it within {max_age_ms} ms"
                )
            if state.support_need is None:
                raise ValueError("Learner State support need is uncertain")
            return "same-session fresh MAT-FRC support need is available"

        checks.append(_check("LEARNER_STATE", learner_state_check))

        def curriculum_check() -> str:
            if settings.tutor_pp1_experimental_demo_enabled:
                content = EXPERIMENTAL_CURRICULUM_PATH.read_text(encoding="utf-8")
                if "UNREVIEWED" not in content:
                    raise ValueError("experimental curriculum lost its UNREVIEWED label")
                return "local UNREVIEWED_EXPERIMENTAL MAT-FRC content is available"
            if learner is None:
                raise ValueError("an existing learner is required to determine grade")
            request = CurriculumRetrievalRequest(
                learner_question="Fractions readiness check",
                skill_id="MAT-FRC",
                grade=learner.grade,
                subject="Mathematics",
                required_language=language,
            )
            chunks = CurriculumVectorIndex(session).approved_chunks(request)
            if not chunks:
                raise ValueError(
                    f"no approved, rights-permitted MAT-FRC chunks for grade {learner.grade}/{language}"
                )
            embedded = set(
                session.scalars(
                    select(CurriculumChunkEmbeddingModel.chunk_id).where(
                        CurriculumChunkEmbeddingModel.chunk_id.in_(
                            [item.chunk.chunk_id for item in chunks]
                        ),
                        CurriculumChunkEmbeddingModel.model_name == E5_MODEL_NAME,
                        CurriculumChunkEmbeddingModel.model_revision == E5_MODEL_REVISION,
                    )
                )
            )
            if not embedded:
                raise ValueError("approved MAT-FRC chunks lack pinned E5 embeddings")
            return f"{len(embedded)} approved MAT-FRC chunk(s) have pinned E5 embeddings"

        checks.append(_check("CURRICULUM_MAT_FRC", curriculum_check))

        checks.append(
            _check(
                "RESEARCH_COMPOSITION",
                lambda: (
                    build_local_research_tutor_service(settings, session)
                    and "real local composition builds without provider calls"
                ),
            )
        )
    engine.dispose()
    return tuple(checks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AT-24 live research prerequisites.")
    parser.add_argument("--learner-id", default=os.environ.get("AT24_LEARNER_ID"))
    parser.add_argument("--session-id", default=os.environ.get("AT24_SESSION_ID"))
    parser.add_argument("--language", default=os.environ.get("AT24_LANGUAGE", "en"))
    parser.add_argument("--max-age-ms", type=int, default=60_000)
    args = parser.parse_args()
    try:
        settings = get_settings()
        learner_id = UUID(args.learner_id) if args.learner_id else None
        session_id = UUID(args.session_id) if args.session_id else None
    except ValidationError as error:
        fields = ", ".join(".".join(map(str, item["loc"])) for item in error.errors())
        print(f"BLOCKED CONFIGURATION: invalid or missing setting(s): {fields}")
        print("READINESS: BLOCKED")
        return 1
    except ValueError:
        print("BLOCKED CONFIGURATION: learner and session IDs must be UUIDs")
        print("READINESS: BLOCKED")
        return 1
    checks = run_checks(
        settings,
        learner_id=learner_id,
        session_id=session_id,
        language=args.language,
        max_age_ms=args.max_age_ms,
    )
    for item in checks:
        print(f"{'READY' if item.ready else 'BLOCKED'} {item.name}: {item.reason}")
    ready = all(item.ready for item in checks)
    print(f"READINESS: {'READY' if ready else 'BLOCKED'}")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
