"""Try the whole marking chain on a photo of one page, and save nothing.

    python -m scripts.try_page_photo path\to\\photo.jpg                 # page 2 of this week's paper
    python -m scripts.try_page_photo photo.jpg --page 1
    python -m scripts.try_page_photo photo.jpg --paper-token 5LPI7EPDL4H5
    python -m scripts.try_page_photo photo.jpg --out some\folder        # also keep the straightened page and crops

It does what the app does after an upload: find the page by its four black squares and its QR code,
straighten it, cut one picture per question, let the reader (VISION_PROVIDER) read each one without
knowing the answer, and compare with the key. Then it prints, per question, what was read and how it
was marked.

Nothing is written: no photo record, no marked answer, no attempt, no mastery change, so the page can
still be uploaded and marked in the app afterwards. The paper's own files and the database are only
read. The crops are sent to the configured reader (OpenAI or Gemini), exactly as in a real upload.
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.knowledge_tracing.api.papers_router import get_paper_storage
from app.knowledge_tracing.api.submissions_router import _review_policy
from app.knowledge_tracing.application.grading import GradingConfig
from app.knowledge_tracing.application.grading.pipeline import ItemJob, grade_items
from app.knowledge_tracing.application.paper_generation import week_start_for
from app.knowledge_tracing.application.photo_alignment import AlignmentFailure
from app.knowledge_tracing.application.photo_check import check_page_photo, failure_message
from app.knowledge_tracing.application.photo_crops import draw_overlay, encode_png
from app.knowledge_tracing.infrastructure.db.answer_key_repository import (
    SqlAlchemyAnswerKeyRepository,
)
from app.knowledge_tracing.infrastructure.db.models import PaperModel
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import render_pages
from app.knowledge_tracing.infrastructure.vision.factory import (
    VisionNotConfigured,
    get_second_vision_provider,
    get_vision_provider,
)
from app.shared.database.session import SessionLocal

DEFAULT_LEARNER_ID = "00000000-0000-4000-8000-000000000721"  # the learner the game and the papers share


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo", type=Path)
    parser.add_argument("--page", type=int, default=2)
    parser.add_argument("--paper-token", help="the code printed on the page (default: this week's paper)")
    parser.add_argument("--out", type=Path, help="a folder for the straightened page and the question crops")
    args = parser.parse_args(argv)

    data = args.photo.read_bytes()
    settings = get_settings()
    try:
        provider = get_vision_provider()
        second = get_second_vision_provider()
    except VisionNotConfigured as error:
        print(f"NOT READY: {error}")
        return 1

    with SessionLocal() as session:
        papers = SqlAlchemyPaperRepository(session)
        if args.paper_token:
            paper_id = session.scalar(select(PaperModel.id).where(PaperModel.qr_token == args.paper_token))
            paper = None if paper_id is None else papers.get(paper_id)
        else:
            paper = papers.find_for_week(UUID(DEFAULT_LEARNER_ID), week_start_for(datetime.now(UTC)))
        if paper is None:
            print("no paper found (is there one for this week? try --paper-token)", file=sys.stderr)
            return 1
        items = papers.items(paper.id)
        pdf = get_paper_storage().get(paper.pdf_key)
        keys = SqlAlchemyAnswerKeyRepository(session).keys([i.question_id for i in items], paper.language)

        print(f"paper {paper.token}  ({paper.mode}, {len(items)} questions, {paper.page_count} pages, "
              f"language {paper.language}); trying page {args.page}")
        try:
            check = check_page_photo(data, paper, args.page, items, lambda: render_pages(pdf))
        except AlignmentFailure as failure:
            print(f"\nTHE PHOTO WAS NOT ACCEPTED: {failure.reason}\n  {failure_message(failure.reason)}")
            print(f"  detail: {failure.detail}")
            return 1
        print(f"photo accepted: found by {check.alignment.method}, sharpness {check.alignment.blur_score:.1f}, "
              f"{len(check.crops)} questions cut out\n")

        by_position = {i.position: i for i in items}
        jobs, used = [], []
        for crop in check.crops:
            item = by_position[crop.position]
            key = keys.get(item.question_id)
            if not key:
                print(f"  Q{crop.position}: no answer key, skipped")
                continue
            jobs.append(ItemJob(key, encode_png(crop.image), paper.language,
                                blank_reference=None if crop.blank is None else encode_png(crop.blank)))
            used.append((crop, item))

        graded = grade_items(
            jobs, provider, workers=settings.vision_concurrency, second_provider=second,
            config=GradingConfig(
                confidence_min=settings.vision_confidence_min,
                review_policy=_review_policy(),
                recheck_blanks=settings.grading_recheck_blanks,
            ),
        )
        session.rollback()  # nothing above wrote anything; this makes sure of it

    print(f"reader: {provider.name} / {getattr(provider, 'model', '?')}"
          + (f", second reader {second.name}" if second else ""))
    print(f"{'Q':>2} {'skill':8} {'read':<22} {'marked':<10} {'conf':>5}  note")
    tally: dict[str, int] = {}
    for (crop, item), grade in zip(used, graded, strict=True):
        for part in grade.question.parts:
            label = "needs a parent" if part.needs_review else part.status
            tally[label] = tally.get(label, 0) + 1
            note = part.review_reason or ""
            if grade.errors:
                note = f"{note} reader error: {', '.join(grade.errors)}".strip()
            print(f"{crop.position:>2} {item.skill_code:8} {part.read_text[:20]!r:<22} {label:<10} "
                  f"{part.confidence:>5.2f}  {note}")
    print("\nsummary: " + ", ".join(f"{n} {label}" for label, n in sorted(tally.items())))
    print("nothing was saved; the page can still be uploaded in the app.")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "page.png").write_bytes(encode_png(check.alignment.canonical))
        (args.out / "overlay.png").write_bytes(
            encode_png(draw_overlay(check.alignment.canonical, [(c.position, c.box) for c in check.crops]))
        )
        for crop, _ in used:
            (args.out / f"q{crop.position}.png").write_bytes(encode_png(crop.image))
        print(f"pictures saved in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
