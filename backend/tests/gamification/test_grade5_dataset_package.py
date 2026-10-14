import hashlib
import json
from pathlib import Path


PACKAGE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "gamification"
    / "grade5-curriculum-game-dataset"
    / "v2"
)


def load_jsonl(filename: str) -> list[dict[str, object]]:
    path = PACKAGE_DIR / filename
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_manifest_hashes_every_generated_file() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["version"] == "2.0.0"
    assert len(manifest["source_workbooks"]) == 5
    for filename, metadata in manifest["files"].items():
        payload = (PACKAGE_DIR / filename).read_bytes()
        assert len(payload) == metadata["bytes"]
        assert hashlib.sha256(payload).hexdigest() == metadata["sha256"]


def test_package_has_resolved_core_references_and_valid_single_select_items() -> None:
    nodes = load_jsonl("curriculum_nodes.jsonl")
    games = load_jsonl("games.jsonl")
    items = load_jsonl("game_items.jsonl")
    item_curriculum = load_jsonl("item_curriculum_mappings.jsonl")

    node_ids = {node["curriculum_node_id"] for node in nodes}
    game_ids = {game["game_id"] for game in games}
    item_ids = {item["item_id"] for item in items}

    assert len(nodes) == 1_884
    assert len(games) == 48
    assert len(items) == 1_920
    assert len(item_curriculum) == 4_424
    assert all(item["game_id"] in game_ids for item in items)
    assert all(set(item["curriculum_node_ids"]) <= node_ids for item in items)
    assert all(mapping["item_id"] in item_ids for mapping in item_curriculum)
    assert all(mapping["curriculum_node_id"] in node_ids for mapping in item_curriculum)

    single_select = [item for item in items if item["response_format"] == "single_select"]
    assert all(len(item["options"]) == len(set(item["options"])) for item in single_select)
    assert all(set(item["correct_answers"]) <= set(item["options"]) for item in single_select)
    assert not any(
        str(option).startswith("Option ")
        for item in single_select
        for option in item["options"]
    )
    assert sum("audio" in item["required_asset_types"] for item in items) == 120


def test_model_catalogues_are_explicitly_fail_closed_until_review() -> None:
    items = load_jsonl("game_items.jsonl")
    item_skill_mappings = load_jsonl("item_skill_mappings.jsonl")
    misconceptions = load_jsonl("misconception_catalogue.jsonl")
    structured_errors = load_jsonl("structured_error_mappings.jsonl")
    support_actions = load_jsonl("support_actions.jsonl")
    verification_pairs = load_jsonl("verification_pair_candidates.jsonl")
    review_decisions = load_jsonl("review_decisions.jsonl")

    assert misconceptions == [
        {
            "misconception_code": "unknown/other",
            "catalogue_version": "grade5-misconceptions-v2",
            "label_primary": "නොදන්නා හෝ වෙනත්",
            "label_en": "Unknown or other",
            "description": (
                "Conservative fallback when no expert-approved diagnosis is available."
            ),
            "applicable_skill_candidate_ids": [],
            "approval_status": "engineering_fallback_only",
            "child_facing_diagnosis_approved": False,
        }
    ]
    assert structured_errors == []
    assert review_decisions == []
    assert support_actions and not any(action["approved"] for action in support_actions)
    assert verification_pairs and not any(pair["approved"] for pair in verification_pairs)

    mapped_items = {mapping["item_id"] for mapping in item_skill_mappings}
    assert len(mapped_items) == 1_440
    assert len(items) - len(mapped_items) == 480


def test_readiness_report_matches_release_gates() -> None:
    readiness = json.loads(
        (PACKAGE_DIR / "readiness_report.json").read_text(encoding="utf-8")
    )
    validation = json.loads(
        (PACKAGE_DIR / "validation_report.json").read_text(encoding="utf-8")
    )
    annotations = load_jsonl("workbook_annotations.jsonl")

    assert validation["status"] == "pass"
    assert readiness["gates"]["package_integrity"]["status"] == "ready"
    assert readiness["gates"]["game_prototyping"]["status"] == "ready_with_restrictions"
    assert readiness["gates"]["misconception_inference"]["status"] == "blocked"
    assert readiness["gates"]["support_selection"]["status"] == "blocked"
    assert readiness["gates"]["independence_gain"]["status"] == "blocked"
    assert readiness["gates"]["child_facing_delivery"]["status"] == "blocked"
    assert all(annotation["instruction_authority"] == "none" for annotation in annotations)
