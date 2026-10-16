import builtins
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.adaptive_tutor.application import (
    ConversationalSkillMapper,
    SemanticRelevanceGate,
    SemanticSkillRetriever,
    SkillMappingPolicy,
    SkillMappingRequest,
    validate_skill_ids_against_taxonomy,
)
from app.adaptive_tutor.application.skill_mapper import prepare_text
from app.adaptive_tutor.domain import (
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
    SkillNode,
)
from app.adaptive_tutor.infrastructure import (
    JsonSkillRelevanceCatalog,
    JsonSkillTaxonomyEnrichmentCatalog,
    SentenceTransformerE5EmbeddingModel,
    XlsxSkillTaxonomyCatalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class FakeEmbeddingModel:
    """Deterministic vectors test orchestration, not multilingual model quality."""

    def __init__(self) -> None:
        self.query_calls = 0
        self.passage_calls = 0

    def embed_queries(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.query_calls += 1
        return tuple(self._query_vector(text) for text in texts)

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.passage_calls += 1
        return tuple(self._passage_vector(text) for text in texts)

    @staticmethod
    def _query_vector(text: str) -> tuple[float, ...]:
        lowered = text.casefold()
        if "work with these numbers" in lowered:
            return (1.0, 1.0, 0.0)
        if "time" in lowered or "leap year" in lowered:
            return (0.0, 0.0, 1.0)
        if any(term in lowered for term in ("fraction", "fractions", "common denominator")):
            return (1.0, 0.0, 0.0)
        if "divide" in lowered or "operation" in lowered:
            return (0.0, 1.0, 0.0)
        return (0.0, 0.0, 0.0)

    @staticmethod
    def _passage_vector(text: str) -> tuple[float, ...]:
        if "MAT-FRC" in text:
            return (1.0, 0.0, 0.0)
        if "MAT-OPS" in text:
            return (0.0, 1.0, 0.0)
        if "MAT-TIM" in text:
            return (0.0, 0.0, 1.0)
        raise AssertionError(f"unexpected passage: {text}")


@pytest.fixture
def skill_nodes() -> tuple[SkillNode, ...]:
    return (
        SkillNode("MAT", "MAT-FRC", "Fractions & Decimals", "භාග සහ දශම", "Fractions."),
        SkillNode("MAT", "MAT-OPS", "Fundamental Operations", "මූලික කර්ම", "Operations."),
        SkillNode("MAT", "MAT-TIM", "Time & Calendar", "කාලය", "Time and calendars."),
    )


@pytest.fixture
def mapper(
    skill_nodes: tuple[SkillNode, ...],
) -> tuple[ConversationalSkillMapper, FakeEmbeddingModel]:
    embeddings = FakeEmbeddingModel()
    retriever = SemanticSkillRetriever(skill_nodes, embeddings)
    return ConversationalSkillMapper(retriever), embeddings


def test_xlsx_catalog_loads_authoritative_taxonomy() -> None:
    nodes = XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()

    assert len(nodes) == 30
    assert {node.skill_id for node in nodes} >= {"APT-LOG", "MAT-FRC", "LAN-CMP", "ENV-BIO"}
    assert all(node.name and node.description for node in nodes)


def test_semantic_candidates_are_ranked_by_similarity(
    skill_nodes: tuple[SkillNode, ...],
) -> None:
    retriever = SemanticSkillRetriever(skill_nodes, FakeEmbeddingModel())

    ranked = retriever.rank("Please explain fractions")

    assert [candidate.node.skill_id for candidate in ranked] == [
        "MAT-FRC",
        "MAT-OPS",
        "MAT-TIM",
    ]


def test_optional_enrichment_adds_passages_without_changing_skill_identity(
    skill_nodes: tuple[SkillNode, ...],
) -> None:
    retriever = SemanticSkillRetriever(
        skill_nodes,
        FakeEmbeddingModel(),
        {"MAT-FRC": ("MAT-FRC provisional Tamil fraction alias",)},
    )

    ranked = retriever.rank("Please explain fractions")

    assert ranked[0].node.skill_id == "MAT-FRC"
    assert {candidate.node.skill_id for candidate in ranked} == {
        "MAT-FRC",
        "MAT-OPS",
        "MAT-TIM",
    }


def test_enrichment_catalog_validates_membership_and_provenance() -> None:
    nodes = XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    enrichments = JsonSkillTaxonomyEnrichmentCatalog(
        REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-enrichment-v1.json"
    ).load({node.skill_id for node in nodes})

    assert {item.skill_id for item in enrichments} == {
        "ENV-BIO",
        "ENV-HLT",
        "MAT-FRC",
        "MAT-OPS",
        "MAT-TIM",
    }
    assert all(item.provenance and item.review_status for item in enrichments)
    assert all(
        item.review_status == "qualified_review_pending"
        for item in enrichments
        if item.language in {"sinhala", "tamil", "singlish", "tanglish"}
    )


@pytest.mark.parametrize(
    "records, message",
    [
        (
            [{"skill_id": "NOT-REAL", "entries": []}],
            "unknown enrichment skill ID",
        ),
        (
            [
                {
                    "skill_id": "MAT-FRC",
                    "entries": [
                        {
                            "language": "english",
                            "text": "fractions",
                            "provenance": "test",
                            "review_status": "test",
                        }
                    ],
                },
                {
                    "skill_id": "MAT-FRC",
                    "entries": [
                        {
                            "language": "sinhala",
                            "text": "භාග",
                            "provenance": "test",
                            "review_status": "test",
                        }
                    ],
                },
            ],
            "duplicate enrichment record",
        ),
    ],
)
def test_enrichment_catalog_rejects_unknown_and_duplicate_records(
    tmp_path: Path,
    records: list[dict[str, object]],
    message: str,
) -> None:
    path = tmp_path / "enrichment.json"
    path.write_text(json.dumps({"records": records}), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match=message):
        JsonSkillTaxonomyEnrichmentCatalog(path).load({"MAT-FRC"})


def test_clear_semantic_match_returns_taxonomy_skill(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
    skill_nodes: tuple[SkillNode, ...],
) -> None:
    service, _ = mapper

    result = service.map(SkillMappingRequest(learner_message="Explain these fractions"))

    assert result.status is SkillMappingStatus.MATCHED
    assert result.skill_id == "MAT-FRC"
    assert result.confidence == 1.0
    validate_skill_ids_against_taxonomy(result, {node.skill_id for node in skill_nodes})


def test_close_candidates_are_ambiguous(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, _ = mapper

    result = service.map(SkillMappingRequest(learner_message="How do I work with these numbers?"))

    assert result.status is SkillMappingStatus.AMBIGUOUS
    assert [candidate.skill_id for candidate in result.candidate_skills] == [
        "MAT-FRC",
        "MAT-OPS",
    ]
    assert result.clarification_question
    assert SkillMappingReasonCode.MULTIPLE_CANDIDATES in result.reason_codes


def test_low_evidence_learning_request_abstains_with_no_match(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, _ = mapper

    result = service.map(SkillMappingRequest(learner_message="Teach me algebraic equations"))

    assert result.status is SkillMappingStatus.NO_MATCH
    assert result.skill_id is None
    assert not result.candidate_skills


def test_semantic_relevance_gate_rejects_unsupported_and_off_topic_messages(
    skill_nodes: tuple[SkillNode, ...],
) -> None:
    class RelevanceEmbeddingModel:
        def embed_queries(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
            return tuple(
                (1.0, 0.0) if "algebra" in text.casefold() else (0.0, 1.0)
                for text in texts
            )

        def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
            return tuple(
                (1.0, 0.0) if "algebra" in text.casefold() else (0.0, 1.0)
                for text in texts
            )

    relevance = SemanticRelevanceGate(
        RelevanceEmbeddingModel(),
        {"unsupported_learning": ("Algebra example",), "off_topic": ("Sports example",)},
    )
    service = ConversationalSkillMapper(
        SemanticSkillRetriever(skill_nodes, FakeEmbeddingModel()),
        relevance_gate=relevance,
    )

    unsupported = service.map(SkillMappingRequest(learner_message="Teach me algebra"))
    off_topic = service.map(SkillMappingRequest(learner_message="Sports score please"))

    assert unsupported.status is SkillMappingStatus.NO_MATCH
    assert unsupported.intent is LearningIntent.EXPLANATION_REQUEST
    assert off_topic.status is SkillMappingStatus.NOT_SKILL_RELATED
    assert off_topic.intent is LearningIntent.OFF_TOPIC


def test_relevance_resource_is_small_and_valid() -> None:
    examples = JsonSkillRelevanceCatalog(
        REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-relevance-v1.json"
    ).load()

    assert set(examples) == {"unsupported_learning", "off_topic"}
    assert sum(map(len, examples.values())) == 7


def test_development_and_held_out_evaluation_splits_are_disjoint() -> None:
    development = json.loads(
        (REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-development-v1.json").read_text(
            encoding="utf-8"
        )
    )
    held_out = json.loads(
        (REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-held-out-v1.json").read_text(
            encoding="utf-8"
        )
    )
    valid_ids = {
        node.skill_id
        for node in XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    }

    assert development["tuning_allowed"] is True
    assert held_out["tuning_allowed"] is False
    assert {case["case_id"] for case in development["cases"]}.isdisjoint(
        {case["case_id"] for case in held_out["cases"]}
    )
    assert {
        case["expected_skill_id"]
        for document in (development, held_out)
        for case in document["cases"]
        if case["expected_skill_id"] is not None
    } <= valid_ids


def test_greeting_does_not_run_semantic_retrieval(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, embeddings = mapper

    result = service.map(SkillMappingRequest(learner_message="Ayubowan teacher!"))

    assert result.status is SkillMappingStatus.NOT_SKILL_RELATED
    assert result.intent is LearningIntent.GREETING
    assert embeddings.query_calls == 0


def test_off_topic_message_is_not_forced_to_a_skill(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, _ = mapper

    result = service.map(SkillMappingRequest(learner_message="Who won the cricket match?"))

    assert result.status is SkillMappingStatus.NOT_SKILL_RELATED
    assert result.intent is LearningIntent.OFF_TOPIC


def test_short_numeric_message_is_an_answer_submission(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, _ = mapper
    request = SkillMappingRequest(
        learner_message="3/4",
        active_skill_id="MAT-FRC",
        conversation_context=[
            {"role": "TUTOR", "message": "Write the answer as a fraction."},
        ],
    )

    result = service.map(request)

    assert result.status is SkillMappingStatus.MATCHED
    assert result.intent is LearningIntent.ANSWER_SUBMISSION
    assert result.skill_id == "MAT-FRC"


def test_active_skill_supports_a_contextual_follow_up(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, _ = mapper
    request = SkillMappingRequest(
        learner_message="Why did you multiply that?",
        active_skill_id="MAT-FRC",
        conversation_context=[
            {"role": "LEARNER", "message": "Help me add these fractions."},
            {"role": "TUTOR", "message": "First find a common denominator."},
        ],
    )

    result = service.map(request)

    assert result.status is SkillMappingStatus.MATCHED
    assert result.skill_id == "MAT-FRC"
    assert result.intent is LearningIntent.FOLLOW_UP_QUESTION
    assert SkillMappingReasonCode.ACTIVE_SKILL_USED in result.reason_codes


def test_self_contained_new_topic_overrides_active_skill(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, _ = mapper
    request = SkillMappingRequest(
        learner_message="How many days are in a leap year?",
        active_skill_id="MAT-FRC",
        conversation_context=[
            {"role": "LEARNER", "message": "Help me add these fractions."},
        ],
    )

    result = service.map(request)

    assert result.status is SkillMappingStatus.MATCHED
    assert result.skill_id == "MAT-TIM"
    assert SkillMappingReasonCode.ACTIVE_SKILL_USED not in result.reason_codes


def test_invalid_active_skill_is_rejected_before_retrieval(
    mapper: tuple[ConversationalSkillMapper, FakeEmbeddingModel],
) -> None:
    service, embeddings = mapper

    with pytest.raises(ValueError, match="unknown skill IDs: NOT-REAL"):
        service.map(
            SkillMappingRequest(
                learner_message="Why?",
                active_skill_id="NOT-REAL",
                conversation_context=[{"role": "TUTOR", "message": "Try again."}],
            )
        )

    assert embeddings.query_calls == 0


def test_unicode_and_mathematical_symbols_are_preserved() -> None:
    text = "  භාගය  3/4   மற்றும்  ½  "

    assert prepare_text(text) == "භාගය 3/4 மற்றும் ½"


def test_ties_are_deterministic_by_skill_id(
    skill_nodes: tuple[SkillNode, ...],
) -> None:
    retriever = SemanticSkillRetriever(skill_nodes, FakeEmbeddingModel())

    first = retriever.rank("How do I work with these numbers?")
    second = retriever.rank("How do I work with these numbers?")

    assert first == second
    assert [candidate.node.skill_id for candidate in first[:2]] == ["MAT-FRC", "MAT-OPS"]


def test_passage_embeddings_are_cached(
    skill_nodes: tuple[SkillNode, ...],
) -> None:
    embeddings = FakeEmbeddingModel()
    retriever = SemanticSkillRetriever(skill_nodes, embeddings)

    retriever.rank("fractions")
    retriever.rank("time")

    assert embeddings.passage_calls == 1
    assert embeddings.query_calls == 2


def test_e5_adapter_does_not_import_or_download_on_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("sentence_transformers"):
            raise AssertionError("sentence-transformers must be lazy-loaded")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    SentenceTransformerE5EmbeddingModel()


def test_e5_adapter_applies_query_and_passage_prefixes() -> None:
    class RecordingModel:
        def __init__(self) -> None:
            self.calls: list[tuple[list[str], dict[str, object]]] = []

        def encode(self, texts: list[str], **kwargs: object) -> list[list[float]]:
            self.calls.append((texts, kwargs))
            return [[1.0, 0.0] for _ in texts]

    model = RecordingModel()
    embeddings = SentenceTransformerE5EmbeddingModel()
    embeddings._model = model

    embeddings.embed_queries(["භාග 3/4"])
    embeddings.embed_passages(["Fractions and decimals"])

    assert model.calls[0][0] == ["query: භාග 3/4"]
    assert model.calls[1][0] == ["passage: Fractions and decimals"]
    assert all(call[1]["normalize_embeddings"] is True for call in model.calls)


def test_policy_rejects_incoherent_thresholds() -> None:
    with pytest.raises(ValueError, match="candidate_threshold must not exceed"):
        SkillMappingPolicy(match_threshold=0.7, candidate_threshold=0.8)
