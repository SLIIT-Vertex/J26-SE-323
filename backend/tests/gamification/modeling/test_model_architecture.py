import ast
from pathlib import Path

MODELING_ROOT = Path(__file__).parents[3] / "app" / "gamification" / "modeling"
MODEL_PACKAGES = (
    "misconception_inference",
    "support_selection",
    "independence_gain",
)
FORBIDDEN_FRAMEWORK_PREFIXES = (
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "app.gamification.api",
    "app.gamification.infrastructure",
    "app.adaptive_tutor.infrastructure",
    "app.knowledge_tracing.infrastructure",
    "app.learner_state.infrastructure",
)
CONCRETE_ORCHESTRATION_MODULES = (
    "probabilistic_model",
    "deterministic_baseline",
    "reference_policy",
    "eligibility",
    "calculator",
    "validity",
)


def imported_modules_from_source(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def architecture_violations(owner: str, modules: set[str]) -> list[str]:
    violations = [module for module in modules if module.startswith(FORBIDDEN_FRAMEWORK_PREFIXES)]
    if owner in MODEL_PACKAGES:
        other_models = tuple(
            f"app.gamification.modeling.{name}" for name in MODEL_PACKAGES if name != owner
        )
        violations.extend(module for module in modules if module.startswith(other_models))
    elif owner == "shared":
        model_prefixes = tuple(f"app.gamification.modeling.{name}" for name in MODEL_PACKAGES)
        violations.extend(module for module in modules if module.startswith(model_prefixes))
    elif owner == "orchestration":
        violations.extend(
            module
            for module in modules
            if module.startswith("app.gamification.modeling.")
            and module.rsplit(".", 1)[-1] in CONCRETE_ORCHESTRATION_MODULES
        )
    return sorted(set(violations))


def dependency_cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            cycle = path[path.index(node) :] + (node,)
            rotations = [cycle[index:-1] + cycle[:index] for index in range(len(cycle) - 1)]
            cycles.add(min(rotations))
            return
        for dependency in graph.get(node, set()):
            visit(dependency, path + (node,))

    for node in graph:
        visit(node, ())
    return sorted(cycles)


def model_dependency_graph() -> dict[str, set[str]]:
    prefix = "app.gamification.modeling."
    paths = tuple(MODELING_ROOT.rglob("*.py"))
    nodes = {
        (
            ".".join(path.relative_to(MODELING_ROOT).with_suffix("").parts[:-1])
            if path.name == "__init__.py"
            else ".".join(path.relative_to(MODELING_ROOT).with_suffix("").parts)
        )
        for path in paths
    }
    graph: dict[str, set[str]] = {node: set() for node in nodes}
    for path in paths:
        node = (
            ".".join(path.relative_to(MODELING_ROOT).with_suffix("").parts[:-1])
            if path.name == "__init__.py"
            else ".".join(path.relative_to(MODELING_ROOT).with_suffix("").parts)
        )
        for imported in imported_modules_from_source(path.read_text(encoding="utf-8")):
            if imported.startswith(prefix):
                dependency = imported.removeprefix(prefix)
                if dependency in nodes and dependency != node:
                    graph[node].add(dependency)
    return graph


def test_model_package_dependency_rules() -> None:
    violations: list[str] = []
    for owner in (*MODEL_PACKAGES, "shared", "orchestration"):
        for path in (MODELING_ROOT / owner).rglob("*.py"):
            modules = imported_modules_from_source(path.read_text(encoding="utf-8"))
            for module in architecture_violations(owner, modules):
                relative_path = path.relative_to(MODELING_ROOT).as_posix()
                violations.append(f"{relative_path} -> {module}")
    assert violations == []


def test_selection_does_not_name_other_model_classes() -> None:
    banned = (
        "IndependenceGainResult",
        "RawIndependenceGainCalculator",
        "ProbabilisticMisconceptionModel",
    )
    root = MODELING_ROOT / "support_selection"
    offenders = [
        f"{path.name}:{name}"
        for path in root.rglob("*.py")
        for name in banned
        if name in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_modeling_import_graph_has_no_cycles() -> None:
    assert dependency_cycles(model_dependency_graph()) == []


def test_architecture_detector_rejects_cross_model_and_framework_imports() -> None:
    modules = imported_modules_from_source(
        "from app.gamification.modeling.support_selection.reference_policy import "
        "SafeSupportPolicy\nimport sqlalchemy\n"
    )
    assert architecture_violations("misconception_inference", modules) == [
        "app.gamification.modeling.support_selection.reference_policy",
        "sqlalchemy",
    ]


def test_cycle_detector_rejects_a_cycle() -> None:
    assert dependency_cycles({"a": {"b"}, "b": {"a"}}) == [("a", "b")]


def test_flat_model_modules_and_combined_test_are_removed() -> None:
    old_modules = (
        "features.py",
        "independence.py",
        "misconception.py",
        "offline.py",
        "pipeline.py",
        "policy.py",
        "synthetic.py",
    )
    assert [name for name in old_modules if (MODELING_ROOT / name).exists()] == []
    assert not (Path(__file__).parents[1] / "test_three_models.py").exists()
