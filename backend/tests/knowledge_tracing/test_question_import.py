import io
from pathlib import Path

import pytest
from PIL import Image

from app.knowledge_tracing.application.question_import import (
    ImageInfo,
    ImportPlan,
    QuestionBankFiles,
    build_plan,
    load_files,
)
from app.knowledge_tracing.infrastructure.storage import LocalStorage
from app.knowledge_tracing.infrastructure.storage.question_images import StorageImageSource

SKILL_CODES = (
    [f"APT-AA{chr(65 + i)}" for i in range(10)]
    + [f"MAT-MA{chr(65 + i)}" for i in range(10)]
    + [f"LAN-LA{chr(65 + i)}" for i in range(5)]
    + [f"ENV-EA{chr(65 + i)}" for i in range(5)]
)
NODES = "\n".join(
    ["| Domain Tag | Skill ID | Skill Name (English) | Sinhala | Description |", "|---|---|---|---|---|"]
    + [f"| {code[:3]} | {code} | {code} | | |" for code in SKILL_CODES]
)


class FakeImages:
    def __init__(self, missing: set[tuple[str, str]] | None = None) -> None:
        self.missing = missing or set()

    def describe(self, language: str, question_id: str) -> ImageInfo | None:
        if (language, question_id) in self.missing:
            return None
        key = f"questions/{language}/{question_id}.png"
        return ImageInfo(key, 400, 200, f"{language}{question_id}")


def bank(**overrides: str) -> QuestionBankFiles:
    texts = {
        "answers": "1.1 - 3\n1.2 - 2, ගස\n",
        "answers_ta": "1.1 - 3\n1.2 - 2, மரம்\n",
        "skills": "1.1 - APT-AAA\n1.2 - MAT-MAA, MAT-MAB\n",
        "difficulty": (
            "1.1 - APT-AAA: Easy | 1.0 min   "
            "1.2 - MAT-MAA, MAT-MAB: Hard / Medium | 2.0 / 1.0 mins"
        ),
    }
    texts.update(overrides)
    files = QuestionBankFiles(skill_nodes=("skill_nodes.md", NODES))
    files.answers[("1", "si")] = ("answers-1.md", texts["answers"])
    files.answers[("1", "ta")] = ("answers-1-T.md", texts["answers_ta"])
    files.skill_maps["1"] = ("skillMap-1.md", texts["skills"])
    files.difficulties["1"] = ("difficult-time-1.md", texts["difficulty"])
    return files


def errors(plan: ImportPlan) -> list[str]:
    return [str(issue) for issue in plan.errors]


def test_a_valid_bank_builds_a_plan() -> None:
    plan = build_plan(bank(), FakeImages())

    assert plan.ok, errors(plan)
    assert len(plan.skills) == 30
    assert [s.sort_index for s in plan.skills] == list(range(30))
    first, second = plan.questions
    assert (first.id, first.skill_code, first.difficulty, first.est_seconds) == (
        "1.1",
        "APT-AAA",
        "easy",
        60,
    )
    assert (second.skill_code, second.secondary_skill_codes) == ("MAT-MAA", ("MAT-MAB",))
    assert second.difficulty == "hard"
    assert second.est_seconds == 180
    assert set(second.variants) == {"si", "ta"}
    assert [p.answer_kind for p in second.variants["si"].parts] == ["choice", "text"]


def test_feature_spec_order_controls_sort_index() -> None:
    reversed_order = list(reversed([s.code for s in build_plan(bank(), FakeImages()).skills]))

    plan = build_plan(bank(), FakeImages(), feature_spec_order=reversed_order)

    assert plan.ok
    assert [s.code for s in plan.skills] == reversed_order
    assert plan.skills[0].sort_index == 0


def test_feature_spec_that_disagrees_is_an_error() -> None:
    plan = build_plan(bank(), FakeImages(), feature_spec_order=["APT-AAA", "NOT-REAL"])

    assert not plan.ok
    assert any("NOT-REAL" in e for e in errors(plan))


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"skills": "1.1 - APT-AAA\n"}, "1.2 has an answer but no skill"),
        ({"difficulty": "1.1 - APT-AAA: Easy | 1.0 min"}, "1.2 has an answer but no difficulty"),
        (
            {"skills": "1.1 - APT-AAA\n1.2 - MAT-MAA, MAT-MAB\n1.3 - MAT-MAA\n"},
            "1.3 has a skill but no answer",
        ),
        ({"skills": "1.1 - NOP-NOP\n1.2 - MAT-MAA, MAT-MAB\n"}, "unknown skill NOP-NOP"),
        ({"answers_ta": "1.1 - 3\n"}, "1.2 has a Sinhala answer but no Tamil answer"),
        ({"answers_ta": "1.1 - 3\n1.2 - 2\n"}, "1 answer parts but the Sinhala key has 2"),
        ({"answers": "1.1 - 3\n1.2 - 2, \n"}, "part 2 is empty"),
        ({"answers": '1.1 - "oops\n1.2 - 2, ගස\n'}, "unbalanced double quote"),
        ({"answers": "1.1 - 3\n2.1 - 4\n1.2 - 2, ගස\n"}, "does not belong to set 1"),
        (
            {
                "difficulty": "1.1 - APT-AAB: Easy | 1.0 min   "
                "1.2 - MAT-MAA, MAT-MAB: Hard / Medium | 2.0 / 1.0 mins"
            },
            "differ from the skill map",
        ),
    ],
)
def test_problems_are_reported_and_block_the_import(
    override: dict[str, str], expected: str
) -> None:
    plan = build_plan(bank(**override), FakeImages())

    assert not plan.ok
    assert any(expected in e for e in errors(plan)), errors(plan)


