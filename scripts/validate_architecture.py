"""Validate module ownership, path statuses, dependency rules, and status metadata."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_FIELDS = (
    "entrypoints",
    "public_interfaces",
    "tests",
    "docs",
    "generated_artifacts",
    "owned_configuration",
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _load_json(relative_path: str) -> dict[str, Any]:
    with (REPOSITORY_ROOT / relative_path).open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{relative_path} must contain a JSON object")
    return value


def _valid_repository_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value == path.as_posix()


def _iter_references(module_map: dict[str, Any]):
    for module in module_map.get("modules", []):
        module_id = module.get("id", "<unknown>")
        for field in REFERENCE_FIELDS:
            for reference in module.get(field, []):
                yield module_id, field, reference
    for reference in module_map.get("repository_artifacts", []):
        yield "repository", "repository_artifacts", reference


def _check_module_map(module_map: dict[str, Any], errors: list[str]) -> set[str]:
    modules = module_map.get("modules", [])
    module_ids = [module.get("id") for module in modules]
    roots = [module.get("root") for module in modules]

    for label, values in (("module IDs", module_ids), ("module roots", roots)):
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            errors.append(f"Duplicate {label}: {', '.join(duplicates)}")

    for module in modules:
        module_id = module.get("id", "<unknown>")
        root = module.get("root")
        if not _valid_repository_path(root):
            errors.append(f"Module {module_id} has invalid root: {root!r}")
        elif not (REPOSITORY_ROOT / root).is_dir():
            errors.append(f"Module {module_id} root does not exist: {root}")

    owned_paths: dict[str, str] = {}
    for module_id, field, reference in _iter_references(module_map):
        if not isinstance(reference, dict):
            errors.append(f"{module_id}.{field} contains a non-object reference")
            continue
        path_value = reference.get("path")
        status = reference.get("status")
        if not _valid_repository_path(path_value):
            errors.append(f"{module_id}.{field} has invalid path: {path_value!r}")
            continue
        if status not in {"planned", "implemented", "generated"}:
            errors.append(f"{path_value} has invalid status: {status!r}")
            continue
        path = REPOSITORY_ROOT / path_value
        if status in {"implemented", "generated"} and not path.exists():
            errors.append(f"{path_value} is marked {status} but does not exist")
        if status == "generated":
            generator = reference.get("generator")
            sources = reference.get("sources")
            if not _valid_repository_path(generator) or not (REPOSITORY_ROOT / generator).is_file():
                errors.append(f"Generated path {path_value} has an invalid generator: {generator!r}")
            if not isinstance(sources, list) or not sources:
                errors.append(f"Generated path {path_value} must name at least one source")
            else:
                for source in sources:
                    if not _valid_repository_path(source) or not (REPOSITORY_ROOT / source).exists():
                        errors.append(f"Generated path {path_value} has invalid source: {source!r}")
        if field in {"generated_artifacts", "owned_configuration"}:
            previous = owned_paths.get(path_value)
            if previous and previous != module_id:
                errors.append(f"Owned path {path_value} belongs to both {previous} and {module_id}")
            owned_paths[path_value] = module_id

    return {value for value in module_ids if isinstance(value, str)}


def _check_cycles(graph: dict[str, Any], nodes: set[str], errors: list[str]) -> None:
    acyclic_types = set(graph.get("acyclic_edge_types", []))
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in graph.get("allowed_edges", []):
        if edge.get("type") in acyclic_types:
            source = edge.get("from")
            target = edge.get("to")
            if source in nodes and target in nodes:
                adjacency[source].add(target)

    visited: set[str] = set()
    active: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in active:
            start = stack.index(node)
            return [*stack[start:], node]
        if node in visited:
            return None
        active.add(node)
        stack.append(node)
        for target in sorted(adjacency[node]):
            cycle = visit(target)
            if cycle:
                return cycle
        stack.pop()
        active.remove(node)
        visited.add(node)
        return None

    for node in sorted(nodes):
        cycle = visit(node)
        if cycle:
            errors.append(f"Dependency cycle: {' -> '.join(cycle)}")
            return


def _check_graph(graph: dict[str, Any], module_ids: set[str], errors: list[str]) -> None:
    nodes = graph.get("nodes", [])
    node_set = {node for node in nodes if isinstance(node, str)}
    if node_set != module_ids:
        errors.append(
            "Dependency nodes do not match module IDs: "
            f"missing={sorted(module_ids - node_set)}, unknown={sorted(node_set - module_ids)}"
        )

    allowed_pairs: set[tuple[str, str]] = set()
    allowed_keys: set[tuple[str, str, str]] = set()
    for edge in graph.get("allowed_edges", []):
        source, target, edge_type = edge.get("from"), edge.get("to"), edge.get("type")
        if source not in node_set or target not in node_set:
            errors.append(f"Allowed edge references unknown module: {source} -> {target}")
        if source == target:
            errors.append(f"Self-dependency is not allowed: {source}")
        key = (source, target, edge_type)
        if key in allowed_keys:
            errors.append(f"Duplicate allowed edge: {source} -> {target} ({edge_type})")
        allowed_keys.add(key)
        allowed_pairs.add((source, target))

    forbidden_pairs: set[tuple[str, str]] = set()
    for edge in graph.get("forbidden_edges", []):
        pair = (edge.get("from"), edge.get("to"))
        if pair[0] not in node_set or pair[1] not in node_set:
            errors.append(f"Forbidden edge references unknown module: {pair[0]} -> {pair[1]}")
        if pair in forbidden_pairs:
            errors.append(f"Duplicate forbidden edge: {pair[0]} -> {pair[1]}")
        if pair in allowed_pairs:
            errors.append(f"Edge is both allowed and forbidden: {pair[0]} -> {pair[1]}")
        forbidden_pairs.add(pair)

    _check_cycles(graph, node_set, errors)


def _check_status(errors: list[str]) -> None:
    status = _load_json("docs/project-status.json")
    baseline = status.get("frontend_baseline_commit")
    if not isinstance(baseline, str) or not COMMIT_PATTERN.fullmatch(baseline):
        errors.append("docs/project-status.json has an invalid frontend_baseline_commit")
        return
    process = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, "HEAD"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        errors.append(f"Recorded frontend baseline is not an ancestor of HEAD: {baseline}")


def _check_model_manifest(errors: list[str]) -> None:
    manifest = _load_json("backend/models/model-manifest.json")
    schema = _load_json("schemas/model-manifest.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for validation_error in sorted(validator.iter_errors(manifest), key=lambda error: list(error.path)):
        location = ".".join(str(part) for part in validation_error.path) or "<root>"
        errors.append(f"Model manifest {location}: {validation_error.message}")

    models = manifest.get("models", [])
    model_ids = [model.get("id") for model in models if isinstance(model, dict)]
    filenames = [model.get("filename") for model in models if isinstance(model, dict)]
    for label, values in (("IDs", model_ids), ("filenames", filenames)):
        duplicates = sorted({value for value in values if value and values.count(value) > 1})
        if duplicates:
            errors.append(f"Duplicate model {label}: {', '.join(duplicates)}")
    if manifest.get("selectedModelId") not in model_ids:
        errors.append("selectedModelId does not reference a registered model")


def _check_frontend_invariants(errors: list[str]) -> None:
    route_tree = (REPOSITORY_ROOT / "frontend/src/routeTree.gen.js").read_text(encoding="utf-8")
    forbidden_types = (" as any", "declare module", "export interface", "_addFileTypes")
    for token in forbidden_types:
        if token in route_tree:
            errors.append(f"Generated JavaScript route tree contains TypeScript syntax: {token!r}")

    api_client = (REPOSITORY_ROOT / "frontend/src/utils/apiClient.js").read_text(encoding="utf-8")
    if "VITE_USE_MOCK ?? 'false'" not in api_client:
        errors.append("Frontend must default to real API mode")


def main() -> int:
    errors: list[str] = []
    try:
        module_map = _load_json("module-map.json")
        graph = _load_json("dependency-graph.json")
        module_ids = _check_module_map(module_map, errors)
        _check_graph(graph, module_ids, errors)
        _check_model_manifest(errors)
        _check_status(errors)
        _check_frontend_invariants(errors)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        errors.append(f"Cannot load architecture metadata: {error}")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[FAIL] Architecture validation found {len(errors)} issue(s).", file=sys.stderr)
        return 1

    print(f"[OK] Validated {len(module_ids)} modules, paths, graph rules, and status metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
