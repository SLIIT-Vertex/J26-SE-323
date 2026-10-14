import ast
from pathlib import Path

GAMIFICATION_ROOT = Path(__file__).parents[2] / "app" / "gamification"
BOUNDARY_LAYERS = (GAMIFICATION_ROOT / "domain", GAMIFICATION_ROOT / "application")
FORBIDDEN_PREFIXES = (
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "app.adaptive_tutor.infrastructure",
    "app.knowledge_tracing.infrastructure",
    "app.learner_state.infrastructure",
    "app.shared.learner.model",
    "app.shared.learner.repository",
)
OTHER_COMPONENT_PREFIXES = (
    "app.adaptive_tutor",
    "app.curriculum",
    "app.knowledge_tracing",
    "app.learner_state",
)
# Published application contracts that only gamification infrastructure adapters may import.
PUBLISHED_CONTRACT_MODULES = (
    "app.curriculum.application",
    "app.knowledge_tracing.application.mastery",
    "app.learner_state.application.support_need",
)
ADAPTER_LAYER = "infrastructure"
DATA_FILE_SUFFIXES = {".csv", ".json", ".jsonl", ".xlsx"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_and_application_do_not_cross_framework_or_private_boundaries() -> None:
    violations: list[str] = []
    for layer in BOUNDARY_LAYERS:
        for path in layer.rglob("*.py"):
            for module in imported_modules(path):
                if module.startswith(FORBIDDEN_PREFIXES):
                    violations.append(f"{path.relative_to(GAMIFICATION_ROOT)} -> {module}")

    assert violations == []


def _is_within(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def component_import_violations(relative_path: Path, modules: set[str]) -> list[str]:
    in_adapter_layer = relative_path.parts[:1] == (ADAPTER_LAYER,)
    violations: list[str] = []
    for module in sorted(modules):
        if not any(_is_within(module, prefix) for prefix in OTHER_COMPONENT_PREFIXES):
            continue
        is_published_contract = any(
            _is_within(module, contract) for contract in PUBLISHED_CONTRACT_MODULES
        )
        if not (in_adapter_layer and is_published_contract):
            violations.append(f"{relative_path} -> {module}")
    return violations


def test_entire_component_only_imports_permitted_shared_foundations() -> None:
    violations: list[str] = []
    for path in GAMIFICATION_ROOT.rglob("*.py"):
        violations.extend(
            component_import_violations(path.relative_to(GAMIFICATION_ROOT), imported_modules(path))
        )
    assert violations == []


def test_published_contracts_are_allowed_only_in_infrastructure_adapters() -> None:
    adapter = Path("infrastructure/gateways/knowledge_tracing_mastery.py")
    assert (
        component_import_violations(
            adapter,
            {
                "app.knowledge_tracing.application.mastery",
                "app.learner_state.application.support_need",
                "app.curriculum.application",
                "app.curriculum.application.retrieval",
            },
        )
        == []
    )
    assert component_import_violations(
        Path("domain/episode.py"), {"app.knowledge_tracing.application.mastery"}
    ) == ["domain/episode.py -> app.knowledge_tracing.application.mastery"]
    assert component_import_violations(
        Path("application/use_cases.py"), {"app.curriculum.application"}
    ) == ["application/use_cases.py -> app.curriculum.application"]


def test_other_component_internals_are_forbidden_even_in_adapters() -> None:
    adapter = Path("infrastructure/gateways/knowledge_tracing_mastery.py")
    forbidden = {
        "app.knowledge_tracing.infrastructure.db.models",
        "app.knowledge_tracing.application.question_import",
        "app.learner_state.application.service",
        "app.adaptive_tutor.application.mastery_handoff",
        "app.curriculum.infrastructure",
        "app.knowledge_tracing.application.mastery_extras",
    }
    assert len(component_import_violations(adapter, forbidden)) == len(forbidden)


def test_persistence_only_references_shared_learner_table() -> None:
    persistence = (GAMIFICATION_ROOT / "infrastructure" / "db" / "models.py").read_text()
    forbidden_tables = ('"skills.', '"questions.', '"attempts.')
    assert [table for table in forbidden_tables if table in persistence] == []


def test_domain_does_not_depend_on_application_api_or_infrastructure() -> None:
    violations: list[str] = []
    for path in (GAMIFICATION_ROOT / "domain").rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(
                (
                    "app.gamification.application",
                    "app.gamification.api",
                    "app.gamification.infrastructure",
                )
            ):
                violations.append(f"{path.relative_to(GAMIFICATION_ROOT)} -> {module}")

    assert violations == []


def test_gamification_data_is_not_stored_inside_runtime_packages() -> None:
    misplaced = [
        path.relative_to(GAMIFICATION_ROOT)
        for path in GAMIFICATION_ROOT.rglob("*")
        if path.is_file() and path.suffix in DATA_FILE_SUFFIXES
    ]
    assert misplaced == []

