"""Validate module ownership, path statuses, dependency rules, and status metadata."""

from __future__ import annotations

import ast
import csv
import hashlib
import io
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


def _primary_artifact(model: dict[str, Any]) -> dict[str, Any]:
    artifacts = model.get("artifacts", [])
    return artifacts[0] if isinstance(artifacts, list) and artifacts else {}


def _ultralytics_config(model: dict[str, Any]) -> dict[str, Any]:
    config = model.get("backendConfig", {})
    return config if model.get("backend") == "ultralytics" and isinstance(config, dict) else {}


def _valid_repository_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value == path.as_posix()


def _source_hash_exists_in_history(relative_path: str, expected_hash: str) -> bool:
    path = REPOSITORY_ROOT / relative_path
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash:
        return True
    revisions = subprocess.run(
        ["git", "rev-list", "HEAD", "--", relative_path],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if revisions.returncode != 0:
        return False
    for revision in revisions.stdout.splitlines():
        blob = subprocess.run(
            ["git", "show", f"{revision}:{relative_path}"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == expected_hash:
            return True
    return False


def _check_historical_source_files(
    label: str,
    evidence: dict[str, Any],
    errors: list[str],
) -> dict[str, str]:
    source_files = evidence.get("sourceFiles")
    if not isinstance(source_files, dict) or not source_files:
        errors.append(f"{label} evidence must record sourceFiles hashes")
        return {}
    valid: dict[str, str] = {}
    for relative_path, expected_hash in source_files.items():
        if not _valid_repository_path(relative_path):
            errors.append(f"{label} evidence has invalid source path: {relative_path!r}")
            continue
        if not isinstance(expected_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_hash
        ):
            errors.append(f"{label} evidence has invalid source hash: {relative_path}")
            continue
        if not _source_hash_exists_in_history(relative_path, expected_hash):
            errors.append(
                f"{label} evidence source snapshot is absent from repository history: "
                f"{relative_path}"
            )
            continue
        valid[relative_path] = expected_hash
    return valid


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
    filenames = [
        artifact.get("filename")
        for model in models
        if isinstance(model, dict)
        for artifact in model.get("artifacts", [])
        if isinstance(artifact, dict)
    ]
    for label, values in (("IDs", model_ids), ("filenames", filenames)):
        duplicates = sorted({value for value in values if value and values.count(value) > 1})
        if duplicates:
            errors.append(f"Duplicate model {label}: {', '.join(duplicates)}")
    if manifest.get("defaultModelId") not in model_ids:
        errors.append("defaultModelId does not reference a registered model")

    profiles = manifest.get("preprocessingProfiles", {})
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = model.get("id")
        if model.get("backend") == "ultralytics":
            profile_id = _ultralytics_config(model).get("preprocessingProfile")
            if profile_id not in profiles:
                errors.append(f"Model references an unknown preprocessing profile: {model_id}")
        native_classes = set(model.get("nativeClasses", []))
        weight_classes = set(model.get("quality", {}).get("classWeights", {}))
        if not weight_classes.issubset(native_classes):
            errors.append(f"Model quality weights reference unknown classes: {model_id}")


def _check_detection_evidence(errors: list[str]) -> None:
    evidence = _load_json("docs/evidence/models/model-registry-acceptance.json")
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

    _check_historical_source_files("Detection", evidence, errors)

    manifest_models = {
        model["id"]: model
        for model in manifest.get("models", [])
        if model.get("backend") == "ultralytics"
    }
    evidence_models = evidence.get("models")
    if not isinstance(evidence_models, list):
        errors.append("Detection evidence must contain a models array")
        return
    if evidence.get("defaultModelId") != manifest.get("defaultModelId"):
        errors.append("Detection evidence default model does not match the manifest")
    if evidence.get("pipeline") != "DetectionRuntimeManager -> DetectionService":
        errors.append("Detection evidence does not use the production runtime/service pipeline")
    if evidence.get("accuracyClaim") is not False:
        errors.append("Detection evidence must not make an accuracy claim")
    if {model.get("modelId") for model in evidence_models} != set(manifest_models):
        errors.append("Detection evidence model IDs do not match the model manifest")
    for model_result in evidence_models:
        model_id = model_result.get("modelId")
        model_spec = manifest_models.get(model_id)
        if model_spec is None:
            continue
        if model_result.get("sha256") != _primary_artifact(model_spec).get("sha256"):
            errors.append(f"Detection evidence hash mismatch for model: {model_id}")
        if model_result.get("classes") != model_spec["nativeClasses"]:
            errors.append(f"Detection evidence class mismatch for model: {model_id}")
        if model_result.get("task") != "detect":
            errors.append(f"Detection evidence task mismatch for model: {model_id}")
        if not isinstance(model_result.get("totalDetections"), int) or model_result["totalDetections"] < 1:
            errors.append(f"Detection evidence has no detections for model: {model_id}")
        backend_config = _ultralytics_config(model_spec)
        if model_result.get("confidence") != backend_config.get("confidence"):
            errors.append(f"Detection evidence confidence mismatch for model: {model_id}")
        if model_result.get("preprocessingProfile") != backend_config.get(
            "preprocessingProfile"
        ):
            errors.append(f"Detection evidence preprocessing mismatch for model: {model_id}")
        if model_result.get("quality") != model_spec["quality"]:
            errors.append(f"Detection evidence quality config mismatch for model: {model_id}")
        samples = model_result.get("samples", [])
        if not isinstance(samples, list) or len(samples) < 3:
            errors.append(f"Detection evidence has too few samples for model: {model_id}")
            continue
        classes = model_spec["nativeClasses"]
        for sample in samples:
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
            if sample.get("annotationDimensionsMatchOriginal") is not True:
                errors.append(f"Detection evidence annotation dimensions mismatch: {model_id}")


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

    _check_historical_source_files("Inspection-service", evidence, errors)

    model = evidence.get("model", {})
    evidence_model_id = model.get("modelId")
    registered_model = next(
        (item for item in manifest.get("models", []) if item.get("id") == evidence_model_id),
        None,
    )
    if registered_model is None:
        errors.append("Inspection-service evidence uses an unregistered model")
        allowed_types: set[str] = set()
    else:
        if model.get("sha256") != _primary_artifact(registered_model).get("sha256"):
            errors.append("Inspection-service evidence model hash does not match the manifest")
        if model.get("classes") != registered_model.get("nativeClasses"):
            errors.append("Inspection-service evidence classes do not match the manifest")
        allowed_types = set(registered_model.get("nativeClasses", []))

    pipeline = evidence.get("pipeline", {})
    if registered_model is not None:
        registered_config = _ultralytics_config(registered_model)
        if pipeline.get("confidence") != registered_config.get("confidence"):
            errors.append("Inspection-service evidence confidence does not match the manifest")
        if pipeline.get("iou") != registered_config.get("iou"):
            errors.append("Inspection-service evidence IoU does not match the manifest")
        if pipeline.get("preprocessingProfile") != registered_config.get(
            "preprocessingProfile"
        ):
            errors.append(
                "Inspection-service evidence preprocessing profile does not match the manifest"
            )
    if pipeline.get("coordinateRestoreCount") != 1:
        errors.append("Inspection-service evidence must restore coordinates exactly once")
    expected_size = (
        registered_model.get("inputSize", {}) if registered_model is not None else {}
    )
    if pipeline.get("modelInput") != {
        "width": expected_size.get("width"),
        "height": expected_size.get("height"),
        "channels": 3,
        "dtype": "uint8",
    }:
        errors.append("Inspection-service evidence has an invalid model input contract")

    quality = evidence.get("quality", {})
    if quality.get("version") != "quality-v1" or quality.get("heuristic") is not True:
        errors.append("Inspection-service evidence has an invalid quality contract")
    if registered_model is not None:
        model_quality = registered_model.get("quality", {})
        if quality.get("defaultWeight") != model_quality.get("defaultWeight"):
            errors.append("Inspection-service evidence has an invalid default quality weight")
        if quality.get("classWeights") != model_quality.get("classWeights"):
            errors.append("Inspection-service evidence has invalid per-class quality weights")
    if evidence.get("accuracyClaim") is not False:
        errors.append("Inspection-service evidence must not claim model accuracy")

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
        if sample.get("modelId") != evidence_model_id:
            errors.append("Inspection-service evidence sample has inconsistent modelId")
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
        errors.append("Inspection-service evidence must contain real registered-model detections")


def _check_api_persistence_evidence(errors: list[str]) -> None:
    evidence = _load_json("docs/evidence/api-persistence/api-persistence-acceptance.json")
    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("API persistence evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(f"API persistence evidence sourceCommit is not an ancestor: {source_commit}")

    _check_historical_source_files("API persistence", evidence, errors)

    output_bodies: dict[str, object] = {}
    outputs = evidence.get("httpOutputs")
    if not isinstance(outputs, list) or len(outputs) != 5:
        errors.append("API persistence evidence must record five HTTP JSON outputs")
    else:
        for output in outputs:
            relative_path = output.get("path") if isinstance(output, dict) else None
            if not _valid_repository_path(relative_path):
                errors.append("API persistence evidence has an invalid HTTP output path")
                continue
            path = REPOSITORY_ROOT / relative_path
            if not path.is_file():
                errors.append(f"API persistence HTTP output is missing: {relative_path}")
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != output.get("sha256"):
                errors.append(f"API persistence HTTP output hash mismatch: {relative_path}")
            try:
                output_bodies[Path(relative_path).name] = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                errors.append(f"API persistence HTTP output is invalid JSON: {relative_path}: {error}")

    expected_sequence = [
        ("POST", "/api/inspect", 200),
        ("GET", "/api/history", 200),
        ("GET", "/api/history/{id}", 200),
        ("DELETE", "/api/history/{id}", 200),
        ("GET", "/api/history", 200),
    ]
    actual_sequence = [
        (entry.get("method"), entry.get("path"), entry.get("status"))
        for entry in evidence.get("endpointSequence", [])
        if isinstance(entry, dict)
    ]
    if actual_sequence != expected_sequence:
        errors.append("API persistence evidence endpoint sequence is incomplete")

    post = output_bodies.get("post-inspect.json")
    detail = output_bodies.get("get-detail.json")
    history = output_bodies.get("get-history.json")
    deleted = output_bodies.get("delete-history.json")
    history_after_delete = output_bodies.get("get-history-after-delete.json")
    if not isinstance(post, dict) or post != detail:
        errors.append("API persistence POST and detail outputs must match")
    else:
        inspection_id = post.get("inspectionId")
        defects = post.get("defects")
        if not isinstance(defects, list) or not defects or post.get("totalDefects") != len(defects):
            errors.append("API persistence evidence must contain real API defects")
        if post.get("status") != "failed":
            errors.append("API persistence defect result must be failed")
        if post.get("model") != {
            "id": "neu-defect-yolov8",
            "displayName": "Steel Surface",
        }:
            errors.append("API persistence evidence has an invalid model projection")
        for field in ("imageUrl", "originalImageUrl"):
            if not isinstance(post.get(field), str) or not post[field].startswith("data:image/jpeg;base64,"):
                errors.append(f"API persistence evidence has an invalid {field}")
        if (
            not isinstance(history, list)
            or len(history) != 1
            or history[0].get("inspectionId") != inspection_id
            or "imageUrl" in history[0]
            or "originalImageUrl" in history[0]
        ):
            errors.append("API persistence history output violates the summary contract")
        if deleted != {"inspectionId": inspection_id, "deleted": True}:
            errors.append("API persistence delete output violates the contract")
    if history_after_delete != []:
        errors.append("API persistence history must be empty after delete")

    sample = evidence.get("sample", {})
    persisted = evidence.get("persistenceBeforeDelete", {})
    original = persisted.get("original", {}) if isinstance(persisted, dict) else {}
    annotated = persisted.get("annotated", {}) if isinstance(persisted, dict) else {}
    if (
        persisted.get("recordExists") is not True
        or original.get("byteExactToSource") is not True
        or original.get("sha256") != sample.get("sourceSha256")
    ):
        errors.append("API persistence evidence does not prove byte-exact original storage")
    dimensions = annotated.get("dimensions", {})
    database_fields = persisted.get("databaseFields", {}) if isinstance(persisted, dict) else {}
    if dimensions != {
        "width": database_fields.get("imageWidth"),
        "height": database_fields.get("imageHeight"),
    }:
        errors.append("API persistence annotated dimensions differ from the original")
    if evidence.get("persistenceAfterDelete") != {
        "recordExists": False,
        "historyCount": 0,
        "remainingMediaFiles": [],
    }:
        errors.append("API persistence evidence does not prove delete cleanup")
    acceptance = evidence.get("acceptance", {})
    if not isinstance(acceptance, dict) or not acceptance or not all(
        value is True for value in acceptance.values()
    ):
        errors.append("API persistence acceptance flags are incomplete")


def _check_api_bonus_evidence(errors: list[str]) -> None:
    evidence = _load_json("docs/evidence/api-bonuses/api-bonuses-acceptance.json")
    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("API bonus evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(f"API bonus evidence sourceCommit is not an ancestor: {source_commit}")

    _check_historical_source_files("API bonus", evidence, errors)

    artifact_values: dict[str, object] = {}
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 5:
        errors.append("API bonus evidence must record five response artifacts")
    else:
        for artifact in artifacts:
            relative_path = artifact.get("path") if isinstance(artifact, dict) else None
            if not _valid_repository_path(relative_path):
                errors.append("API bonus evidence has an invalid artifact path")
                continue
            path = REPOSITORY_ROOT / relative_path
            if not path.is_file():
                errors.append(f"API bonus evidence artifact is missing: {relative_path}")
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.get("sha256"):
                errors.append(f"API bonus evidence artifact hash mismatch: {relative_path}")
            try:
                if path.suffix == ".json":
                    artifact_values[path.name] = json.loads(path.read_text(encoding="utf-8"))
                elif path.suffix == ".csv":
                    text_value = path.read_text(encoding="utf-8")
                    artifact_values[path.name] = list(csv.DictReader(io.StringIO(text_value)))
            except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as error:
                errors.append(f"API bonus evidence artifact is invalid: {relative_path}: {error}")

    history_before = artifact_values.get("history-before-stream.json")
    history_after = artifact_values.get("history-after-stream.json")
    stream = artifact_values.get("stream.json")
    if history_before != [] or history_after != []:
        errors.append("API bonus stream evidence must leave empty history unchanged")
    if not isinstance(stream, dict):
        errors.append("API bonus stream output is missing")
    else:
        defects = stream.get("defects")
        if (
            not isinstance(defects, list)
            or not defects
            or stream.get("totalDefects") != len(defects)
            or stream.get("status") != "failed"
        ):
            errors.append("API bonus stream output must contain real non-persisted defects")
        if not all(
            isinstance(stream.get(field), int) and stream[field] > 0
            for field in ("frameWidth", "frameHeight")
        ):
            errors.append("API bonus stream output has invalid frame dimensions")

    history = artifact_values.get("filtered-history.json")
    csv_rows = artifact_values.get("filtered-export.csv")
    if not isinstance(history, list) or not isinstance(csv_rows, list):
        errors.append("API bonus filtered history or CSV artifact is missing")
    else:
        projected_rows = [
            {
                "inspectionId": item.get("inspectionId", ""),
                "timestamp": item.get("timestamp", ""),
                "defectCount": str(item.get("totalDefects", "")),
                "types": " | ".join(
                    dict.fromkeys(
                        defect.get("type", "")
                        for defect in item.get("defects", [])
                        if isinstance(defect, dict)
                    )
                ),
                "qualityScore": str(item.get("qualityScore", "")),
                "status": item.get("status", ""),
            }
            for item in history
            if isinstance(item, dict)
        ]
        if len(history) != 2 or csv_rows != projected_rows:
            errors.append("API bonus CSV rows/order do not match filtered history semantics")

    export = evidence.get("export", {})
    if export.get("contentType") != "text/csv; charset=utf-8" or export.get(
        "contentDisposition"
    ) != 'attachment; filename="inspection-history.csv"':
        errors.append("API bonus CSV response headers violate the contract")
    if export.get("historyInspectionIds") != export.get("csvInspectionIds"):
        errors.append("API bonus CSV inspection IDs/order differ from history")

    persistence = evidence.get("persistence", {})
    if (
        persistence.get("createdInspectionCount") != 3
        or len(persistence.get("mediaFilesBeforeClear", [])) != 6
        or persistence.get("clearResponse") != {"cleared": 3}
        or persistence.get("mediaFilesAfterClear") != []
    ):
        errors.append("API bonus evidence does not prove cleanup after export setup")
    acceptance = evidence.get("acceptance", {})
    if not isinstance(acceptance, dict) or not acceptance or not all(
        value is True for value in acceptance.values()
    ):
        errors.append("API bonus acceptance flags are incomplete")


def _check_demo_sample_evidence(errors: list[str]) -> None:
    evidence = _load_json("docs/evidence/demo-samples/demo-samples-acceptance.json")
    sample_manifest = _load_json("backend/samples/demo-samples.json")
    model_manifest = _load_json("backend/models/model-manifest.json")
    if evidence.get("schemaVersion") != 2:
        errors.append("Demo sample evidence must use schemaVersion 2")
    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("Demo sample evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(f"Demo sample evidence sourceCommit is not an ancestor: {source_commit}")

    source_files = _check_historical_source_files("Demo sample", evidence, errors)

    required_bound_paths = {
        "backend/samples/demo-samples.json",
        "backend/samples/VISA-NOTICE.md",
        "scripts/prepare_demo_samples.py",
        "scripts/probe_demo_samples.py",
        "scripts/validate_demo_samples.py",
        *(item.get("path") for item in sample_manifest.get("files", [])),
        *(
            item.get("path")
            for item in sample_manifest.get("dataset", {}).get("annotationFiles", [])
        ),
    }
    if not isinstance(source_files, dict) or not required_bound_paths.issubset(source_files):
        errors.append("Demo sample evidence does not hash-bind all images and annotations")

    if evidence.get("dataset") != sample_manifest.get("dataset"):
        errors.append("Demo sample evidence provenance differs from the sample manifest")
    selected_model_id = sample_manifest.get("modelObservationContract", {}).get("modelId")
    selected_model = next(
        (
            model
            for model in model_manifest.get("models", [])
            if model.get("id") == selected_model_id
        ),
        None,
    )
    model = evidence.get("modelObservationContract", {})
    if (
        selected_model is None
        or model.get("modelId") != selected_model_id
        or model.get("modelSha256") != _primary_artifact(selected_model).get("sha256")
        or model.get("nativeClasses") != selected_model.get("nativeClasses")
        or model.get("confidenceThreshold")
        != _ultralytics_config(selected_model).get("confidence")
        or model.get("groundTruth") is not False
        or model.get("accuracyClaim") is not False
        or model != sample_manifest.get("modelObservationContract")
        or evidence.get("accuracyClaim") is not False
    ):
        errors.append("Demo sample evidence has an invalid registered-model contract")

    manifest_files = {
        item.get("id"): item
        for item in sample_manifest.get("files", [])
        if isinstance(item, dict)
    }
    samples = evidence.get("samples")
    if (
        not isinstance(samples, list)
        or len(samples) < 10
        or evidence.get("summary", {}).get("sampleCount") != len(samples)
        or {sample.get("sampleId") for sample in samples if isinstance(sample, dict)}
        != set(manifest_files)
    ):
        errors.append("Demo sample evidence does not cover the complete source-balanced manifest")
        return

    total_detections = 0
    observed_types: set[str] = set()
    ground_truth_split = {"normal": 0, "anomaly": 0}
    source_categories: set[str] = set()
    source_defect_labels: set[str] = set()
    normal_detection_counts: list[int] = []
    anomaly_detection_counts: list[int] = []
    for sample in samples:
        manifest_item = manifest_files.get(sample.get("sampleId"))
        if manifest_item is None:
            continue
        if (
            sample.get("path") != manifest_item.get("path")
            or sample.get("sha256") != manifest_item.get("sha256")
            or sample.get("dimensions") != manifest_item.get("dimensions")
            or sample.get("sourceGroundTruth") != manifest_item.get("sourceGroundTruth")
            or sample.get("modelObservation") != manifest_item.get("modelObservation")
        ):
            errors.append(f"Demo sample evidence differs from manifest: {sample.get('sampleId')}")
            continue
        ground_truth = sample["sourceGroundTruth"]
        source_label = ground_truth.get("label")
        if source_label not in ground_truth_split:
            errors.append(f"Demo sample evidence has invalid source label: {sample.get('sampleId')}")
            continue
        ground_truth_split[source_label] += 1
        source_categories.add(ground_truth.get("category"))
        source_defect_labels.update(ground_truth.get("defectLabels", []))
        observation = sample["modelObservation"]
        detections = observation.get("detections")
        if not isinstance(detections, list) or observation.get("totalDetections") != len(
            detections
        ):
            errors.append(f"Demo sample evidence has invalid model output: {sample.get('sampleId')}")
            continue
        total_detections += len(detections)
        observed_types.update(observation.get("observedNativeClasses", []))
        if source_label == "normal":
            normal_detection_counts.append(len(detections))
        else:
            anomaly_detection_counts.append(len(detections))

    expected_summary = {
        "sampleCount": len(samples),
        "groundTruthSplit": ground_truth_split,
        "sourceCategories": sorted(source_categories),
        "sourceCategoryCount": len(source_categories),
        "sourceDefectLabels": sorted(source_defect_labels, key=str.casefold),
        "sourceDefectLabelCount": len(source_defect_labels),
        "observedNativeClasses": sorted(observed_types),
        "totalModelDetections": total_detections,
        "zeroDetectionSampleCount": sum(
            count == 0 for count in [*normal_detection_counts, *anomaly_detection_counts]
        ),
        "normalModelOutcomes": {
            "sampleCount": len(normal_detection_counts),
            "zeroDetections": sum(count == 0 for count in normal_detection_counts),
            "falsePositiveSamples": sum(count > 0 for count in normal_detection_counts),
        },
        "anomalyModelOutcomes": {
            "sampleCount": len(anomaly_detection_counts),
            "zeroDetections": sum(count == 0 for count in anomaly_detection_counts),
            "samplesWithDetections": sum(count > 0 for count in anomaly_detection_counts),
        },
    }
    if evidence.get("summary") != expected_summary:
        errors.append("Demo sample evidence summary does not match source truth/model outputs")
    if (
        ground_truth_split["normal"] < 3
        or ground_truth_split["anomaly"] < 3
        or len(source_categories) < 4
        or len(source_defect_labels) < 4
    ):
        errors.append("Demo sample evidence does not prove source-ground-truth diversity")
    acceptance = evidence.get("acceptance", {})
    if not isinstance(acceptance, dict) or not acceptance or not all(
        value is True for value in acceptance.values()
    ):
        errors.append("Demo sample acceptance flags are incomplete")


def _observations_match(
    actual: object,
    expected: object,
) -> bool:
    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    if len(actual) != len(expected):
        return False
    for actual_item, expected_item in zip(actual, expected, strict=True):
        if not isinstance(actual_item, dict) or not isinstance(expected_item, dict):
            return False
        if actual_item.get("type") != expected_item.get("type"):
            return False
        confidence = actual_item.get("confidence")
        expected_confidence = expected_item.get("confidence")
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in (confidence, expected_confidence)
        ) or not math.isclose(confidence, expected_confidence, abs_tol=1e-6):
            return False
        xyxy = actual_item.get("xyxy")
        expected_xyxy = expected_item.get("xyxy")
        if (
            not isinstance(xyxy, list)
            or not isinstance(expected_xyxy, list)
            or len(xyxy) != 4
            or len(expected_xyxy) != 4
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in [*xyxy, *expected_xyxy]
            )
            or any(
                not math.isclose(value, expected_value, abs_tol=1e-4)
                for value, expected_value in zip(xyxy, expected_xyxy, strict=True)
            )
        ):
            return False
    return True


def _check_anomalyclip_public_api_evidence(errors: list[str]) -> None:
    evidence_path = "docs/evidence/anomalyclip-public-api/public-api-acceptance.json"
    contract_path = "docs/evidence/anomalyclip-public-api/sample-contract.json"
    evidence = _load_json(evidence_path)
    contract = _load_json(contract_path)
    manifest = _load_json("backend/models/model-manifest.json")
    if evidence.get("schemaVersion") != 1 or contract.get("schemaVersion") != 1:
        errors.append("AnomalyCLIP public API bundle must use schemaVersion 1")

    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("AnomalyCLIP public API evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(
                "AnomalyCLIP public API evidence sourceCommit is not an ancestor: "
                f"{source_commit}"
            )

    source_files = evidence.get("sourceFiles")
    if not isinstance(source_files, dict) or not source_files:
        errors.append("AnomalyCLIP public API evidence must bind current source files")
    else:
        for relative_path, expected_hash in source_files.items():
            if not _valid_repository_path(relative_path):
                errors.append(
                    "AnomalyCLIP public API evidence has an invalid source path: "
                    f"{relative_path!r}"
                )
                continue
            path = REPOSITORY_ROOT / relative_path
            if (
                not isinstance(expected_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash
            ):
                errors.append(
                    "AnomalyCLIP public API evidence is stale for current source file: "
                    f"{relative_path}"
                )

    contract_binding = evidence.get("sampleContract", {})
    contract_hash = hashlib.sha256(
        (REPOSITORY_ROOT / contract_path).read_bytes()
    ).hexdigest()
    if contract_binding.get("path") != contract_path or contract_binding.get(
        "sha256"
    ) != contract_hash:
        errors.append("AnomalyCLIP public API evidence has a stale sample contract")
    if contract_binding.get("qualification") != contract.get("qualification"):
        errors.append("AnomalyCLIP public API qualification provenance changed")

    groups = contract.get("models")
    if not isinstance(groups, list) or len(groups) != 1:
        errors.append("AnomalyCLIP sample contract must contain one model group")
        return
    group = groups[0]
    if group.get("modelId") != "anomalyclip-general-v1":
        errors.append("AnomalyCLIP sample contract has the wrong model ID")
    samples = group.get("samples")
    if not isinstance(samples, list):
        errors.append("AnomalyCLIP sample contract must contain samples")
        return
    sample_by_id = {
        sample.get("id"): sample for sample in samples if isinstance(sample, dict)
    }
    inspect_contract = [
        sample for sample in samples if sample.get("runtimePath") == "inspect"
    ]
    stream_contract = [
        sample for sample in samples if sample.get("runtimePath") == "stream"
    ]
    if len(inspect_contract) != 5 or len(stream_contract) != 1:
        errors.append("AnomalyCLIP bundle must bind five inspect samples and one stream sample")
    if not any(
        sample.get("sourceLabel") == "normal" and sample.get("expectedDetections") == []
        for sample in inspect_contract
    ):
        errors.append("AnomalyCLIP bundle must preserve a valid zero-detection normal case")
    cable = sample_by_id.get("mvtec-holdout-cable-bent-wire-000", {})
    if not cable.get("diagnosticLimitation"):
        errors.append("AnomalyCLIP cable observation must remain explicitly diagnostic")

    manifest_models = {
        model.get("id"): model
        for model in manifest.get("models", [])
        if isinstance(model, dict)
    }
    anomalyclip = manifest_models.get("anomalyclip-general-v1")
    if (
        not isinstance(anomalyclip, dict)
        or anomalyclip.get("exposed") is not True
        or manifest.get("defaultModelId") != "factory-defect-guard-v6-mc"
        or anomalyclip.get("nativeClasses") != ["anomaly"]
        or anomalyclip.get("backendConfig", {})
        .get("preprocessing", {})
        .get("profileId")
        != "anomalyclip-stretch"
    ):
        errors.append("Current manifest does not match the public AnomalyCLIP contract")
        return

    registry = evidence.get("registry", {})
    public_models = registry.get("publicModels")
    exposed_ids = [
        model.get("id")
        for model in manifest.get("models", [])
        if isinstance(model, dict) and model.get("exposed") is True
    ]
    if (
        registry.get("defaultModelId") != manifest.get("defaultModelId")
        or not isinstance(public_models, list)
        or [model.get("id") for model in public_models] != exposed_ids
        or len(public_models) != 4
    ):
        errors.append("AnomalyCLIP evidence has an invalid four-model registry projection")
    else:
        public_anomalyclip = public_models[-1]
        if (
            public_anomalyclip.get("description") != anomalyclip.get("description")
            or public_anomalyclip.get("preprocessingProfile") != "anomalyclip-stretch"
            or public_anomalyclip.get("classes") != ["anomaly"]
            or public_anomalyclip.get("isDefault") is not False
            or public_anomalyclip.get("installed") is not True
        ):
            errors.append("AnomalyCLIP public metadata projection is incomplete")

    integrity = registry.get("anomalyclip", {})
    artifact_records = {
        item.get("id"): item
        for item in integrity.get("artifacts", [])
        if isinstance(item, dict)
    }
    for artifact in anomalyclip.get("artifacts", []):
        record = artifact_records.get(artifact.get("id"))
        if (
            not isinstance(record, dict)
            or record.get("filename") != artifact.get("filename")
            or record.get("sizeBytes") != artifact.get("sizeBytes")
            or record.get("sha256") != artifact.get("sha256")
            or record.get("verified") is not True
        ):
            errors.append(
                "AnomalyCLIP evidence has invalid binary integrity for: "
                f"{artifact.get('id')}"
            )
    calibration_spec = anomalyclip.get("backendConfig", {}).get("scoreCalibration", {})
    calibration = integrity.get("calibration", {})
    calibration_path = calibration_spec.get("path")
    if (
        not _valid_repository_path(calibration_path)
        or calibration.get("path") != calibration_path
        or calibration.get("sizeBytes") != calibration_spec.get("sizeBytes")
        or calibration.get("sha256") != calibration_spec.get("sha256")
        or calibration.get("verified") is not True
        or hashlib.sha256((REPOSITORY_ROOT / calibration_path).read_bytes()).hexdigest()
        != calibration_spec.get("sha256")
    ):
        errors.append("AnomalyCLIP evidence has invalid tracked calibration integrity")

    inspect = evidence.get("inspect")
    if not isinstance(inspect, list) or {
        item.get("sampleId") for item in inspect if isinstance(item, dict)
    } != {sample.get("id") for sample in inspect_contract}:
        errors.append("AnomalyCLIP inspect evidence does not cover the fixed sample contract")
    else:
        for result in inspect:
            sample = sample_by_id.get(result.get("sampleId"))
            if not isinstance(sample, dict):
                continue
            dimensions = sample.get("dimensions", {})
            observation = result.get("observation")
            if (
                result.get("sourceSha256") != sample.get("sha256")
                or result.get("dimensions") != dimensions
                or result.get("model", {}).get("id") != "anomalyclip-general-v1"
                or result.get("totalDefects") != len(observation or [])
                or result.get("status")
                != ("passed" if not observation else "failed")
                or not isinstance(result.get("qualityScore"), int)
                or not 0 <= result.get("qualityScore") <= 100
                or not isinstance(result.get("latencyMs"), (int, float))
                or not math.isfinite(result.get("latencyMs"))
                or result.get("latencyMs") < 0
                or result.get("qualificationMatch") is not True
                or result.get("historyDetailMatchesPost") is not True
                or result.get("original", {}).get("byteExactToSource") is not True
                or result.get("original", {}).get("sha256") != sample.get("sha256")
                or result.get("annotated", {}).get("dimensions") != dimensions
                or not _observations_match(observation, sample.get("expectedDetections"))
            ):
                errors.append(
                    "AnomalyCLIP public inspect preservation mismatch: "
                    f"{result.get('sampleId')}"
                )
                continue
            for defect in observation:
                xyxy = defect["xyxy"]
                if not (
                    0 <= xyxy[0] < xyxy[2] <= dimensions["width"]
                    and 0 <= xyxy[1] < xyxy[3] <= dimensions["height"]
                ):
                    errors.append(
                        "AnomalyCLIP public inspect bbox is outside original coordinates: "
                        f"{result.get('sampleId')}"
                    )

    stream = evidence.get("stream", {})
    stream_sample = stream_contract[0] if stream_contract else {}
    if (
        stream.get("sampleId") != stream_sample.get("id")
        or stream.get("sourceSha256") != stream_sample.get("sha256")
        or stream.get("dimensions") != stream_sample.get("dimensions")
        or stream.get("model", {}).get("id") != "anomalyclip-general-v1"
        or stream.get("totalDefects") != len(stream.get("observation", []))
        or not _observations_match(
            stream.get("observation"), stream_sample.get("expectedDetections")
        )
        or stream.get("qualificationMatch") is not True
        or stream.get("historyUnchanged") is not True
        or stream.get("historyCountBefore") != 5
        or stream.get("historyCountAfter") != 5
    ):
        errors.append("AnomalyCLIP public stream preservation evidence is incomplete")

    history = evidence.get("history", {})
    if history != {
        "inspectionCount": 5,
        "allModelIdsPreserved": True,
        "allDetailsMatchPost": True,
    }:
        errors.append("AnomalyCLIP history/detail preservation evidence is incomplete")
    if evidence.get("accuracyClaim") is not False:
        errors.append("AnomalyCLIP public API evidence must not make an accuracy claim")
    acceptance = evidence.get("acceptance", {})
    if not isinstance(acceptance, dict) or not acceptance or not all(
        value is True for value in acceptance.values()
    ):
        errors.append("AnomalyCLIP public API acceptance flags are incomplete")

    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    tracked_weights = [
        path
        for path in tracked.stdout.splitlines()
        if Path(path).suffix.casefold() in {".pt", ".pth"}
    ]
    if tracked.returncode != 0 or tracked_weights:
        errors.append(f"Model weights must not be tracked: {tracked_weights}")


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
        _check_api_persistence_evidence(errors)
        _check_api_bonus_evidence(errors)
        _check_demo_sample_evidence(errors)
        _check_anomalyclip_public_api_evidence(errors)
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
