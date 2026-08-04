"""Install registered checkpoints with pinned size and SHA-256 verification."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from typing import BinaryIO


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.utils.model_loader import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_MODELS_DIRECTORY,
    ModelRegistry,
    ModelSpec,
)


DownloadOpener = Callable[[str], BinaryIO]


def verify_checkpoint(path: Path, spec: ModelSpec) -> bool:
    if not path.is_file() or path.stat().st_size != spec.size_bytes:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as checkpoint_file:
        for chunk in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == spec.sha256


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
        return registry.models
    return (registry.get(model_id),)


def install_model(
    spec: ModelSpec,
    *,
    destination_dir: Path,
    opener: DownloadOpener = _default_opener,
) -> tuple[Path, bool]:
    destination_dir = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    target_path = destination_dir / spec.filename
    if verify_checkpoint(target_path, spec):
        return target_path, False

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f"{spec.filename}.",
            suffix=".part",
            dir=destination_dir,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            digest = hashlib.sha256()
            downloaded_size = 0
            with closing(opener(spec.download_url)) as response:
                content_length = getattr(response, "headers", {}).get("Content-Length")
                if content_length is not None and int(content_length) != spec.size_bytes:
                    raise ValueError("download Content-Length does not match model manifest")
                while chunk := response.read(1024 * 1024):
                    downloaded_size += len(chunk)
                    if downloaded_size > spec.size_bytes:
                        raise ValueError("downloaded checkpoint exceeds model manifest size")
                    digest.update(chunk)
                    temporary_file.write(chunk)

        if downloaded_size != spec.size_bytes:
            raise ValueError("downloaded checkpoint size does not match model manifest")
        if digest.hexdigest() != spec.sha256:
            raise ValueError("downloaded checkpoint SHA-256 does not match model manifest")
        os.replace(temporary_path, target_path)
        temporary_path = None
        return target_path, True
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
) -> tuple[tuple[ModelSpec, Path, bool], ...]:
    registry = ModelRegistry(manifest_path)
    return tuple(
        (spec, *install_model(spec, destination_dir=destination_dir, opener=opener))
        for spec in requested_models(registry, model_id=model_id, install_all=install_all)
    )


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
        help="Directory for untracked checkpoint files.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--model", dest="model_id", help="Install one model ID.")
    selection.add_argument("--all", dest="install_all", action="store_true", help="Install all models.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    results = install_models(
        args.manifest,
        destination_dir=args.destination_dir,
        model_id=args.model_id,
        install_all=args.install_all,
    )
    for spec, target_path, downloaded in results:
        action = "installed" if downloaded else "already verified"
        print(f"[OK] {spec.model_id} {action}: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
