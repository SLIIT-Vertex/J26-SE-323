import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.adaptive_tutor.application.skill_mapper import RankedSkill
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingRequest
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus, SkillNode
from tools.skill_mapper_benchmark.calibration import fit_policy, labelled, predicted_status
from tools.skill_mapper_benchmark.evidence import contradicts_evidence, notation_evidence
from tools.skill_mapper_benchmark.mappers import (
    CrossEncoderScorer,
    DecisionPolicy,
    ScoredCase,
    decide,
)
from tools.skill_mapper_benchmark.metrics import CaseOutcome, macro_f1, summarize
from tools.skill_mapper_benchmark.normalization import normalize_math_text

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
V2 = REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-v2"
NODES = tuple(
    SkillNode("MAT", skill_id, name, name, f"{name} scope.")
    for skill_id, name in (
        ("MAT-FRC", "Fractions"),
        ("MAT-TIM", "Time"),
        ("MAT-OPS", "Operations"),
        ("MAT-MON", "Money"),
    )
)
NODES_BY_ID = {node.skill_id: node for node in NODES}


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("½ + ¼", "1/2 + 1/4"),
        ("2½ − 1 / 4", "2 1/2 - 1/4"),
        ("3⁄4 of １２", "3/4 of 12"),
        ("08 : 30 → 10:15", "08:30 → 10:15"),
        ("1/2 සහ 2/4 සමානද?", "1/2 සහ 2/4 සමානද?"),
        ("how to add frations", "how to add frations"),
    ],
)
def test_normalization_only_canonicalizes_notation(raw: str, normalized: str) -> None:
    assert normalize_math_text(raw) == normalized


@pytest.mark.parametrize(
    ("message", "skills"),
    [
        ("½ + ¼", {"MAT-FRC"}),
        ("1/2 saha 2/4 samanada?", {"MAT-FRC"}),
        ("14:00 - 09:30", {"MAT-TIM"}),
        ("25/12/2026 is which day of the week?", {"MAT-TIM"}),
        ("Rs. 500 − Rs. 275", {"MAT-MON"}),
        ("2 kg 300 g + 1 kg 900 g", {"MAT-MAS"}),
        ("3 m 40 cm = ? cm", {"MAT-LEN"}),
        ("Convert 1/2 hour to minutes", set()),
        ("What is 3/4?", set()),
        ("How do I add these?", set()),
    ],
)
def test_notation_evidence_is_narrow_and_time_aware(message: str, skills: set[str]) -> None:
    assert notation_evidence(message) == frozenset(skills)


def test_evidence_can_only_contradict_never_select() -> None:
    assert contradicts_evidence("MAT-TIM", frozenset({"MAT-FRC"}))
    assert not contradicts_evidence("MAT-FRC", frozenset({"MAT-FRC"}))
    assert not contradicts_evidence("MAT-OPS", frozenset())


def scored(
    ranking: Sequence[tuple[str, float]],
    *,
    evidence: frozenset[str] = frozenset(),
    intent: LearningIntent = LearningIntent.EXPLANATION_REQUEST,
    kind: str = "logit",
) -> ScoredCase:
    return ScoredCase(
        intent=intent,
        ranking=tuple(ranking),
        decision_pool=len(ranking),
        evidence=evidence,
        uses_context=False,
        seconds=0.0,
        score_kind=kind,
    )


POLICY = DecisionPolicy(match_score=2.0, minimum_margin=1.0, candidate_score=-1.0)
REQUEST = SkillMappingRequest(learner_message="How do I add 1/4 and 1/5?")


def test_confident_top_skill_is_matched_with_sigmoid_confidence() -> None:
    result, vetoed = decide(
        REQUEST, scored([("MAT-FRC", 3.0), ("MAT-TIM", 1.0)]), POLICY, NODES_BY_ID
    )

    assert result.status is SkillMappingStatus.MATCHED
    assert result.skill_id == "MAT-FRC"
    assert result.confidence == pytest.approx(0.952574, abs=1e-6)
    assert not vetoed


