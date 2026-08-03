"""Validate module ownership, path statuses, dependency rules, and status metadata."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import cv2
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
JAVASCRIPT_IMPORT_PATTERN = re.compile(
    r"(?:\bfrom\s*|\bimport\s*\(?\s*)['\"](?P<path>\.{1,2}/[^'\"]+)['\"]"
)


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
        for additional_path in module.get("additional_owned_paths", []):
            if not _valid_repository_path(additional_path):
                errors.append(
                    f"Module {module_id} has invalid additional owned path: {additional_path!r}"
                )
            elif not (REPOSITORY_ROOT / additional_path).exists():
                errors.append(
                    f"Module {module_id} additional owned path does not exist: {additional_path}"
                )

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


def _owner_for_path(relative_path: PurePosixPath, module_map: dict[str, Any]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for module in module_map.get("modules", []):
        module_id = module["id"]
        owned_paths = [module["root"], *module.get("additional_owned_paths", [])]
        for owned_path in owned_paths:
            owned = PurePosixPath(owned_path)
            if relative_path == owned or owned in relative_path.parents:
                candidates.append((len(owned.parts), module_id))
    if not candidates:
        return None
    return max(candidates)[1]


def _python_module_name(relative_path: PurePosixPath) -> str:
    without_suffix = relative_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_from_import(source_module: str, module: str | None, level: int) -> str:
    if level == 0:
        return module or ""
    source_parts = source_module.split(".")
    source_path = REPOSITORY_ROOT / (source_module.replace(".", "/") + ".py")
    if not source_path.is_file():
        package_parts = source_parts
    else:
        package_parts = source_parts[:-1]
    keep = len(package_parts) - level + 1
    if keep < 0:
        return ""
    prefix = package_parts[:keep]
    return ".".join([*prefix, *(module.split(".") if module else [])])


def _check_python_imports(
    module_map: dict[str, Any],
    graph: dict[str, Any],
    errors: list[str],
) -> None:
    python_files = sorted((REPOSITORY_ROOT / "backend").rglob("*.py"))
    modules_by_name: dict[str, str] = {}
    sources: list[tuple[Path, PurePosixPath, str, str]] = []
    for path in python_files:
        if "__pycache__" in path.parts:
            continue
        relative_path = PurePosixPath(path.relative_to(REPOSITORY_ROOT).as_posix())
        owner = _owner_for_path(relative_path, module_map)
        if owner is None:
            errors.append(f"Backend Python file has no module owner: {relative_path}")
            continue
        module_name = _python_module_name(relative_path)
        modules_by_name[module_name] = owner
        sources.append((path, relative_path, module_name, owner))

    allowed_pairs = {
        (edge.get("from"), edge.get("to")) for edge in graph.get("allowed_edges", [])
    }
    known_names = sorted(modules_by_name, key=len, reverse=True)
    for path, relative_path, source_module, source_owner in sources:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative_path))
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            errors.append(f"Cannot parse backend import source {relative_path}: {error}")
            continue
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_names.append(
                    _resolve_from_import(source_module, node.module, node.level)
                )
        for imported_name in imported_names:
            target_name = next(
                (
                    known_name
                    for known_name in known_names
                    if imported_name == known_name or imported_name.startswith(known_name + ".")
                ),
                None,
            )
            if target_name is None:
                continue
            target_owner = modules_by_name[target_name]
            if source_owner != target_owner and (source_owner, target_owner) not in allowed_pairs:
                errors.append(
                    f"Forbidden Python import in {relative_path}: "
                    f"{source_owner} -> {target_owner} ({imported_name})"
                )


def _resolve_javascript_import(source_path: Path, specifier: str) -> Path | None:
    unresolved = source_path.parent / specifier
    candidates = (
        unresolved,
        Path(f"{unresolved}.js"),
        Path(f"{unresolved}.jsx"),
        unresolved / "index.js",
        unresolved / "index.jsx",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _check_javascript_imports(
    module_map: dict[str, Any],
    graph: dict[str, Any],
    errors: list[str],
) -> None:
    allowed_pairs = {
        (edge.get("from"), edge.get("to")) for edge in graph.get("allowed_edges", [])
    }
    source_files = sorted((REPOSITORY_ROOT / "frontend/src").rglob("*.js"))
    source_files.extend(sorted((REPOSITORY_ROOT / "frontend/src").rglob("*.jsx")))
    for source_path in source_files:
        relative_source = PurePosixPath(source_path.relative_to(REPOSITORY_ROOT).as_posix())
        source_owner = _owner_for_path(relative_source, module_map)
        if source_owner is None:
            errors.append(f"Frontend JavaScript file has no module owner: {relative_source}")
            continue
        content = source_path.read_text(encoding="utf-8")
        for match in JAVASCRIPT_IMPORT_PATTERN.finditer(content):
            specifier = match.group("path")
            target_path = _resolve_javascript_import(source_path, specifier)
            if target_path is None:
                errors.append(f"Unresolved JavaScript import in {relative_source}: {specifier}")
                continue
            try:
                relative_target = PurePosixPath(
                    target_path.relative_to(REPOSITORY_ROOT).as_posix()
                )
            except ValueError:
                errors.append(
                    f"JavaScript import escapes repository in {relative_source}: {specifier}"
                )
                continue
            target_owner = _owner_for_path(relative_target, module_map)
            if target_owner is None:
                errors.append(
                    f"JavaScript import target has no module owner: {relative_target}"
                )
            elif source_owner != target_owner and (source_owner, target_owner) not in allowed_pairs:
                errors.append(
                    f"Forbidden JavaScript import in {relative_source}: "
                    f"{source_owner} -> {target_owner} ({specifier})"
                )


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


def _check_detection_evidence(errors: list[str]) -> None:
    evidence = _load_json("docs/evidence/models/detection-core-acceptance.json")
    manifest = _load_json("backend/models/model-manifest.json")
    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("Detection evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(f"Detection evidence sourceCommit is not an ancestor: {source_commit}")

    source_files = evidence.get("sourceFiles")
    if not isinstance(source_files, dict) or not source_files:
        errors.append("Detection evidence must record sourceFiles hashes")
    else:
        for relative_path, expected_hash in source_files.items():
            if not _valid_repository_path(relative_path):
                errors.append(f"Detection evidence has invalid source path: {relative_path!r}")
                continue
            path = REPOSITORY_ROOT / relative_path
            if not path.is_file():
                errors.append(f"Detection evidence source file is missing: {relative_path}")
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(f"Detection evidence is stale for source file: {relative_path}")

    manifest_models = {model["id"]: model for model in manifest.get("models", [])}
    evidence_models = evidence.get("models")
    if not isinstance(evidence_models, list):
        errors.append("Detection evidence must contain a models array")
        return
    if {model.get("modelId") for model in evidence_models} != set(manifest_models):
        errors.append("Detection evidence model IDs do not match the model manifest")
    for model_result in evidence_models:
        model_id = model_result.get("modelId")
        model_spec = manifest_models.get(model_id)
        if model_spec is None:
            continue
        if model_result.get("sha256") != model_spec["sha256"]:
            errors.append(f"Detection evidence hash mismatch for model: {model_id}")
        if model_result.get("classes") != model_spec["classes"]:
            errors.append(f"Detection evidence class mismatch for model: {model_id}")
        if model_result.get("task") != "detect":
            errors.append(f"Detection evidence task mismatch for model: {model_id}")
        if not isinstance(model_result.get("totalDetections"), int) or model_result["totalDetections"] < 1:
            errors.append(f"Detection evidence has no detections for model: {model_id}")
        classes = model_spec["classes"]
        for sample in model_result.get("samples", []):
            dimensions = sample.get("dimensions", {})
            width = dimensions.get("width")
            height = dimensions.get("height")
            for detection in sample.get("detections", []):
                class_id = detection.get("classId")
                if not isinstance(class_id, int) or not 0 <= class_id < len(classes):
                    errors.append(f"Detection evidence has invalid class ID for model: {model_id}")
                    continue
                if detection.get("className") != classes[class_id]:
                    errors.append(f"Detection evidence has invalid class name for model: {model_id}")
                xyxy = detection.get("xyxy", [])
                if (
                    not isinstance(width, int)
                    or not isinstance(height, int)
                    or not isinstance(xyxy, list)
                    or len(xyxy) != 4
                    or not (0 <= xyxy[0] < xyxy[2] <= width)
                    or not (0 <= xyxy[1] < xyxy[3] <= height)
                ):
                    errors.append(f"Detection evidence has invalid bbox for model: {model_id}")


def _check_inspection_service_evidence(errors: list[str]) -> None:
    evidence_path = "docs/evidence/inspection-service/inspection-service-acceptance.json"
    evidence = _load_json(evidence_path)
    manifest = _load_json("backend/models/model-manifest.json")
    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("Inspection-service evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(
                f"Inspection-service evidence sourceCommit is not an ancestor: {source_commit}"
            )

    source_files = evidence.get("sourceFiles")
    if not isinstance(source_files, dict) or not source_files:
        errors.append("Inspection-service evidence must record sourceFiles hashes")
    else:
        for relative_path, expected_hash in source_files.items():
            if not _valid_repository_path(relative_path):
                errors.append(
                    f"Inspection-service evidence has invalid source path: {relative_path!r}"
                )
                continue
            path = REPOSITORY_ROOT / relative_path
            if not path.is_file():
                errors.append(
                    f"Inspection-service evidence source file is missing: {relative_path}"
                )
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(
                    f"Inspection-service evidence is stale for source file: {relative_path}"
                )

    selected_model_id = manifest.get("selectedModelId")
    selected_model = next(
        (model for model in manifest.get("models", []) if model.get("id") == selected_model_id),
        None,
    )
    model = evidence.get("model", {})
    if selected_model is None or model.get("modelId") != selected_model_id:
        errors.append("Inspection-service evidence does not use the selected model")
        allowed_types: set[str] = set()
    else:
        if model.get("sha256") != selected_model.get("sha256"):
            errors.append("Inspection-service evidence model hash does not match the manifest")
        if model.get("classes") != selected_model.get("classes"):
            errors.append("Inspection-service evidence classes do not match the manifest")
        expected_mapping = {name: name for name in selected_model.get("classes", [])}
        if model.get("serviceClassMapping") != expected_mapping:
            errors.append("Inspection-service evidence must use the selected identity mapping")
        allowed_types = set(expected_mapping.values())

    pipeline = evidence.get("pipeline", {})
    if pipeline.get("confidence") != 0.25:
        errors.append("Inspection-service evidence must use production confidence 0.25")
    if pipeline.get("coordinateRestoreCount") != 1:
        errors.append("Inspection-service evidence must restore coordinates exactly once")
    if pipeline.get("modelInput") != {
        "width": 640,
        "height": 640,
        "channels": 3,
        "dtype": "uint8",
    }:
        errors.append("Inspection-service evidence has an invalid model input contract")
    if pipeline.get("clahe") != {"clipLimit": 2.0, "tileGridSize": [8, 8]}:
        errors.append("Inspection-service evidence has an invalid CLAHE contract")

    quality = evidence.get("quality", {})
    if quality.get("version") != "quality-v1" or quality.get("heuristic") is not True:
        errors.append("Inspection-service evidence has an invalid quality contract")
    if quality.get("classWeights") != {
        "crazing": 1.25,
        "inclusion": 1.10,
        "patches": 0.90,
        "pitted_surface": 1.00,
        "rolled-in_scale": 1.20,
        "scratches": 0.85,
    }:
        errors.append("Inspection-service evidence has invalid quality-v1 class weights")

    samples = evidence.get("samples")
    if not isinstance(samples, list) or len(samples) < 3:
        errors.append("Inspection-service evidence must contain at least three samples")
        return
    counted_detections = 0
    for sample in samples:
        dimensions = sample.get("originalDimensions", {})
        width = dimensions.get("width")
        height = dimensions.get("height")
        defects = sample.get("defects")
        if not isinstance(width, int) or width <= 0 or not isinstance(height, int) or height <= 0:
            errors.append("Inspection-service evidence has invalid original dimensions")
            continue
        if not isinstance(defects, list):
            errors.append("Inspection-service evidence sample has invalid defects")
            continue
        counted_detections += len(defects)
        if sample.get("totalDefects") != len(defects):
            errors.append("Inspection-service evidence has inconsistent totalDefects")
        expected_status = "passed" if not defects else "failed"
        if sample.get("status") != expected_status:
            errors.append("Inspection-service evidence has inconsistent status")
        score = sample.get("qualityScore")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
            errors.append("Inspection-service evidence has invalid qualityScore")
        for defect in defects:
            if defect.get("type") not in allowed_types:
                errors.append("Inspection-service evidence contains an unmapped defect type")
            confidence = defect.get("confidence")
            box = defect.get("boundingBox", {})
            x, y = box.get("x"), box.get("y")
            box_width, box_height = box.get("width"), box.get("height")
            numeric_values = (confidence, x, y, box_width, box_height)
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in numeric_values
            ):
                errors.append("Inspection-service evidence contains a non-numeric defect")
                continue
            if not 0.0 <= confidence <= 1.0:
                errors.append("Inspection-service evidence contains invalid confidence")
            if not (0.0 <= x < x + box_width <= width and 0.0 <= y < y + box_height <= height):
                errors.append("Inspection-service evidence contains invalid original-space bbox")

        annotated = sample.get("annotatedOutput", {})
        relative_output = annotated.get("path")
        if not _valid_repository_path(relative_output):
            errors.append("Inspection-service evidence has an invalid annotated output path")
            continue
        output_path = REPOSITORY_ROOT / relative_output
        if not output_path.is_file():
            errors.append(f"Inspection-service annotated output is missing: {relative_output}")
            continue
        if hashlib.sha256(output_path.read_bytes()).hexdigest() != annotated.get("sha256"):
            errors.append(f"Inspection-service annotated output hash mismatch: {relative_output}")
        annotated_image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
        if annotated_image is None or annotated_image.shape != (height, width, 3):
            errors.append(f"Inspection-service annotated output dimensions changed: {relative_output}")

    if counted_detections < 1 or evidence.get("totalDetections") != counted_detections:
        errors.append("Inspection-service evidence must contain real selected-model detections")


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
        _check_python_imports(module_map, graph, errors)
        _check_javascript_imports(module_map, graph, errors)
        _check_model_manifest(errors)
        _check_detection_evidence(errors)
        _check_inspection_service_evidence(errors)
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
