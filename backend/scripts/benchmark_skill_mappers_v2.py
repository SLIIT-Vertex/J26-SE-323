"""Diagnostic benchmark: frozen E5 baselines vs. calibrated E5, hybrid E5+cross-encoder, all-30 CE.

Offline only (local_files_only). No Gemini or other network calls. Results on the design-authored
corpus are diagnostic until the corpus receives qualified human review.

Pre-registered development-only selections:
- Cross-encoder passage format: the format with higher development top-1 accuracy for all-30
  scoring ("scope" wins ties).
- Hybrid shortlist size k: the smallest k in 3..15 whose normalized-E5 development recall@k is at
  least 0.95 (15 if none reaches it).
- Decision policies: tools.skill_mapper_benchmark.calibration.fit_policy on development cases.
The test split is scored once per configuration and never used for any selection.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import platform
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

from app.adaptive_tutor.application.skill_mapper import SemanticSkillRetriever
from app.adaptive_tutor.application.skill_mapper_contracts import (
    ConversationTurn,
    SkillMappingRequest,
)
from app.adaptive_tutor.infrastructure import (
    DEFAULT_E5_MODEL,
    DEFAULT_E5_REVISION,
    SentenceTransformerE5EmbeddingModel,
    XlsxSkillTaxonomyCatalog,
)
from tools.skill_mapper_benchmark.calibration import fit_policy, labelled
from tools.skill_mapper_benchmark.mappers import (
    CrossEncoderScorer,
    DecisionPolicy,
    E5Scorer,
    ScoredCase,
    decide,
)
from tools.skill_mapper_benchmark.metrics import (
    CaseOutcome,
    bootstrap_intervals,
    latency,
    sliced,
    summarize,
)
from tools.skill_mapper_benchmark.rerankers import (
    BGE_RERANKER_LICENSE,
    BGE_RERANKER_MODEL,
    BGE_RERANKER_REVISION,
    SentenceTransformerCrossEncoder,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
V2 = REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-v2"
WARMUP = ("How do I add 1/4 and 1/5?", "What time is it?", "Hello")

Case = dict[str, object]
Scorer = Callable[[SkillMappingRequest], ScoredCase]


def load_split(split: str) -> list[Case]:
    return json.loads((V2 / f"skill-mapper-corpus-v2-{split}.json").read_text(encoding="utf-8"))[
        "cases"
    ]


def to_request(case: Case) -> SkillMappingRequest:
    return SkillMappingRequest(
        learner_message=str(case["learner_message"]),
        conversation_context=tuple(
            ConversationTurn(role=turn["role"], message=turn["message"])  # type: ignore[index]
            for turn in case.get("conversation_context", [])  # type: ignore[union-attr]
        ),
        active_skill_id=case.get("active_skill_id"),  # type: ignore[arg-type]
    )


def load_frozen_baseline(name: str) -> ModuleType:
    manifest = json.loads((V2 / "baselines/manifest.json").read_text(encoding="utf-8"))
    entry = manifest["baselines"][name]
    source_path = REPOSITORY_ROOT / entry["source"]
    source = source_path.read_bytes()
    if hashlib.sha256(source).hexdigest() != entry["sha256"]:
        raise RuntimeError(f"frozen baseline {name} does not match its manifest hash")
    module_name = f"frozen_skill_mapper_{name.replace('-', '_')}"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = module
    exec(compile(source, str(source_path), "exec"), module.__dict__)  # noqa: S102 - hash-verified snapshot
    return module


def outcome(
    case: Case,
    result,
    ranking: tuple[str, ...],
    top: float,
    margin: float,
    vetoed: bool,
    seconds: float,
) -> CaseOutcome:  # type: ignore[no-untyped-def]
    return CaseOutcome(
        case_id=str(case["case_id"]),
        language=str(case["language"]),
        category=str(case["category"]),
        gold_status=str(case["proposed_status"]),
        gold_skill_id=case.get("proposed_skill_id"),  # type: ignore[arg-type]
        predicted_status=result.status.value,
        predicted_skill_id=result.skill_id,
        ranking=ranking,
        top_score=top,
        margin=margin,
        vetoed=vetoed,
        seconds=seconds,
    )


def run_baseline(mapper, cases: list[Case]) -> list[CaseOutcome]:  # type: ignore[no-untyped-def]
    outcomes = []
    for case in cases:
        request = to_request(case)
        started = time.perf_counter()
        result = mapper.map(request)
        seconds = time.perf_counter() - started
        ranked = mapper.rank(request)
        margin = ranked[0].score - ranked[1].score if len(ranked) > 1 else 1.0
        outcomes.append(
            outcome(
                case,
                result,
                tuple(item.node.skill_id for item in ranked),
                ranked[0].score,
                margin,
                False,
                seconds,
            )
        )
    return outcomes


def score_all(scorer: Scorer, cases: list[Case]) -> list[ScoredCase]:
    return [scorer(to_request(case)) for case in cases]


def decide_all(
    cases: list[Case], scored: list[ScoredCase], policy: DecisionPolicy, nodes_by_id
) -> list[CaseOutcome]:  # type: ignore[no-untyped-def]
    outcomes = []
    for case, item in zip(cases, scored, strict=True):
        result, vetoed = decide(to_request(case), item, policy, nodes_by_id)
        outcomes.append(
            outcome(
                case,
                result,
                tuple(skill for skill, _ in item.ranking),
                item.top[1],
                item.margin,
                vetoed,
                item.seconds,
            )
        )
    return outcomes


def top1(cases: list[Case], scored: list[ScoredCase]) -> float:
    pairs = [
        (case, item)
        for case, item in zip(cases, scored, strict=True)
        if case["proposed_status"] == "MATCHED"
    ]
    return sum(item.top[0] == case["proposed_skill_id"] for case, item in pairs) / len(pairs)


def recall_at(cases: list[Case], scored: list[ScoredCase], k: int) -> float:
    pairs = [
        (case, item)
        for case, item in zip(cases, scored, strict=True)
        if case["proposed_status"] == "MATCHED"
    ]
    return sum(
        case["proposed_skill_id"] in [skill for skill, _ in item.ranking[:k]]
        for case, item in pairs
    ) / len(pairs)


def report(outcomes: list[CaseOutcome]) -> dict[str, object]:
    return {
        "overall": summarize(outcomes),
        "bootstrap_95ci": bootstrap_intervals(outcomes),
        "by_language": sliced(outcomes, lambda item: item.language),
        "by_category": sliced(outcomes, lambda item: item.category),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--devices", default="cpu,mps")
    parser.add_argument("--output", type=Path, default=V2 / "results")
    args = parser.parse_args()
    devices = [device.strip() for device in args.devices.split(",") if device.strip()]
    if devices[0] != "cpu":
        raise ValueError("cpu must run first: it produces the reference scores")

    nodes = XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    nodes_by_id = {node.skill_id: node for node in nodes}
    development, test = load_split("development"), load_split("test")
    frozen = {name: load_frozen_baseline(name) for name in ("e5-head", "e5-working-tree")}

    results: dict[str, object] = {
        "benchmark_version": "skill-mapper-benchmark-v2",
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "DIAGNOSTIC — design-authored, unreviewed corpus; not evidence for runtime integration",
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "torch": __import__("torch").__version__,
            "sentence_transformers": __import__("sentence_transformers").__version__,
        },
        "models": {
            "e5": {"name": DEFAULT_E5_MODEL, "revision": DEFAULT_E5_REVISION},
            "cross_encoder": {
                "name": BGE_RERANKER_MODEL,
                "revision": BGE_RERANKER_REVISION,
                "license": BGE_RERANKER_LICENSE,
                "max_length": 256,
                "scores": "raw logits for ranking and calibration; sigmoid only for contract confidence",
            },
        },
        "corpus": {"development_cases": len(development), "test_cases": len(test)},
        "selection_rules": __doc__.split("Pre-registered development-only selections:", 1)[
            1
        ].strip(),
    }
    configs: dict[str, dict[str, object]] = {}
    reference_scores: dict[str, list[ScoredCase]] = {}
    latencies: dict[str, dict[str, object]] = {}

    for device in devices:
        print(f"[{device}] loading models", flush=True)
        e5 = SentenceTransformerE5EmbeddingModel(device=device, local_files_only=True)
        retriever = SemanticSkillRetriever(nodes, e5)
        cross_encoder = SentenceTransformerCrossEncoder(device=device)
        baselines = {
            name: module.ConversationalSkillMapper(module.SemanticSkillRetriever(nodes, e5))
            for name, module in frozen.items()
        }
        e5_scorer = E5Scorer(retriever)
        for text in WARMUP:
            request = SkillMappingRequest(learner_message=text)
            e5_scorer.score(request)
            cross_encoder.score([(text, "warm up")])
            for mapper in baselines.values():
                mapper.map(request)

        if device == "cpu":
            print("[cpu] frozen baselines", flush=True)
            for name, mapper in baselines.items():
                configs[name] = {
                    "description": "frozen live policy (0.82 / 0.03 / 0.70), taxonomy passages only",
                    "development": report(run_baseline(mapper, development)),
                    "test_outcomes": run_baseline(mapper, test),
                }

            print("[cpu] dev selections", flush=True)
            e5_dev = score_all(e5_scorer.score, development)
            recalls = {k: recall_at(development, e5_dev, k) for k in range(3, 16)}
            hybrid_k = next((k for k, value in recalls.items() if value >= 0.95), 15)
            format_top1 = {}
            all30_dev = {}
            for passage_format in ("scope", "taxonomy"):
                scorer = CrossEncoderScorer(nodes, cross_encoder, passage_format=passage_format)
                all30_dev[passage_format] = score_all(scorer.score, development)
                format_top1[passage_format] = top1(development, all30_dev[passage_format])
            passage_format = (
                "scope" if format_top1["scope"] >= format_top1["taxonomy"] else "taxonomy"
            )
            results["development_selections"] = {
                "e5_normalized_recall_at_k": recalls,
                "hybrid_k": hybrid_k,
                "all30_top1_by_passage_format": format_top1,
                "passage_format": passage_format,
            }

            hybrid = CrossEncoderScorer(
                nodes,
                cross_encoder,
                retriever=retriever,
                top_k=hybrid_k,
                passage_format=passage_format,
            )
            all30 = CrossEncoderScorer(nodes, cross_encoder, passage_format=passage_format)
            dev_scores = {
                "e5-calibrated": e5_dev,
                f"hybrid-e5top{hybrid_k}-bge": score_all(hybrid.score, development),
                "all30-bge": all30_dev[passage_format],
            }
            scorers = {
                "e5-calibrated": e5_scorer.score,
                f"hybrid-e5top{hybrid_k}-bge": hybrid.score,
                "all30-bge": all30.score,
            }
            for name, scorer in scorers.items():
                print(f"[cpu] {name}", flush=True)
                test_scores = score_all(scorer, test)
                reference_scores[name] = test_scores
                for veto in (True, False):
                    label = name if veto else f"{name} (no evidence veto)"
                    dev_labelled = [
                        labelled(
                            to_request(case),
                            str(case["proposed_status"]),
                            case.get("proposed_skill_id"),
                            item,
                        )  # type: ignore[arg-type]
                        for case, item in zip(development, dev_scores[name], strict=True)
                    ]
                    policy, fit = fit_policy(dev_labelled, evidence_veto=veto)
                    configs[label] = {
                        "description": "development-calibrated policy",
                        "policy": {
                            "match_score": policy.match_score,
                            "minimum_margin": policy.minimum_margin,
                            "candidate_score": policy.candidate_score,
                            "evidence_veto": policy.evidence_veto,
                        },
                        "fit": fit,
                        "development": report(
                            decide_all(development, dev_scores[name], policy, nodes_by_id)
                        ),
                        "test_outcomes": decide_all(test, test_scores, policy, nodes_by_id),
                    }
            latencies["cpu"] = {
                **{
                    name: latency([item.seconds for item in configs[name]["test_outcomes"]])
                    for name in baselines
                },  # type: ignore[union-attr]
                **{
                    name: latency([item.seconds for item in reference_scores[name]])
                    for name in scorers
                },
            }
        else:
            print(f"[{device}] latency and score agreement", flush=True)
            hybrid_k = results["development_selections"]["hybrid_k"]  # type: ignore[index]
            passage_format = results["development_selections"]["passage_format"]  # type: ignore[index]
            scorers = {
                "e5-calibrated": e5_scorer.score,
                f"hybrid-e5top{hybrid_k}-bge": CrossEncoderScorer(
                    nodes,
                    cross_encoder,
                    retriever=retriever,
                    top_k=hybrid_k,
                    passage_format=passage_format,
                ).score,
                "all30-bge": CrossEncoderScorer(
                    nodes, cross_encoder, passage_format=passage_format
                ).score,
            }
            device_latency: dict[str, object] = {
                name: latency([item.seconds for item in run_baseline(mapper, test)])
                for name, mapper in baselines.items()
            }
            for name, scorer in scorers.items():
                scored = score_all(scorer, test)
                drift = (
                    max(
                        abs(a[1] - b[1])
                        for ref, new in zip(reference_scores[name], scored, strict=True)
                        for a, b in zip(ref.ranking, new.ranking, strict=True)
                        if a[0] == b[0] and a[1] != float("-inf")
                    )
                    if all(
                        [s for s, _ in ref.ranking] == [s for s, _ in new.ranking]
                        for ref, new in zip(reference_scores[name], scored, strict=True)
                    )
                    else None
                )
                ranking_changes = sum(
                    [s for s, _ in ref.ranking[:1]] != [s for s, _ in new.ranking[:1]]
                    for ref, new in zip(reference_scores[name], scored, strict=True)
                )
                device_latency[name] = {
                    **latency([item.seconds for item in scored]),
                    "max_abs_score_drift_vs_cpu": drift,
                    "top1_changes_vs_cpu": ranking_changes,
                }
            latencies[device] = device_latency

    results["latency_test_split_per_query"] = latencies
    results["configurations"] = {}
    for name, config in configs.items():
        test_outcomes: list[CaseOutcome] = config.pop("test_outcomes")  # type: ignore[assignment]
        config["test"] = report(test_outcomes)
        results["configurations"][name] = config  # type: ignore[index]
        config["_test_outcomes"] = test_outcomes

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "benchmark-v2-test-cases.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "configuration",
                "case_id",
                "language",
                "category",
                "gold_status",
                "gold_skill_id",
                "predicted_status",
                "predicted_skill_id",
                "top_1",
                "top_score",
                "margin",
                "evidence_veto",
                "false_confident_match",
            ]
        )
        for name, config in configs.items():
            for item in config.pop("_test_outcomes"):  # type: ignore[union-attr]
                writer.writerow(
                    [
                        name,
                        item.case_id,
                        item.language,
                        item.category,
                        item.gold_status,
                        item.gold_skill_id or "",
                        item.predicted_status,
                        item.predicted_skill_id or "",
                        item.ranking[0],
                        f"{item.top_score:.6f}",
                        f"{item.margin:.6f}",
                        item.vetoed,
                        item.false_confident_match,
                    ]
                )
    (args.output / "benchmark-v2.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                name: {
                    k: config["test"]["overall"][k]
                    for k in (
                        "top_1_accuracy",
                        "confirmed_match_coverage",
                        "false_confident_matches",
                        "clarification_rate",
                        "macro_f1",
                    )
                }
                for name, config in results["configurations"].items()
            },
            indent=1,
            default=str,
        )
    )  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
