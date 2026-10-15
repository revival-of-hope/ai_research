"""Enforce the inward dependency direction on the actual application sources."""

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"


def _imports(path: Path):
    relative = path.relative_to(APP).with_suffix("")
    parts = ("app", *relative.parts)
    package = ".".join(parts[:-1])
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = importlib.util.resolve_name("." * node.level + module, package)
            # `from app import infrastructure` also depends on the outer layer.
            if module == "app":
                for alias in node.names:
                    yield node.lineno, f"app.{alias.name}"
            else:
                yield node.lineno, module


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_layers_depend_only_on_inner_layers(layer: str):
    paths = sorted((APP / layer).rglob("*.py"))
    assert paths, f"The {layer} layer must contain real Python modules"
    allowed_internal = (
        ("app.domain",)
        if layer == "domain"
        else (
            "app.domain",
            "app.application",
        )
    )
    # Application services may offload synchronous work without importing HTTP,
    # ORM, persistence, or model-provider implementations.
    allowed_external = set(sys.stdlib_module_names)
    if layer == "application":
        allowed_external.add("anyio")

    violations = []
    for path in paths:
        for line, module in _imports(path):
            if module == "app" or module.startswith("app."):
                allowed = any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in allowed_internal
                )
            else:
                allowed = module.split(".")[0] in allowed_external
            if not allowed:
                violations.append(f"{path.relative_to(APP)}:{line}: {module}")

    assert not violations, "Dependencies must point inward:\n" + "\n".join(violations)
