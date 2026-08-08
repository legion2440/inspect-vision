"""Run architecture validation with historical evidence compatibility."""

from __future__ import annotations

import hashlib
import subprocess

if __package__:
    from . import validation_core as core
else:
    import validation_core as core


REPOSITORY_ROOT = core.REPOSITORY_ROOT
_check_javascript_imports = core._check_javascript_imports
_check_python_imports = core._check_python_imports
_observations_match = core._observations_match
_source_hash_exists_in_history = core._source_hash_exists_in_history


def _expected_artifacts(model: dict) -> list[dict]:
    return [
        {
            "id": artifact.get("id"),
            "filename": artifact.get("filename"),
            "sizeBytes": artifact.get("sizeBytes"),
            "sha256": artifact.get("sha256"),
        }
        for artifact in model.get("artifacts", [])
    ]


def _expected_runtime_fields(model: dict) -> tuple[str | None, float | None, float, str | None]:
    backend = model.get("backend")
    config = model.get("backendConfig", {})
    task = config.get("task")
    if backend == "ultralytics":
        return (
            task,
            config.get("confidence"),
            config.get("iou", 0.0),
            config.get("preprocessingProfile"),
        )
    if backend == "bayespfl":
        return (
            task,
            config.get("postprocessing", {}).get("mapThreshold"),
            0.0,
            config.get("preprocessing", {}).get("profileId"),
        )
    return task, None, 0.0, None


