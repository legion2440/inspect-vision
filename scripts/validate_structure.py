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
    "backend/detection/third_party/anomalyclip",
    "backend/detection/third_party/bayespfl",
    "backend/storage",
    "backend/models",
    "backend/models/config",
    "backend/samples",
    "backend/samples/demo",
    "backend/samples/provenance",
    "backend/samples/provenance/showcase",
    "backend/samples/showcase",
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
    ".python-version",
    "dependency-graph.json",
    "module-map.json",
    "pyproject.toml",
    "requirements-api.txt",
    "requirements-detection.txt",
    "backend/config.py",
    "backend/main.py",
    "backend/detection/annotation.py",
    "backend/detection/anomalyclip_backend.py",
    "backend/detection/bayespfl_backend.py",
    "backend/detection/bayespfl_runtime.py",
    "backend/detection/model-selection.json",
    "backend/detection/model_selection.py",
    "backend/detection/product_context.py",
    "backend/detection/MODEL_SELECTION.md",
    "backend/detection/third_party/anomalyclip/OPENAI-CLIP-LICENSE",
    "backend/detection/third_party/bayespfl/NOTICE.md",
    "backend/detection/quality.py",
    "backend/detection/runtime.py",
    "backend/detection/service.py",
    "backend/storage/__init__.py",
    "backend/storage/media.py",
    "backend/storage/repository.py",
    "backend/storage/service.py",
    "backend/models/model-manifest.json",
    "backend/models/config/anomalyclip-general-v1-score-calibration.json",
    "backend/models/record.py",
    "backend/routes/__init__.py",
    "backend/routes/dependencies.py",
    "backend/routes/detect.py",
    "backend/routes/export.py",
    "backend/routes/filters.py",
    "backend/routes/history.py",
    "backend/routes/images.py",
    "backend/routes/models.py",
    "backend/routes/samples.py",
    "backend/routes/serialization.py",
    "backend/routes/stream.py",
    "backend/samples/model-probe-samples.json",
    "backend/samples/demo-samples.json",
    "backend/samples/showcase-samples.json",
    "backend/samples/VISA-NOTICE.md",
    "backend/samples/provenance/candle-image_anno.csv",
    "backend/samples/provenance/capsules-image_anno.csv",
    "backend/samples/provenance/cashew-image_anno.csv",
    "backend/samples/provenance/chewinggum-image_anno.csv",
    "backend/samples/provenance/showcase/defectdet-selected-coco.json",
    "backend/samples/provenance/showcase/hu-selected-metadata.json",
    "docs/api-contract.md",
    "docs/verification.md",
    "docs/env-model-contract.md",
    "docs/evidence/inspection-service/inspection-service-acceptance.json",
    "docs/evidence/inspection-service/neu-crazing-1-annotated.png",
    "docs/evidence/inspection-service/neu-inclusion-1-annotated.png",
    "docs/evidence/inspection-service/neu-scratches-1-annotated.png",
    "docs/evidence/api-persistence/api-persistence-acceptance.json",
    "docs/evidence/api-persistence/post-inspect.json",
    "docs/evidence/api-persistence/get-history.json",
    "docs/evidence/api-persistence/get-detail.json",
    "docs/evidence/api-persistence/delete-history.json",
    "docs/evidence/api-persistence/get-history-after-delete.json",
    "docs/evidence/api-bonuses/api-bonuses-acceptance.json",
    "docs/evidence/api-bonuses/history-before-stream.json",
    "docs/evidence/api-bonuses/stream.json",
    "docs/evidence/api-bonuses/history-after-stream.json",
    "docs/evidence/api-bonuses/filtered-history.json",
    "docs/evidence/api-bonuses/filtered-export.csv",
    "docs/evidence/anomalyclip-public-api/sample-contract.json",
    "docs/evidence/anomalyclip-public-api/public-api-acceptance.json",
    "docs/evidence/demo-samples/demo-samples-acceptance.json",
    "docs/project-status.json",
    "docs/generated/dependency-graph.md",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/routeTree.gen.js",
    "frontend/tests/utils.test.js",
    "frontend/tests/models.test.js",
    "frontend/tests/samples.test.js",
    "schemas/dependency-graph.schema.json",
    "schemas/model-manifest.schema.json",
    "schemas/module-map.schema.json",
    "scripts/generate_dependency_graph.py",
    "scripts/check_frontend_dependencies.py",
    "scripts/install_models.py",
    "scripts/probe_inspection_service.py",
    "scripts/probe_api_bonuses.py",
    "scripts/probe_anomalyclip_public_api.py",
    "scripts/probe_demo_samples.py",
    "scripts/probe_api_persistence.py",
    "scripts/probe_models.py",
    "scripts/prepare_demo_samples.py",
    "scripts/show_status.py",
    "scripts/validate.py",
    "scripts/validate_model_selection.py",
    "scripts/validate_architecture.py",
    "scripts/validate_demo_samples.py",
    "scripts/validate_showcase_samples.py",
    "scripts/validate_structure.py",
    "tests/unit/history/test_repository.py",
    "tests/unit/history/test_storage_service.py",
    "tests/unit/backend_api/test_config.py",
    "tests/unit/contracts/test_records.py",
    "tests/unit/detection/test_install_models.py",
    "tests/unit/detection/test_anomalyclip_backend.py",
    "tests/unit/detection/test_bayespfl_backend.py",
    "tests/unit/detection/test_model_selection.py",
    "tests/unit/detection/test_runtime.py",
    "tests/integration/api/test_inspection_api.py",
)

JSON_FILES = (
    "dependency-graph.json",
    "module-map.json",
    "backend/models/model-manifest.json",
    "backend/detection/model-selection.json",
    "backend/models/config/anomalyclip-general-v1-score-calibration.json",
    "backend/samples/model-probe-samples.json",
    "backend/samples/demo-samples.json",
    "backend/samples/showcase-samples.json",
    "backend/samples/provenance/showcase/defectdet-selected-coco.json",
    "backend/samples/provenance/showcase/hu-selected-metadata.json",
    "docs/evidence/models/model-registry-acceptance.json",
    "docs/evidence/api-persistence/api-persistence-acceptance.json",
    "docs/evidence/api-persistence/post-inspect.json",
    "docs/evidence/api-persistence/get-history.json",
    "docs/evidence/api-persistence/get-detail.json",
    "docs/evidence/api-persistence/delete-history.json",
    "docs/evidence/api-persistence/get-history-after-delete.json",
    "docs/evidence/api-bonuses/api-bonuses-acceptance.json",
    "docs/evidence/api-bonuses/history-before-stream.json",
    "docs/evidence/api-bonuses/stream.json",
    "docs/evidence/api-bonuses/history-after-stream.json",
    "docs/evidence/api-bonuses/filtered-history.json",
    "docs/evidence/anomalyclip-public-api/sample-contract.json",
    "docs/evidence/anomalyclip-public-api/public-api-acceptance.json",
    "docs/evidence/demo-samples/demo-samples-acceptance.json",
    "docs/project-status.json",
    "frontend/package.json",
    "frontend/package-lock.json",
    "schemas/dependency-graph.schema.json",
    "schemas/model-manifest.schema.json",
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
SKIPPED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
    ".vite",
}
EXACT_UPSTREAM_DIRECTORIES = (
    Path("backend/detection/third_party/bayespfl/runtime"),
)


def _is_skipped(path: Path) -> bool:
    if any(part in SKIPPED_DIRECTORIES for part in path.parts):
        return True
    return any(
        path == directory or directory in path.parents
        for directory in EXACT_UPSTREAM_DIRECTORIES
    )


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
