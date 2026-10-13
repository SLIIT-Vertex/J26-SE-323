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

