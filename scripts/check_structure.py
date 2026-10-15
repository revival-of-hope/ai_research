"""Check useful architectural boundaries instead of arbitrary folder/file sizes."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"
REQUIRED = (
    "domain",
    "application/repo",
    "application/uow",
    "application/service",
    "infrastructure/repo",
    "infrastructure/uow",
    "infrastructure/agents",
    "api",
)


def main():
    problems = []
    for directory in REQUIRED:
        if not any((APP / directory).glob("*.py")):
            problems.append(f"Missing implementation: {directory}")
    for layer in ("domain", "application"):
        allowed = {"app.domain"} | (
            {"app.application"} if layer == "application" else set()
        )
        external = set(sys.stdlib_module_names) | (
            {"anyio"} if layer == "application" else set()
        )
        for path in (APP / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                names = (
                    [x.name for x in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                for name in names:
                    if name.startswith("app."):
                        valid = any(
                            name == p or name.startswith(p + ".") for p in allowed
                        )
                    else:
                        valid = name.split(".")[0] in external
                    if not valid:
                        problems.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: {name}"
                        )
    for path in APP.rglob("*.py"):
        if "app.services" in path.read_text(encoding="utf-8-sig"):
            problems.append(f"Legacy service dependency: {path.relative_to(ROOT)}")
    if problems:
        raise SystemExit("Structure check failed:\n" + "\n".join(problems))
    print("DDD structure and inward dependencies verified")


if __name__ == "__main__":
    main()