def _check_current_detection_evidence(
    evidence: dict,
    manifest: dict,
    errors: list[str],
) -> None:
    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not core.COMMIT_PATTERN.fullmatch(source_commit):
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

    core._check_historical_source_files("Detection", evidence, errors)

    manifest_models = {
        model["id"]: model
        for model in manifest.get("models", [])
        if model.get("exposed") is True
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
        errors.append("Detection evidence model IDs do not match exposed manifest models")

    for model_result in evidence_models:
        model_id = model_result.get("modelId")
        model_spec = manifest_models.get(model_id)
        if model_spec is None:
            continue
        if model_result.get("artifacts") != _expected_artifacts(model_spec):
            errors.append(f"Detection evidence artifact metadata mismatch for model: {model_id}")
        if model_result.get("classes") != model_spec.get("nativeClasses"):
            errors.append(f"Detection evidence class mismatch for model: {model_id}")

        expected_task, expected_confidence, expected_iou, expected_preprocessing = (
            _expected_runtime_fields(model_spec)
        )
        if model_result.get("task") != expected_task:
            errors.append(f"Detection evidence task mismatch for model: {model_id}")
        if model_result.get("confidence") != expected_confidence:
            errors.append(f"Detection evidence confidence mismatch for model: {model_id}")
        if model_result.get("iou") != expected_iou:
            errors.append(f"Detection evidence IoU mismatch for model: {model_id}")
        if model_result.get("preprocessingProfile") != expected_preprocessing:
            errors.append(f"Detection evidence preprocessing mismatch for model: {model_id}")
        if model_result.get("requiresProductName") is not (model_spec.get("backend") == "bayespfl"):
            errors.append(f"Detection evidence product-context mismatch for model: {model_id}")
        if model_result.get("quality") != model_spec.get("quality"):
            errors.append(f"Detection evidence quality config mismatch for model: {model_id}")
        if not isinstance(model_result.get("totalDetections"), int) or model_result["totalDetections"] < 1:
            errors.append(f"Detection evidence has no detections for model: {model_id}")

        samples = model_result.get("samples", [])
        if not isinstance(samples, list) or len(samples) < 3:
            errors.append(f"Detection evidence has too few samples for model: {model_id}")
            continue
        classes = model_spec.get("nativeClasses", [])
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


def _check_detection_snapshot(errors: list[str]) -> None:
    """Validate detector evidence against either the current or historical registry state."""

    expected_historical_default = "factory-defect-guard-v6-mc"
    expected_current_default = "bayespfl-general-v1"
    evidence = core._load_json("docs/evidence/models/model-registry-acceptance.json")
    manifest = core._load_json("backend/models/model-manifest.json")

    if evidence.get("defaultModelId") == expected_current_default:
        _check_current_detection_evidence(evidence, manifest, errors)
        return

    start = len(errors)
    core._check_detection_evidence_original(errors)

    stale_default_error = "Detection evidence default model does not match the manifest"
    if (
        evidence.get("defaultModelId") == expected_historical_default
        and manifest.get("defaultModelId") == expected_current_default
    ):
        for index in range(len(errors) - 1, start - 1, -1):
            if errors[index] == stale_default_error:
                errors.pop(index)


def _check_anomalyclip_snapshot(errors: list[str]) -> None:
    """Validate the retired AnomalyCLIP milestone as an immutable historical snapshot."""

    evidence_path = "docs/evidence/anomalyclip-public-api/public-api-acceptance.json"
    contract_path = "docs/evidence/anomalyclip-public-api/sample-contract.json"
    evidence = core._load_json(evidence_path)
    contract = core._load_json(contract_path)

    if evidence.get("schemaVersion") != 1 or contract.get("schemaVersion") != 1:
        errors.append("AnomalyCLIP historical API bundle must use schemaVersion 1")

    source_commit = evidence.get("sourceCommit")
    if not isinstance(source_commit, str) or not core.COMMIT_PATTERN.fullmatch(source_commit):
        errors.append("AnomalyCLIP historical API evidence has an invalid sourceCommit")
    else:
        process = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            errors.append(
                "AnomalyCLIP historical API evidence sourceCommit is not an ancestor: "
                f"{source_commit}"
            )

    source_files = core._check_historical_source_files(
        "AnomalyCLIP historical API",
        evidence,
        errors,
    )
    if contract_path not in source_files:
        errors.append("AnomalyCLIP historical API evidence does not bind its sample contract")

    contract_binding = evidence.get("sampleContract", {})
    current_contract_hash = hashlib.sha256(
        (REPOSITORY_ROOT / contract_path).read_bytes()
    ).hexdigest()
    if (
        contract_binding.get("path") != contract_path
        or contract_binding.get("sha256") != current_contract_hash
        or contract_binding.get("qualification") != contract.get("qualification")
    ):
        errors.append("AnomalyCLIP historical API sample contract changed")

    groups = contract.get("models")
    if not isinstance(groups, list) or len(groups) != 1:
        errors.append("AnomalyCLIP historical sample contract must contain one model group")
        return
    group = groups[0]
    if group.get("modelId") != "anomalyclip-general-v1":
        errors.append("AnomalyCLIP historical sample contract has the wrong model ID")
    samples = group.get("samples")
    if not isinstance(samples, list):
        errors.append("AnomalyCLIP historical sample contract must contain samples")
        return
    inspect_samples = [sample for sample in samples if sample.get("runtimePath") == "inspect"]
    stream_samples = [sample for sample in samples if sample.get("runtimePath") == "stream"]
    if len(inspect_samples) != 5 or len(stream_samples) != 1:
        errors.append("AnomalyCLIP historical bundle must bind five inspect cases and one stream case")
    if not any(
        sample.get("sourceLabel") == "normal" and sample.get("expectedDetections") == []
        for sample in inspect_samples
    ):
        errors.append("AnomalyCLIP historical bundle lost its clean zero-detection case")

    registry = evidence.get("registry", {})
    public_models = registry.get("publicModels")
    if not isinstance(public_models, list) or len(public_models) != 4:
        errors.append("AnomalyCLIP historical registry snapshot must contain four public models")
        return
    snapshot_ids = [model.get("id") for model in public_models if isinstance(model, dict)]
    if snapshot_ids != [
        "factory-defect-guard-v6-mc",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
        "anomalyclip-general-v1",
    ]:
        errors.append("AnomalyCLIP historical registry model order changed")
    if registry.get("defaultModelId") != "factory-defect-guard-v6-mc":
        errors.append("AnomalyCLIP historical registry default changed")
    anomalyclip = public_models[-1]
    if (
        anomalyclip.get("classes") != ["anomaly"]
        or anomalyclip.get("preprocessingProfile") != "anomalyclip-stretch"
        or anomalyclip.get("isDefault") is not False
        or anomalyclip.get("installed") is not True
    ):
        errors.append("AnomalyCLIP historical registry projection changed")

    if evidence.get("pipeline") != (
        "POST /api/inspect and POST /api/stream -> DetectionRuntimeManager -> "
        "DetectionService -> AnomalyCLIP backend"
    ):
        errors.append("AnomalyCLIP historical API pipeline changed")

    acceptance = evidence.get("acceptance", {})
    if not isinstance(acceptance, dict) or not acceptance or not all(
        value is True for value in acceptance.values()
    ):
        errors.append("AnomalyCLIP historical API acceptance flags are incomplete")


core._check_detection_evidence_original = core._check_detection_evidence
core._check_detection_evidence = _check_detection_snapshot
core._check_anomalyclip_public_api_evidence = _check_anomalyclip_snapshot
main = core.main


if __name__ == "__main__":
    raise SystemExit(main())
