import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = REPOSITORY_ROOT / "data" / "gamification" / "grade5-curriculum-game-dataset" / "v2"
CURRICULUM_TRACE_DIR = REPOSITORY_ROOT / "data" / "curriculum" / "grade5-curriculum-trace" / "v1"
CURRICULUM_TRACE_FILES = (
    "curriculum_sources.jsonl",
    "curriculum_nodes.jsonl",
    "curriculum_terms.jsonl",
)
BUILDER_PATH = (
    REPOSITORY_ROOT
    / "tools"
    / "gamification"
    / "datasets"
    / "build_grade5_curriculum_game_dataset.py"
)
BUILDER_SPEC = importlib.util.spec_from_file_location("grade5_dataset_builder", BUILDER_PATH)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
sys.modules[BUILDER_SPEC.name] = BUILDER
BUILDER_SPEC.loader.exec_module(BUILDER)


def load_jsonl(filename: str, directory: Path = PACKAGE_DIR) -> list[dict[str, object]]:
    path = directory / filename
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_manifest_hashes_every_generated_file() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["version"] == "2.0.0"
    assert manifest["component_owner"] == "hareeshagunasekara"
    assert len(manifest["source_workbooks"]) == 5
    assert all(
        source["prepared_by"] == "hareeshagunasekara"
        for source in manifest["source_workbooks"].values()
    )
    for filename, metadata in manifest["files"].items():
        payload = (PACKAGE_DIR / filename).read_bytes()
        assert len(payload) == metadata["bytes"]
        assert hashlib.sha256(payload).hexdigest() == metadata["sha256"]


def test_curriculum_trace_is_shared_and_pinned_by_hash() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    trace = manifest["curriculum_trace_package"]
    trace_manifest = (PACKAGE_DIR / trace["path"] / "manifest.json").resolve()

    assert trace_manifest == CURRICULUM_TRACE_DIR / "manifest.json"
    assert (trace["package"], trace["version"]) == ("grade5-curriculum-trace", "1.0.0")
    assert hashlib.sha256(trace_manifest.read_bytes()).hexdigest() == trace["manifest_sha256"]
    assert not any((PACKAGE_DIR / filename).exists() for filename in CURRICULUM_TRACE_FILES)
    assert not set(CURRICULUM_TRACE_FILES) & set(manifest["files"])


def test_repackaging_existing_records_reproduces_both_packages(tmp_path: Path) -> None:
    output_dir = tmp_path / PACKAGE_DIR.relative_to(REPOSITORY_ROOT)
    curriculum_output_dir = tmp_path / CURRICULUM_TRACE_DIR.relative_to(REPOSITORY_ROOT)
    shutil.copytree(PACKAGE_DIR, output_dir)
    shutil.copytree(CURRICULUM_TRACE_DIR, curriculum_output_dir)

    datasets, source_workbooks = BUILDER.load_existing_packages(output_dir, curriculum_output_dir)
    validation_report = BUILDER.validate_datasets(datasets)
    BUILDER.write_packages(
        datasets,
        validation_report,
        BUILDER.build_readiness_report(datasets, validation_report),
        source_workbooks,
        output_dir,
        curriculum_output_dir,
    )

    for committed, rebuilt in (
        (PACKAGE_DIR, output_dir),
        (CURRICULUM_TRACE_DIR, curriculum_output_dir),
    ):
        assert sorted(path.name for path in rebuilt.iterdir()) == sorted(
            path.name for path in committed.iterdir()
        )
        for path in committed.iterdir():
            assert (rebuilt / path.name).read_bytes() == path.read_bytes(), path.name


def test_package_has_resolved_core_references_and_valid_single_select_items() -> None:
    nodes = load_jsonl("curriculum_nodes.jsonl", CURRICULUM_TRACE_DIR)
    games = load_jsonl("games.jsonl")
    items = load_jsonl("game_items.jsonl")
    item_curriculum = load_jsonl("item_curriculum_mappings.jsonl")
    skill_source_mappings = load_jsonl("skill_source_mappings.jsonl")

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
    assert all(mapping["curriculum_node_id"] in node_ids for mapping in skill_source_mappings)

    single_select = [item for item in items if item["response_format"] == "single_select"]
    assert all(len(item["options"]) == len(set(item["options"])) for item in single_select)
    assert all(set(item["correct_answers"]) <= set(item["options"]) for item in single_select)
    assert not any(
        str(option).startswith("Option ") for item in single_select for option in item["options"]
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
    assert all("knowledge_tracing_skill_id" not in mapping for mapping in item_skill_mappings)
    assert all("gamification_skill_id" in mapping for mapping in item_skill_mappings)


def test_readiness_report_matches_release_gates() -> None:
    readiness = json.loads((PACKAGE_DIR / "readiness_report.json").read_text(encoding="utf-8"))
    validation = json.loads((PACKAGE_DIR / "validation_report.json").read_text(encoding="utf-8"))
    annotations = load_jsonl("workbook_annotations.jsonl")

    assert validation["status"] == "pass"
    assert readiness["gates"]["package_integrity"]["status"] == "ready"
    assert readiness["gates"]["game_prototyping"]["status"] == "ready_with_restrictions"
    assert readiness["gates"]["misconception_inference"]["status"] == "blocked"
    assert readiness["gates"]["support_selection"]["status"] == "blocked"
    assert readiness["gates"]["independence_gain"]["status"] == "blocked"
    assert readiness["gates"]["child_facing_delivery"]["status"] == "blocked"
    assert all(annotation["instruction_authority"] == "none" for annotation in annotations)
