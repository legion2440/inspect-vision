"""Install registered model artifacts and pinned runtime sources."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.utils.model_loader import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_MODELS_DIRECTORY,
    ModelArtifactSpec,
    ModelRegistry,
    ModelSpec,
)


DownloadOpener = Callable[[str], BinaryIO]


@dataclass(frozen=True, slots=True)
class InstallResult:
    model: ModelSpec
    artifact: ModelArtifactSpec
    path: Path
    downloaded: bool


class ArtifactInstallError(ValueError):
    """Raised with a user-facing manual-install fallback."""


def verify_artifact(path: Path, artifact: ModelArtifactSpec) -> bool:
    if not path.is_file() or path.stat().st_size != artifact.size_bytes:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as checkpoint_file:
        for chunk in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == artifact.sha256


def _default_opener(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "Inspect-Vision/1.0"})
    return urllib.request.urlopen(request, timeout=60)


def requested_models(
    registry: ModelRegistry,
    *,
    model_id: str | None = None,
    install_all: bool = False,
) -> tuple[ModelSpec, ...]:
    if model_id is not None and install_all:
        raise ValueError("--model and --all are mutually exclusive")
    if install_all:
        return registry.exposed_models
    return (registry.get(model_id),)


def _manual_install_message(
    artifact: ModelArtifactSpec,
    target_path: Path,
    error: Exception,
) -> str:
    return "\n".join(
        [
            f"Could not install artifact {artifact.artifact_id}: {error}",
            "Manual fallback:",
            f"  source: {artifact.source.download_url}",
            f"  save as: {target_path}",
            f"  expected size: {artifact.size_bytes} bytes",
            f"  expected SHA-256: {artifact.sha256}",
        ]
    )


def install_artifact(
    artifact: ModelArtifactSpec,
    *,
    destination_dir: Path,
    opener: DownloadOpener = _default_opener,
) -> tuple[Path, bool]:
    destination_dir = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    target_path = destination_dir / artifact.filename
    if verify_artifact(target_path, artifact):
        return target_path, False

    temporary_path: Path | None = None
    try:
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f"{artifact.filename}.",
                suffix=".part",
                dir=destination_dir,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                digest = hashlib.sha256()
                downloaded_size = 0
                with closing(opener(artifact.source.download_url)) as response:
                    headers = getattr(response, "headers", {})
                    content_type = str(headers.get("Content-Type", "")).casefold()
                    if "text/html" in content_type:
                        raise ValueError("download source returned HTML instead of model bytes")
                    content_length = headers.get("Content-Length")
                    if content_length is not None and int(content_length) != artifact.size_bytes:
                        raise ValueError("download Content-Length does not match model manifest")
                    while chunk := response.read(1024 * 1024):
                        downloaded_size += len(chunk)
                        if downloaded_size > artifact.size_bytes:
                            raise ValueError("downloaded artifact exceeds model manifest size")
                        digest.update(chunk)
                        temporary_file.write(chunk)

            if downloaded_size != artifact.size_bytes:
                raise ValueError("downloaded artifact size does not match model manifest")
            if digest.hexdigest() != artifact.sha256:
                raise ValueError("downloaded artifact SHA-256 does not match model manifest")
            os.replace(temporary_path, target_path)
            temporary_path = None
            return target_path, True
        except (OSError, TimeoutError, ValueError) as error:
            raise ArtifactInstallError(
                _manual_install_message(artifact, target_path, error)
            ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def install_models(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    destination_dir: Path = DEFAULT_MODELS_DIRECTORY,
    model_id: str | None = None,
    install_all: bool = False,
    opener: DownloadOpener = _default_opener,
) -> tuple[InstallResult, ...]:
    registry = ModelRegistry(manifest_path)
    results: list[InstallResult] = []
    for model in requested_models(registry, model_id=model_id, install_all=install_all):
        for artifact in model.artifacts:
            try:
                path, downloaded = install_artifact(
                    artifact,
                    destination_dir=destination_dir,
                    opener=opener,
                )
            except ArtifactInstallError as error:
                raise ArtifactInstallError(
                    f"{error}\n  retry: python scripts/install_models.py --model {model.model_id}"
                ) from error
            results.append(InstallResult(model, artifact, path, downloaded))
        if model.backend == "bayespfl":
            from backend.detection.bayespfl_runtime import install_bayespfl_runtime

            install_bayespfl_runtime(opener=opener)
    return tuple(results)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to model-manifest.json.",
    )
    parser.add_argument(
        "--destination-dir",
        type=Path,
        default=DEFAULT_MODELS_DIRECTORY,
        help="Directory for untracked model artifacts.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--model", dest="model_id", help="Install one model ID.")
    selection.add_argument(
        "--all",
        dest="install_all",
        action="store_true",
        help="Install all exposed models (hidden candidates require --model).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        results = install_models(
            args.manifest,
            destination_dir=args.destination_dir,
            model_id=args.model_id,
            install_all=args.install_all,
        )
    except ArtifactInstallError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    for result in results:
        action = "installed" if result.downloaded else "already verified"
        print(
            f"[OK] {result.model.model_id}/{result.artifact.artifact_id} "
            f"{action}: {result.path}"
        )
    installed_models = {result.model.model_id for result in results}
    if "bayespfl-general-v1" in installed_models:
        print("[OK] bayespfl-general-v1/runtime sources verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