def test_evidence_contradiction_turns_a_confident_pick_into_clarification() -> None:
    case = scored([("MAT-TIM", 3.0), ("MAT-FRC", 1.0)], evidence=frozenset({"MAT-FRC"}))

    result, vetoed = decide(REQUEST, case, POLICY, NODES_BY_ID)

    assert vetoed
    assert result.status is SkillMappingStatus.AMBIGUOUS
    assert [candidate.skill_id for candidate in result.candidate_skills] == ["MAT-TIM", "MAT-FRC"]
    assert result.skill_id is None


def test_close_scores_ask_for_clarification_instead_of_forcing_a_match() -> None:
    result, _ = decide(REQUEST, scored([("MAT-FRC", 3.0), ("MAT-TIM", 2.5)]), POLICY, NODES_BY_ID)

    assert result.status is SkillMappingStatus.AMBIGUOUS
    assert result.clarification_question


def test_low_scores_abstain_and_greetings_are_not_skill_related() -> None:
    low, _ = decide(REQUEST, scored([("MAT-FRC", -3.0), ("MAT-TIM", -4.0)]), POLICY, NODES_BY_ID)
    greeting, _ = decide(
        SkillMappingRequest(learner_message="Hello"),
        scored([("MAT-FRC", 9.0), ("MAT-TIM", 0.0)], intent=LearningIntent.GREETING),
        POLICY,
        NODES_BY_ID,
    )

    assert low.status is SkillMappingStatus.NO_MATCH
    assert greeting.status is SkillMappingStatus.NOT_SKILL_RELATED


def test_fast_calibration_rule_matches_contract_decisions() -> None:
    scores = (-2.0, 0.5, 2.0, 2.6, 4.0)
    for top, second, has_evidence in itertools.product(scores, scores, (False, True)):
        if second > top:
            continue
        case = scored(
            [("MAT-OPS", top), ("MAT-FRC", second)],
            evidence=frozenset({"MAT-FRC"}) if has_evidence else frozenset(),
        )
        result, _ = decide(REQUEST, case, POLICY, NODES_BY_ID)
        fast = predicted_status(labelled(REQUEST, "MATCHED", "MAT-OPS", case), POLICY)
        assert fast == (result.status.value, result.skill_id)


def test_policy_fit_reaches_zero_development_false_confirmations() -> None:
    cases = [
        labelled(REQUEST, "MATCHED", "MAT-FRC", scored([("MAT-FRC", 5.0), ("MAT-TIM", 1.0)])),
        labelled(REQUEST, "MATCHED", "MAT-TIM", scored([("MAT-TIM", 4.0), ("MAT-FRC", 0.5)])),
        labelled(REQUEST, "AMBIGUOUS", None, scored([("MAT-OPS", 4.5), ("MAT-FRC", 0.0)])),
        labelled(REQUEST, "MATCHED", "MAT-OPS", scored([("MAT-FRC", 3.0), ("MAT-OPS", 2.9)])),
    ]

    policy, fit = fit_policy(cases)

    outcomes = [predicted_status(case, policy) for case in cases]
    false_confirmations = [
        case
        for case, (status, skill) in zip(cases, outcomes, strict=True)
        if status == "MATCHED" and (case.gold_status != "MATCHED" or skill != case.gold_skill_id)
    ]
    assert false_confirmations == []
    assert fit["development_correct_matches"] == 1
    assert outcomes[0] == ("MATCHED", "MAT-FRC")


class FakeCrossEncoder:
    name = "fake"

    def __init__(self) -> None:
        self.pairs: list[tuple[str, str]] = []

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        self.pairs.extend(pairs)
        return [3.0 if "Fractions" in passage else 0.0 for _, passage in pairs]


class FakeRetriever:
    def rank(self, query: str) -> tuple[RankedSkill, ...]:
        order = ("MAT-TIM", "MAT-FRC", "MAT-OPS", "MAT-MON")
        return tuple(
            RankedSkill(NODES_BY_ID[skill], 0.9 - index / 10) for index, skill in enumerate(order)
        )


