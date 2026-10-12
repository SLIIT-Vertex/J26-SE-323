import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.adaptive_tutor.application import (
    ConversationalSkillMapper,
    SemanticSkillRetriever,
    SkillMappingPolicy,
    SkillMappingRequest,
)
from app.adaptive_tutor.infrastructure import (
    DEFAULT_E5_MODEL,
    DEFAULT_E5_REVISION,
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
    mapper = ConversationalSkillMapper(
        SemanticSkillRetriever(nodes, embeddings),
        SkillMappingPolicy(
            match_threshold=args.match_threshold,
            candidate_threshold=args.candidate_threshold,
            minimum_margin=args.minimum_margin,
        ),
    )

    try:
        report = _evaluate(document, mapper, args.top_k, args.model, args.revision)
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
) -> dict[str, Any]:
    totals = _empty_metrics()
    by_language: dict[str, dict[str, int]] = defaultdict(_empty_metrics)
    failures: list[dict[str, Any]] = []

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
        top_ids = (
            [candidate.node.skill_id for candidate in mapper.rank(request)[:top_k]]
            if expected_skill_id
            else []
        )
        status_correct = result.status == case["expected_status"]
        intent_correct = result.intent == case["expected_intent"]
        skill_correct = expected_skill_id is not None and result.skill_id == expected_skill_id
        top_k_correct = expected_skill_id is not None and expected_skill_id in top_ids

        _record(totals, expected_skill_id, status_correct, intent_correct, skill_correct, top_k_correct)
        _record(
            by_language[case["language"]],
            expected_skill_id,
            status_correct,
            intent_correct,
            skill_correct,
            top_k_correct,
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
                    "actual_skill_id": result.skill_id,
                    "top_k": top_ids,
                }
            )

    return {
        "real_model_evaluation": "COMPLETED",
        "dataset_version": document["dataset_version"],
        "dataset_status": document["status"],
        "model": model_name,
        "revision": revision,
        "top_k": top_k,
        "overall": _rates(totals),
        "by_language": {language: _rates(metrics) for language, metrics in sorted(by_language.items())},
        "observed_failures": failures,
    }


def _empty_metrics() -> dict[str, int]:
    return {
        "total": 0,
        "labeled": 0,
        "status_correct": 0,
        "intent_correct": 0,
        "skill_correct": 0,
        "top_k_correct": 0,
    }


def _record(
    metrics: dict[str, int],
    expected_skill_id: str | None,
    status_correct: bool,
    intent_correct: bool,
    skill_correct: bool,
    top_k_correct: bool,
) -> None:
    metrics["total"] += 1
    metrics["status_correct"] += int(status_correct)
    metrics["intent_correct"] += int(intent_correct)
    if expected_skill_id is not None:
        metrics["labeled"] += 1
        metrics["skill_correct"] += int(skill_correct)
        metrics["top_k_correct"] += int(top_k_correct)


def _rates(metrics: dict[str, int]) -> dict[str, int | float | None]:
    total = metrics["total"]
    labeled = metrics["labeled"]
    return {
        **metrics,
        "status_accuracy": metrics["status_correct"] / total if total else None,
        "intent_accuracy": metrics["intent_correct"] / total if total else None,
        "skill_match_accuracy": metrics["skill_correct"] / labeled if labeled else None,
        "top_k_retrieval_accuracy": metrics["top_k_correct"] / labeled if labeled else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
