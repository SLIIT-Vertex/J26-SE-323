"""Measure how well the reader and the rules work on labelled pictures of answered questions.

This is how you decide whether a reader (and a prompt version) is good enough before real
children use it, and how you re-check after changing either. It runs the same code the app runs.

    python -m scripts.benchmark_vision template crops/            # write a labels.json to fill in
    python -m scripts.benchmark_vision run labels.json --dry-run   # count, show a prompt, no calls
    python -m scripts.benchmark_vision run labels.json             # the real measurement
    python -m scripts.benchmark_vision run labels.json --provider gemini --workers 3 --out report.json

labels.json (one entry per cropped question picture; "text" is what the child ACTUALLY wrote or
marked, as a person read it from the photo):

    {"items": [
      {"image": "crops/q_3_41.png", "question_id": "3.41", "language": "si",
       "reference": "crops/q_3_41_blank.png",
       "parts": [{"text": "ii"}, {"text": "", "blank": true}]}
    ]}

Answer keys come from the database (question_id + language), or from an "answer_key" list in the
entry for an offline run: [{"part_no": 1, "kind": "choice", "alternatives": ["2"]}].

What it reports (the targets from the design, adjust to taste):
  * reading accuracy per kind of part: choice and number parts >= 90%, handwritten text >= 80%
  * ZERO clearly blank answers read as answered (and none of a real answer read as blank)
  * share of parts sent to the parent (high but honest is better than low and wrong)
  * how often the final marking (correct / wrong / blank) agrees with the labelled one
  * latency and tokens, and cost when prices are given
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.knowledge_tracing.application.grading import (
    GradingConfig,
    ItemGrade,
    ItemJob,
    KeyPart,
    PartRead,
    compare_part,
    grade_items,
    norm,
    part_specs,
)
from app.knowledge_tracing.application.grading.prompts import blind_prompt
from app.knowledge_tracing.application.grading.types import ItemRead, ReviewPolicy, VisionProvider

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TARGETS = {"choice": 0.90, "number": 0.90, "text": 0.80, "instruction": 0.80}


@dataclass(frozen=True, slots=True)
class LabelledPart:
    text: str
    blank: bool


@dataclass(frozen=True, slots=True)
class LabelledItem:
    image: Path
    question_id: str
    language: str
    parts: tuple[LabelledPart, ...]
    reference: Path | None = None
    answer_key: tuple[KeyPart, ...] | None = None


@dataclass(slots=True)
class PartOutcome:
    kind: str
    reading_exact: bool
    labelled_blank: bool
    read_blank: bool
    sent_to_parent: bool
    final_agrees: bool | None  # None while the parent is still to decide


@dataclass(slots=True)
class Report:
    items: int = 0
    parts: int = 0
    failed_items: int = 0
    by_kind: dict[str, list[bool]] = field(default_factory=lambda: defaultdict(list))
    blank_read_as_answered: int = 0
    answered_read_as_blank: int = 0
    sent_to_parent: int = 0
    final_agree: int = 0
    final_decided: int = 0
    latencies_ms: list[int] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cost: float | None = None

    def summary(self) -> dict:
        def pct(numerator: int, denominator: int) -> float | None:
            return None if denominator == 0 else round(100 * numerator / denominator, 1)

        kinds = {
            kind: {
                "parts": len(values),
                "reading_accuracy_pct": pct(sum(values), len(values)),
                "target_pct": round(100 * TARGETS.get(kind, 0.8)),
            }
            for kind, values in sorted(self.by_kind.items())
        }
        return {
            "items": self.items,
            "parts": self.parts,
            "items_the_reader_failed": self.failed_items,
            "reading_accuracy_by_kind": kinds,
            "blank_read_as_answered": self.blank_read_as_answered,
            "answered_read_as_blank": self.answered_read_as_blank,
            "share_sent_to_parent_pct": pct(self.sent_to_parent, self.parts),
            "final_marking_agreement_pct": pct(self.final_agree, self.final_decided),
            "decided_without_parent": self.final_decided,
            "latency_ms_mean": round(statistics.fmean(self.latencies_ms)) if self.latencies_ms else None,
            "latency_ms_p95": (
                round(sorted(self.latencies_ms)[int(0.95 * (len(self.latencies_ms) - 1))])
                if self.latencies_ms
                else None
            ),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost": None if self.cost is None else round(self.cost, 4),
            "errors": dict(self.errors),
        }

    def verdict(self) -> list[str]:
        """Plain statements about the targets, so the numbers are not left to be interpreted."""
        lines: list[str] = []
        for kind, values in sorted(self.by_kind.items()):
            target = TARGETS.get(kind, 0.8)
            accuracy = sum(values) / len(values)
            lines.append(
                f"{'OK  ' if accuracy >= target else 'LOW '} {kind}: reading {accuracy:.0%} "
                f"(target {target:.0%}, {len(values)} parts)"
            )
        lines.append(
            f"{'OK  ' if self.blank_read_as_answered == 0 else 'FAIL'} blank answers read as "
            f"answered: {self.blank_read_as_answered} (target 0)"
        )
        if self.items < 100:
            lines.append(f"NOTE only {self.items} items; the design asks for 100+ from 5+ children")
        return lines


# ---- reading the labels -----------------------------------------------------------------------


def _key_part(raw: dict) -> KeyPart:
    return KeyPart(
        part_no=int(raw["part_no"]),
        kind=raw["kind"],
        alternatives=tuple(raw.get("alternatives", ())),
        option_labels=tuple(raw["option_labels"]) if raw.get("option_labels") else None,
        instruction=raw.get("instruction"),
        label=raw.get("label"),
    )


def load_labels(path: Path) -> list[LabelledItem]:
    base = path.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[LabelledItem] = []
    for index, raw in enumerate(data["items"]):
        parts = tuple(
            LabelledPart(text=str(p.get("text", "")), blank=bool(p.get("blank", not p.get("text"))))
            for p in raw["parts"]
        )
        if not parts:
            raise ValueError(f"item {index}: no parts")
        items.append(
            LabelledItem(
                image=base / raw["image"],
                question_id=str(raw["question_id"]),
                language=str(raw["language"]),
                parts=parts,
                reference=(base / raw["reference"]) if raw.get("reference") else None,
                answer_key=tuple(_key_part(k) for k in raw["answer_key"]) if raw.get("answer_key") else None,
            )
        )
    return items


def write_template(folder: Path, out: Path) -> int:
    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    template = {
        "items": [
            {
                "image": p.relative_to(out.parent).as_posix() if p.is_relative_to(out.parent) else p.as_posix(),
                "question_id": "FILL-IN",
                "language": "si",
                "parts": [{"text": "FILL-IN what the child wrote, or leave empty and set blank"}],
            }
            for p in images
        ]
    }
    out.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    return len(images)


# ---- the measurement ----------------------------------------------------------------------------


def _expected_status(label: LabelledPart, key: KeyPart, config: GradingConfig) -> str:
    """What the marking should be, by running the labelled text through the same rules."""
    read = PartRead(part=key.part_no, answer="" if label.blank else label.text, blank=label.blank,
                    confidence=1.0)
    return compare_part(read, key, GradingConfig(review_policy=config.review_policy)).status


def evaluate(
    items: list[LabelledItem],
    keys: list[list[KeyPart]],
    provider: VisionProvider,
    *,
    workers: int = 3,
    second_provider: VisionProvider | None = None,
    config: GradingConfig = GradingConfig(),  # noqa: B008
    price_in: float | None = None,
    price_out: float | None = None,
) -> Report:
    jobs = [
        ItemJob(
            key,
            item.image.read_bytes(),
            item.language,
            blank_reference=item.reference.read_bytes() if item.reference else None,
        )
        for item, key in zip(items, keys, strict=True)
    ]
    graded: list[ItemGrade] = grade_items(
        jobs, provider, workers=workers, second_provider=second_provider, config=config
    )

    report = Report()
    for item, key, result in zip(items, keys, graded, strict=True):
        report.items += 1
        for call in result.calls:
            report.latencies_ms.append(call.latency_ms)
            report.tokens_in += call.tokens_in or 0
            report.tokens_out += call.tokens_out or 0
        for code in result.errors:
            report.errors[code] += 1
        if result.errors and not result.calls:
            report.failed_items += 1

        for label, key_part, grade in zip(item.parts, key, result.question.parts, strict=True):
            report.parts += 1
            read_blank = grade.status == "blank" or (
                not norm(grade.read_text) and grade.how in ("empty", "no reading")
            )
            if grade.review_reason in ("vision_error", "part_count_mismatch", "part_missing") and not grade.read_text:
                read_blank = False  # nothing was read at all: not a blank reading
            exact = (label.blank and read_blank) or (
                not label.blank and norm(grade.read_text) == norm(label.text)
            )
            report.by_kind[key_part.kind].append(exact)
            if label.blank and not read_blank and grade.read_text.strip():
                report.blank_read_as_answered += 1
            if not label.blank and read_blank:
                report.answered_read_as_blank += 1
            if grade.needs_review:
                report.sent_to_parent += 1
            else:
                report.final_decided += 1
                report.final_agree += grade.status == _expected_status(label, key_part, config)

    if price_in is not None and price_out is not None:
        report.cost = (report.tokens_in * price_in + report.tokens_out * price_out) / 1_000_000
    return report


# ---- command line -------------------------------------------------------------------------------


def _print(report: Report, provider: VisionProvider) -> None:
    summary = report.summary()
    print(f"reader: {provider.name} / {getattr(provider, 'model', '?')} / {provider.prompt_version}")
    print(f"items: {summary['items']}   parts: {summary['parts']}   "
          f"reader failed on: {summary['items_the_reader_failed']} items")
    print()
    print(f"{'kind':12} {'parts':>6} {'reading %':>10} {'target %':>9}")
    for kind, row in summary["reading_accuracy_by_kind"].items():
        print(f"{kind:12} {row['parts']:>6} {row['reading_accuracy_pct']!s:>10} {row['target_pct']:>9}")
    print()
    print(f"blank read as answered : {summary['blank_read_as_answered']}   (target 0)")
    print(f"answered read as blank : {summary['answered_read_as_blank']}")
    print(f"sent to the parent     : {summary['share_sent_to_parent_pct']} %")
    print(f"marking agrees         : {summary['final_marking_agreement_pct']} % "
          f"of {summary['decided_without_parent']} parts decided without the parent")
    print(f"latency (ms)           : mean {summary['latency_ms_mean']}   p95 {summary['latency_ms_p95']}")
    print(f"tokens                 : in {summary['tokens_in']}   out {summary['tokens_out']}   "
          f"cost {summary['cost']}")
    if summary["errors"]:
        print(f"errors                 : {summary['errors']}")
    print()
    for line in report.verdict():
        print(line)


def _load_keys(items: list[LabelledItem]) -> list[list[KeyPart]]:
    needed = [i for i in items if i.answer_key is None]
    from_db: dict[tuple[str, str], list[KeyPart]] = {}
    if needed:
        from app.knowledge_tracing.infrastructure.db.answer_key_repository import (
            SqlAlchemyAnswerKeyRepository,
        )
        from app.shared.database.session import SessionLocal

        with SessionLocal() as session:
            repository = SqlAlchemyAnswerKeyRepository(session)
            for item in needed:
                from_db[(item.question_id, item.language)] = repository.key(
                    item.question_id, item.language
                )
    keys: list[list[KeyPart]] = []
    for item in items:
        key = list(item.answer_key) if item.answer_key is not None else from_db[(item.question_id, item.language)]
        if not key:
            raise SystemExit(f"no answer key for question {item.question_id} ({item.language})")
        if len(key) != len(item.parts):
            raise SystemExit(
                f"{item.image.name}: the key has {len(key)} parts but the label has {len(item.parts)}"
            )
        keys.append(key)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="write a labels.json skeleton for a folder of crops")
    template.add_argument("folder", type=Path)
    template.add_argument("--out", type=Path, default=None)

    run = sub.add_parser("run", help="measure the reader on labelled pictures")
    run.add_argument("labels", type=Path)
    run.add_argument("--provider", help="mock | gemini (default: VISION_PROVIDER)")
    run.add_argument("--second-provider", help="optional second opinion")
    run.add_argument("--workers", type=int, default=3)
    run.add_argument("--limit", type=int)
    run.add_argument("--policy", choices=("reader_unsure", "strict"), default="reader_unsure")
    run.add_argument("--price-in", type=float, help="cost per 1,000,000 input tokens")
    run.add_argument("--price-out", type=float, help="cost per 1,000,000 output tokens")
    run.add_argument("--out", type=Path, help="write the report as JSON")
    run.add_argument("--dry-run", action="store_true", help="no calls: count items, show a prompt")
    args = parser.parse_args()

    if args.command == "template":
        out = args.out or args.folder / "labels.json"
        count = write_template(args.folder, out)
        print(f"wrote {out} with {count} items to fill in")
        return 0

    items = load_labels(args.labels)
    if args.limit:
        items = items[: args.limit]
    keys = _load_keys(items)

    if args.dry_run:
        print(f"{len(items)} items, {sum(len(i.parts) for i in items)} parts")
        print("a prompt for the first item:\n")
        print(blind_prompt(part_specs(keys[0]), items[0].language, items[0].reference is not None))
        return 0

    from app.config import get_settings
    from app.knowledge_tracing.application.grading.call_log import MemoryCallLog
    from app.knowledge_tracing.infrastructure.vision.factory import create_vision_provider

    settings = get_settings()
    log = MemoryCallLog()
    provider = create_vision_provider(settings, args.provider, call_log=log)
    second = (
        create_vision_provider(settings, args.second_provider, call_log=log)
        if args.second_provider
        else None
    )
    policy = ReviewPolicy.strict() if args.policy == "strict" else ReviewPolicy.reader_unsure()
    config = GradingConfig(confidence_min=settings.vision_confidence_min, review_policy=policy)

    started = time.perf_counter()
    report = evaluate(
        items, keys, provider, workers=args.workers, second_provider=second, config=config,
        price_in=args.price_in, price_out=args.price_out,
    )
    _print(report, provider)
    print(f"\nwall time: {time.perf_counter() - started:.0f} s")
    for warning in sorted(getattr(provider, "warnings", set())):
        print(f"WARNING {warning}")
    if args.out:
        args.out.write_text(
            json.dumps({**report.summary(), "verdict": report.verdict()}, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        print(f"report written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# Re-exported for tests.
__all__ = ["ItemRead", "LabelledItem", "LabelledPart", "Report", "evaluate", "load_labels"]
