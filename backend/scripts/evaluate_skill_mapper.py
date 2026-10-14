import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.adaptive_tutor.application import (
    ConversationalSkillMapper,
    SemanticRelevanceGate,
    SemanticSkillRetriever,
    SkillMappingPolicy,
    SkillMappingRequest,
)
from app.adaptive_tutor.infrastructure import (
    DEFAULT_E5_MODEL,
    DEFAULT_E5_REVISION,
    JsonSkillRelevanceCatalog,
    JsonSkillTaxonomyEnrichmentCatalog,
    SentenceTransformerE5EmbeddingModel,
    XlsxSkillTaxonomyCatalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Skill Mapper with real embeddings")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-evaluation-v1.json",
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=REPOSITORY_ROOT / "docs/skill_nodes.xlsx",
    )
    parser.add_argument("--model", default=DEFAULT_E5_MODEL)
    parser.add_argument("--revision", default=DEFAULT_E5_REVISION)
    parser.add_argument("--cache-folder")
    parser.add_argument("--device")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--match-threshold", type=float, default=0.82)
    parser.add_argument("--candidate-threshold", type=float, default=0.70)
    parser.add_argument("--minimum-margin", type=float, default=0.03)
    parser.add_argument("--enrichment", type=Path)
    parser.add_argument("--relevance", type=Path)
    parser.add_argument("--relevance-minimum-advantage", type=float, default=0.0)
    parser.add_argument("--configuration", default="baseline")
    args = parser.parse_args()

    document = json.loads(args.dataset.read_text(encoding="utf-8"))
    nodes = XlsxSkillTaxonomyCatalog(args.taxonomy).load()
    skill_ids = {node.skill_id for node in nodes}
    unknown_expected = sorted(
        {
            case["expected_skill_id"]
            for case in document["cases"]
            if case.get("expected_skill_id") not in {None, *skill_ids}
        }
    )
    if unknown_expected:
        raise ValueError(f"evaluation data contains unknown skill IDs: {unknown_expected}")

    embeddings = SentenceTransformerE5EmbeddingModel(
        model_name=args.model,
        revision=args.revision,
        device=args.device,
        cache_folder=args.cache_folder,
        local_files_only=not args.allow_download,
    )
    retrieval_enrichments: dict[str, list[str]] = defaultdict(list)
    if args.enrichment:
        for enrichment in JsonSkillTaxonomyEnrichmentCatalog(args.enrichment).load(skill_ids):
            retrieval_enrichments[enrichment.skill_id].append(enrichment.text)
    relevance_gate = None
    if args.relevance:
        relevance_gate = SemanticRelevanceGate(
            embeddings,
            JsonSkillRelevanceCatalog(args.relevance).load(),
            minimum_advantage=args.relevance_minimum_advantage,
        )
    mapper = ConversationalSkillMapper(
        SemanticSkillRetriever(nodes, embeddings, retrieval_enrichments),
        SkillMappingPolicy(
            match_threshold=args.match_threshold,
            candidate_threshold=args.candidate_threshold,
            minimum_margin=args.minimum_margin,
        ),
        relevance_gate,
    )

    try:
        report = _evaluate(
            document,
            mapper,
            args.top_k,
            args.model,
            args.revision,
            args.configuration,
            relevance_gate,
        )
    except (OSError, RuntimeError) as error:
        print(
            json.dumps(
                {
                    "real_model_evaluation": "NOT RUN",
                    "reason": str(error),
                    "hint": "Install the skill-mapper extra and cache the model, or use --allow-download.",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _evaluate(
    document: dict[str, Any],
    mapper: ConversationalSkillMapper,
    top_k: int,
    model_name: str,
    revision: str,
    configuration: str,
    relevance_gate: SemanticRelevanceGate | None,
) -> dict[str, Any]:
    totals = _empty_metrics()
    by_language: dict[str, dict[str, int]] = defaultdict(_empty_metrics)
    by_skill: dict[str, dict[str, int]] = defaultdict(_empty_metrics)
    failures: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)
    status_confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    false_matches: list[str] = []
    incorrect_abstentions: list[str] = []

    for case in document["cases"]:
        request = SkillMappingRequest.model_validate(
            {
                field: case[field]
                for field in (
                    "learner_message",
                    "conversation_context",
                    "active_skill_id",
                    "preferred_language",
                )
                if field in case
            }
        )
        result = mapper.map(request)
        expected_skill_id = case.get("expected_skill_id")
        full_ranking = mapper.rank(request)
        ranked = full_ranking[:top_k]
        top_ids = [candidate.node.skill_id for candidate in ranked]
        top_candidates = [
            {"skill_id": candidate.node.skill_id, "score": candidate.score}
            for candidate in ranked
        ]
        top_margin = ranked[0].score - ranked[1].score if len(ranked) > 1 else None
        expected_candidate = next(
            (
                (index, candidate)
                for index, candidate in enumerate(full_ranking, start=1)
                if candidate.node.skill_id == expected_skill_id
            ),
            None,
        )
        expected_skill_rank = expected_candidate[0] if expected_candidate else None
        expected_skill_score = expected_candidate[1].score if expected_candidate else None
        relevance = (
            relevance_gate.assess(request.learner_message, full_ranking[0].score)
            if relevance_gate
            else None
        )
        status_correct = result.status == case["expected_status"]
        intent_correct = result.intent == case["expected_intent"]
        skill_correct = expected_skill_id is not None and result.skill_id == expected_skill_id
        top_1_correct = expected_skill_id is not None and top_ids[0] == expected_skill_id
        top_k_correct = expected_skill_id is not None and expected_skill_id in top_ids
        status_counts[result.status.value] += 1
        status_confusion[case["expected_status"]][result.status.value] += 1

        is_false_match = result.status.value == "MATCHED" and (
            expected_skill_id is None or result.skill_id != expected_skill_id
        )
        is_incorrect_abstention = (
            case["expected_status"] == "MATCHED" and result.status.value != "MATCHED"
        )
        if is_false_match:
            false_matches.append(case["case_id"])
        if is_incorrect_abstention:
            incorrect_abstentions.append(case["case_id"])

        cases.append(
            {
                "case_id": case["case_id"],
                "language": case["language"],
                "learner_message": case["learner_message"],
                "expected_status": case["expected_status"],
                "actual_status": result.status,
                "expected_intent": case["expected_intent"],
                "actual_intent": result.intent,
                "expected_skill_id": expected_skill_id,
                "expected_skill_rank": expected_skill_rank,
                "expected_skill_score": expected_skill_score,
                "actual_skill_id": result.skill_id,
                "predicted_top_skill_id": top_ids[0],
                "top_margin": top_margin,
                "top_candidates": top_candidates,
                "relevance_category": relevance.category if relevance else None,
                "relevance_negative_score": relevance.negative_score if relevance else None,
                "relevance_supported_score": relevance.supported_score if relevance else None,
                "false_match": is_false_match,
                "incorrect_abstention": is_incorrect_abstention,
            }
        )

        _record(
            totals,
            expected_skill_id,
            status_correct,
            intent_correct,
            skill_correct,
            top_1_correct,
            top_k_correct,
            result.status.value == "MATCHED",
            case["expected_status"] == "MATCHED",
        )
        _record(
            by_language[case["language"]],
            expected_skill_id,
            status_correct,
            intent_correct,
            skill_correct,
            top_1_correct,
            top_k_correct,
            result.status.value == "MATCHED",
            case["expected_status"] == "MATCHED",
        )
        if expected_skill_id is not None:
            _record(
                by_skill[expected_skill_id],
                expected_skill_id,
                status_correct,
                intent_correct,
                skill_correct,
                top_1_correct,
                top_k_correct,
                result.status.value == "MATCHED",
                case["expected_status"] == "MATCHED",
            )

        if not status_correct or not intent_correct or (expected_skill_id and not skill_correct):
            failures.append(
                {
                    "case_id": case["case_id"],
                    "language": case["language"],
                    "expected_status": case["expected_status"],
                    "actual_status": result.status,
                    "expected_intent": case["expected_intent"],
                    "actual_intent": result.intent,
                    "expected_skill_id": expected_skill_id,
                    "expected_skill_rank": expected_skill_rank,
                    "expected_skill_score": expected_skill_score,
                    "actual_skill_id": result.skill_id,
                    "predicted_top_skill_id": top_ids[0],
                    "top_candidates": top_candidates,
                    "top_margin": top_margin,
                    "relevance_category": relevance.category if relevance else None,
                    "relevance_negative_score": relevance.negative_score if relevance else None,
                }
            )

    return {
        "real_model_evaluation": "COMPLETED",
        "dataset_version": document["dataset_version"],
        "dataset_status": document["status"],
        "model": model_name,
        "revision": revision,
        "configuration": configuration,
        "split": document.get("split", "diagnostic-baseline"),
        "tuning_allowed": document.get("tuning_allowed", False),
        "top_k": top_k,
        "overall": _rates(totals),
        "by_language": {language: _rates(metrics) for language, metrics in sorted(by_language.items())},
        "by_skill": {skill_id: _rates(metrics) for skill_id, metrics in sorted(by_skill.items())},
        "actual_status_counts": dict(sorted(status_counts.items())),
        "status_confusion": {
            expected: dict(sorted(actual.items()))
            for expected, actual in sorted(status_confusion.items())
        },
        "false_matches": false_matches,
        "incorrect_abstentions": incorrect_abstentions,
        "observed_failures": failures,
        "cases": cases,
    }


def _empty_metrics() -> dict[str, int]:
    return {
        "total": 0,
        "labeled": 0,
        "status_correct": 0,
        "intent_correct": 0,
        "skill_correct": 0,
        "top_1_correct": 0,
        "top_k_correct": 0,
        "confirmed": 0,
        "confirmed_labeled": 0,
        "correct_confirmed": 0,
        "expected_matched": 0,
        "false_confirmed": 0,
        "incorrect_abstentions": 0,
    }


def _record(
    metrics: dict[str, int],
    expected_skill_id: str | None,
    status_correct: bool,
    intent_correct: bool,
    skill_correct: bool,
    top_1_correct: bool,
    top_k_correct: bool,
    actual_confirmed: bool,
    expected_matched: bool,
) -> None:
    metrics["total"] += 1
    metrics["status_correct"] += int(status_correct)
    metrics["intent_correct"] += int(intent_correct)
    metrics["confirmed"] += int(actual_confirmed)
    metrics["correct_confirmed"] += int(actual_confirmed and skill_correct)
    metrics["expected_matched"] += int(expected_matched)
    metrics["false_confirmed"] += int(actual_confirmed and not skill_correct)
    metrics["incorrect_abstentions"] += int(expected_matched and not actual_confirmed)
    if expected_skill_id is not None:
        metrics["labeled"] += 1
        metrics["confirmed_labeled"] += int(actual_confirmed)
        metrics["skill_correct"] += int(skill_correct)
        metrics["top_1_correct"] += int(top_1_correct)
        metrics["top_k_correct"] += int(top_k_correct)


def _rates(metrics: dict[str, int]) -> dict[str, int | float | None]:
    total = metrics["total"]
    labeled = metrics["labeled"]
    confirmed = metrics["confirmed"]
    expected_matched = metrics["expected_matched"]
    return {
        **metrics,
        "status_accuracy": metrics["status_correct"] / total if total else None,
        "intent_accuracy": metrics["intent_correct"] / total if total else None,
        "skill_match_accuracy": metrics["skill_correct"] / labeled if labeled else None,
        "top_1_retrieval_accuracy": metrics["top_1_correct"] / labeled if labeled else None,
        "top_k_retrieval_accuracy": metrics["top_k_correct"] / labeled if labeled else None,
        "confirmed_match_precision": (
            metrics["correct_confirmed"] / confirmed if confirmed else None
        ),
        "confirmed_match_coverage": (
            metrics["confirmed_labeled"] / labeled if labeled else None
        ),
        "false_confirmation_rate": (
            metrics["false_confirmed"] / confirmed if confirmed else None
        ),
        "incorrect_abstention_rate": (
            metrics["incorrect_abstentions"] / expected_matched
            if expected_matched
            else None
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