def test_a_missing_image_is_an_error() -> None:
    plan = build_plan(bank(), FakeImages(missing={("ta", "1.2")}))

    assert not plan.ok
    assert any("1.2" in e and "no ta image" in e for e in errors(plan))


def test_all_problems_are_listed_not_just_the_first() -> None:
    plan = build_plan(
        bank(skills="1.1 - NOP-NOP\n", answers_ta="1.1 - 3\n"),
        FakeImages(missing={("si", "1.1")}),
    )

    assert len(plan.errors) >= 3


def test_missing_files_are_reported() -> None:
    files = bank()
    del files.skill_maps["1"]

    plan = build_plan(files, FakeImages())

    assert any("skillMap-1 is missing" in e for e in errors(plan))


def test_identical_image_on_two_questions_is_a_warning() -> None:
    class SameImage:
        def describe(self, language: str, question_id: str) -> ImageInfo:
            return ImageInfo(f"{language}/{question_id}", 10, 10, "same")

    plan = build_plan(bank(), SameImage())

    assert plan.ok
    assert any("share an identical image" in str(w) for w in plan.warnings)


def test_missing_feature_spec_is_a_warning_not_an_error() -> None:
    plan = build_plan(bank(), FakeImages())

    assert any("feature_spec.json" in str(w) for w in plan.warnings)


def test_load_files_prefers_md_and_finds_both_languages(tmp_path: Path) -> None:
    (tmp_path / "answers-1.md").write_text("1.1 - 3\n", encoding="utf-8", newline="\n")
    (tmp_path / "answers-1.txt").write_text("1.1 - 9\n", encoding="utf-8", newline="\n")
    (tmp_path / "answers-1-T.txt").write_text("1.1 - 3\n", encoding="utf-8", newline="\n")
    (tmp_path / "skillMap-1.md").write_text("1.1 - APT-AAA\n", encoding="utf-8", newline="\n")
    (tmp_path / "difficult-time-1.md").write_text("1.1 - APT-AAA: Easy | 1.0 min", encoding="utf-8", newline="\n")
    (tmp_path / "skill_nodes.md").write_text(NODES, encoding="utf-8", newline="\n")
    (tmp_path / "notes.md").write_text("ignore me", encoding="utf-8", newline="\n")

    files = load_files(tmp_path)

    assert files.answers[("1", "si")] == ("answers-1.md", "1.1 - 3\n")
    assert files.answers[("1", "ta")][0] == "answers-1-T.txt"
    assert set(files.skill_maps) == set(files.difficulties) == {"1"}
    assert files.skill_nodes is not None


def _png(width: int, height: int, shade: int = 255) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (shade, shade, shade)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_storage_image_source_reads_size_and_hash(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    storage.put("questions/3/3.41.png", _png(300, 120))
    storage.put("questions/3-T/3.41.png", _png(310, 125, 200))
    storage.put("questions/3/3.42.png", b"not an image")
    source = StorageImageSource(storage, "questions/")
    source.prefetch([("si", "3.41"), ("ta", "3.41"), ("si", "3.42")])

    si = source.describe("si", "3.41")
    ta = source.describe("ta", "3.41")

    assert si is not None and ta is not None
    assert (si.key, si.width, si.height) == ("questions/3/3.41.png", 300, 120)
    assert (ta.key, ta.width, ta.height) == ("questions/3-T/3.41.png", 310, 125)
    assert si.content_hash != ta.content_hash
    assert source.describe("si", "9.9") is None
    with pytest.raises(Exception, match="PNG or JPEG|cannot identify"):
        source.describe("si", "3.42")


@pytest.mark.parametrize(
    "override",
    [
        {"skills": "1.1 - APT-AAA\n"},
        {"difficulty": "1.1 - APT-AAA: Easy | 1.0 min"},
        {"skills": "1.1 - APT-AAA\n1.2 - MAT-MAA, MAT-MAB\n1.3 - MAT-MAA\n"},
        {"skills": "1.1 - NOP-NOP\n1.2 - MAT-MAA, MAT-MAB\n"},
        {"answers_ta": "1.1 - 3\n"},
        {"answers": "1.1 - 3\n1.2 - 2, \n"},
        {"answers_ta": "1.1 - 3\n1.2 - 2\n"},
    ],
)
def test_every_question_level_error_points_to_a_file_and_line(override: dict[str, str]) -> None:
    plan = build_plan(bank(**override), FakeImages())

    assert plan.errors
    assert all(issue.line is not None for issue in plan.errors), errors(plan)


def test_a_missing_image_points_to_the_answer_line() -> None:
    plan = build_plan(bank(), FakeImages(missing={("si", "1.2")}))

    [issue] = plan.errors
    assert (issue.source, issue.line, issue.question_id) == ("answers-1.md", 2, "1.2")
