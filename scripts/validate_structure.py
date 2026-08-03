"""Validate the repository scaffold, JSON readability, and LF policy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRECTORIES = (
    "backend",
    "backend/routes",
    "backend/detection",
    "backend/storage",
    "backend/models",
    "backend/samples",
    "docs",
    "docs/evidence",
    "docs/generated",
    "frontend",
    "frontend/src",
    "frontend/tests",
    "schemas",
    "scripts",
    "shared",
)

REQUIRED_FILES = (
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "Makefile",
    "README.md",
    "dependency-graph.json",
    "module-map.json",
    "docs/api-contract.md",
    "docs/audit-evidence.md",
    "docs/env-model-contract.md",
    "docs/project-status.json",
    "docs/generated/dependency-graph.md",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/routeTree.gen.js",
    "frontend/tests/utils.test.js",
    "schemas/dependency-graph.schema.json",
    "schemas/module-map.schema.json",
    "scripts/generate_dependency_graph.py",
    "scripts/show_status.py",
    "scripts/validate.py",
    "scripts/validate_architecture.py",
    "scripts/validate_structure.py",
)

JSON_FILES = (
    "dependency-graph.json",
    "module-map.json",
    "docs/project-status.json",
    "frontend/package.json",
    "frontend/package-lock.json",
    "schemas/dependency-graph.schema.json",
    "schemas/module-map.schema.json",
)

TEXT_SUFFIXES = {
    ".css",
    ".env",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {"Makefile", ".env.example", ".gitattributes", ".gitignore"}
SKIPPED_DIRECTORIES = {".git", "node_modules", "dist", ".vite", "__pycache__"}


def _is_skipped(path: Path) -> bool:
    return any(part in SKIPPED_DIRECTORIES for part in path.parts)


def main() -> int:
    errors: list[str] = []

    for relative_path in REQUIRED_DIRECTORIES:
        if not (REPOSITORY_ROOT / relative_path).is_dir():
            errors.append(f"Missing required directory: {relative_path}")

    for relative_path in REQUIRED_FILES:
        if not (REPOSITORY_ROOT / relative_path).is_file():
            errors.append(f"Missing required file: {relative_path}")

    for relative_path in JSON_FILES:
        path = REPOSITORY_ROOT / relative_path
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8") as json_file:
                json.load(json_file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"Invalid JSON in {relative_path}: {error}")

    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file() or _is_skipped(path.relative_to(REPOSITORY_ROOT)):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        try:
            content = path.read_bytes()
        except OSError as error:
            errors.append(f"Cannot read {path.relative_to(REPOSITORY_ROOT).as_posix()}: {error}")
            continue
        if b"\r\n" in content:
            errors.append(
                f"{path.relative_to(REPOSITORY_ROOT).as_posix()} uses CRLF; text must use LF"
            )

    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[FAIL] Structure validation found {len(errors)} issue(s).", file=sys.stderr)
        return 1

    print("[OK] Repository structure, JSON files, and LF endings are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
