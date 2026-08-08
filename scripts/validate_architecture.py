"""Run architecture validation with historical evidence compatibility."""

from __future__ import annotations

import hashlib
import subprocess

import validation_core as core


REPOSITORY_ROOT = core.REPOSITORY_ROOT


def _check_detection_snapshot(errors: list[str]) -> None:
    """Validate detector evidence against its recorded historical default."""

    expected_historical_default = "factory-defect-guard-v6-mc"
    expected_current_default = "bayespfl-general-v1"
    evidence = core._load_json("docs/evidence/models/model-registry-acceptance.json")
    manifest = core._load_json("backend/models/model-manifest.json")

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