def test_hybrid_reranks_only_the_e5_shortlist() -> None:
    cross_encoder = FakeCrossEncoder()
    scorer = CrossEncoderScorer(NODES, cross_encoder, retriever=FakeRetriever(), top_k=2)  # type: ignore[arg-type]

    case = scorer.score(SkillMappingRequest(learner_message="½ + ¼"))

    assert len(cross_encoder.pairs) == 2
    assert cross_encoder.pairs[0][0] == "1/2 + 1/4"
    assert [skill for skill, _ in case.ranking] == ["MAT-FRC", "MAT-TIM", "MAT-OPS", "MAT-MON"]
    assert case.decision_pool == 2
    assert case.evidence == frozenset({"MAT-FRC"})


def test_all_skill_cross_encoder_scores_every_skill() -> None:
    cross_encoder = FakeCrossEncoder()

    case = CrossEncoderScorer(NODES, cross_encoder).score(
        SkillMappingRequest(learner_message="hi there")
    )

    assert len(cross_encoder.pairs) == len(NODES)
    assert case.top[0] == "MAT-FRC"


def outcome(gold: tuple[str, str | None], predicted: tuple[str, str | None]) -> CaseOutcome:
    return CaseOutcome(
        "c",
        "english",
        "x",
        gold[0],
        gold[1],
        predicted[0],
        predicted[1],
        ("MAT-FRC",),
        1.0,
        1.0,
        False,
        0.0,
    )


def test_false_confident_matches_include_wrong_skills_and_non_matching_gold() -> None:
    outcomes = [
        outcome(("MATCHED", "MAT-FRC"), ("MATCHED", "MAT-FRC")),
        outcome(("MATCHED", "MAT-FRC"), ("MATCHED", "MAT-TIM")),
        outcome(("AMBIGUOUS", None), ("MATCHED", "MAT-FRC")),
        outcome(("NO_MATCH", None), ("AMBIGUOUS", None)),
    ]

    summary = summarize(outcomes)

    assert summary["false_confident_matches"]["count"] == 2  # type: ignore[index]
    assert summary["confirmed_match_coverage"] == {"count": 1, "of": 2, "rate": 0.5}
    assert summary["clarification_rate"]["count"] == 1  # type: ignore[index]
    assert 0.0 < macro_f1(outcomes) < 1.0


def load_corpus() -> tuple[dict[str, object], dict[str, object]]:
    return tuple(  # type: ignore[return-value]
        json.loads((V2 / f"skill-mapper-corpus-v2-{split}.json").read_text(encoding="utf-8"))
        for split in ("development", "test")
    )


@pytest.mark.requires_research
def test_corpus_labels_are_proposals_and_splits_are_group_disjoint() -> None:
    development, test = load_corpus()
    cases = [*development["cases"], *test["cases"]]  # type: ignore[misc]

    assert len(cases) == 270
    assert {case["provenance"] for case in cases} == {"DESIGN_AUTHORED_UNREVIEWED"}
    assert {case["label_status"] for case in cases} == {"PROPOSED"}
    assert development["tuning_allowed"] is True and test["tuning_allowed"] is False
    assert not {c["group_id"] for c in development["cases"]} & {
        c["group_id"] for c in test["cases"]
    }  # type: ignore[union-attr]
    assert development["content_sha256"] == test["content_sha256"]


@pytest.mark.requires_research
def test_corpus_covers_every_skill_and_language_form_in_both_splits() -> None:
    development, test = load_corpus()
    for split in (development, test):
        skills = {
            c["proposed_skill_id"] for c in split["cases"] if c["category"] == "skill-coverage"
        }  # type: ignore[union-attr]
        assert len(skills) == 30
    coverage = Counter(
        (case["proposed_skill_id"], case["language"])
        for case in [*development["cases"], *test["cases"]]  # type: ignore[misc]
        if case["category"] == "skill-coverage"
    )
    assert len(coverage) == 210 and set(coverage.values()) == {1}


@pytest.mark.requires_research
def test_frozen_baseline_snapshots_match_their_manifest() -> None:
    manifest = json.loads((V2 / "baselines/manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["baselines"].values():
        source = (REPOSITORY_ROOT / entry["source"]).read_bytes()
        assert hashlib.sha256(source).hexdigest() == entry["sha256"]
