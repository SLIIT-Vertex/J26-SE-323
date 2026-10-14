from app.knowledge_tracing.application.question_files import (
    parse_answers,
    parse_difficulty,
    parse_skill_map,
    parse_skill_nodes,
)


def test_answers_with_and_without_space_after_dash() -> None:
    parsed = parse_answers("1.1 -3\r\n1.2 - (ii)\n\n4.8 - iii  \n")

    assert {k: v.raw_key for k, v in parsed.entries.items()} == {
        "1.1": "3",
        "1.2": "(ii)",
        "4.8": "iii",
    }
    assert parsed.issues == []


def test_answers_report_line_numbers() -> None:
    parsed = parse_answers("1.1 - 3\nnot a line\n1.1 - 4\n1.3 -\n")

    by_line = {issue.line: issue.message for issue in parsed.issues}
    assert "not '<id> - <answer>'" in by_line[2]
    assert "duplicate" in by_line[3]
    assert "empty answer" in by_line[4] or "<id> - <answer>" in by_line[4]
    assert list(parsed.entries) == ["1.1"]


def test_skill_map_one_and_two_skills() -> None:
    parsed = parse_skill_map("3.1 - APT-VIS\n4.20 - LAN-CMP, LAN-ORT\n")

    assert parsed.entries["3.1"].skills == ("APT-VIS",)
    assert parsed.entries["4.20"].skills == ("LAN-CMP", "LAN-ORT")


def test_skill_map_rejects_bad_code() -> None:
    parsed = parse_skill_map("1.1 - APT-VIS\n1.2 - apt-pat\n")

    assert [i.line for i in parsed.issues] == [2]


def test_difficulty_entries_on_one_line() -> None:
    text = (
        "1.1 - APT-VIS: Easy | 1.0 min   1.2 - APT-PAT: Medium | 1.5 mins   "
        "4.20 - LAN-CMP, LAN-ORT: Hard / Medium | 3.0 / 1.5 mins"
    )
    parsed = parse_difficulty(text)

    assert parsed.issues == []
    assert parsed.entries["1.1"].difficulty == "easy"
    assert parsed.entries["1.1"].est_seconds == 60
    assert parsed.entries["1.2"].est_seconds == 90
    two = parsed.entries["4.20"]
    assert two.skills == ("LAN-CMP", "LAN-ORT")
    assert two.difficulty == "hard"
    assert two.est_seconds == 270


def test_difficulty_without_dash_is_accepted() -> None:
    assert parse_difficulty("3.1 APT-VIS: Easy | 1.0 min").entries["3.1"].skills == ("APT-VIS",)


def test_difficulty_reports_unreadable_text() -> None:
    parsed = parse_difficulty("1.1 - APT-VIS: Easy | 1.0 min   garbage here")

    assert "1.1" in parsed.entries
    assert any("not a difficulty entry" in i.message for i in parsed.issues)


def test_difficulty_mismatched_counts() -> None:
    parsed = parse_difficulty("4.20 - LAN-CMP, LAN-ORT: Hard | 3.0 mins")

    assert parsed.entries == {}
    assert any("2 skills but 1" in i.message for i in parsed.issues)


def test_skill_nodes_table() -> None:
    text = """# Skill nodes

| Domain Tag | Skill ID | Skill Name (English) | Sinhala Designation | Description / Scope |
|---|---|---|---|---|
| Domain 1: General Intelligence |  |  |  |  |
| APT | APT-PAT | Pattern Recognition & Series | රටා | Identifying motifs. |
| MAT | MAT-NUM | Number Concept | සංඛ්‍යා | Reading numbers. |
"""
    nodes, issues = parse_skill_nodes(text)

    assert issues == []
    assert [(n.code, n.area) for n in nodes] == [("APT-PAT", "APT"), ("MAT-NUM", "MAT")]
    assert nodes[0].name_si == "රටා"


def test_skill_nodes_rejects_wrong_area_and_duplicates() -> None:
    nodes, issues = parse_skill_nodes(
        "| APT | MAT-PAT | x | y | z |\n| APT | APT-PAT | x | y | z |\n| APT | APT-PAT | x | y | z |\n"
    )

    assert [n.code for n in nodes] == ["APT-PAT"]
    assert len(issues) == 2
