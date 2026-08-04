"""Install the selected checkpoint declared by the tracked model manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, BinaryIO


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DownloadOpener = Callable[[str], BinaryIO]


def load_selected_model(manifest_path: Path) -> dict[str, Any]:
    """Return the selected model entry after validating install-critical fields."""

    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    selected_id = manifest.get("selectedModelId")
    matches = [model for model in manifest.get("models", []) if model.get("id") == selected_id]
    if len(matches) != 1:
        raise ValueError("selectedModelId must reference exactly one model")

    model = matches[0]
    filename = model.get("filename")
    expected_size = model.get("sizeBytes")
    expected_sha256 = model.get("sha256")
    source = model.get("source", {})
    download_url = source.get("downloadUrl")
    revision = source.get("revision")

    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        raise ValueError("selected model filename must be a safe basename")
    if not isinstance(expected_size, int) or expected_size <= 0:
        raise ValueError("selected model sizeBytes must be a positive integer")
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValueError("selected model sha256 must be a lowercase SHA-256 digest")
    if not isinstance(download_url, str) or not download_url.startswith("https://"):
        raise ValueError("selected model downloadUrl must use HTTPS")
    if not isinstance(revision, str) or not revision or revision not in download_url:
        raise ValueError("selected model downloadUrl must contain its pinned revision")
    return model


def verify_checkpoint(path: Path, *, expected_size: int, expected_sha256: str) -> bool:
    """Return whether a local checkpoint exactly matches the manifest."""

    if not path.is_file() or path.stat().st_size != expected_size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as checkpoint_file:
        for chunk in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def _default_opener(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "Inspect-Vision/1.0"})
    return urllib.request.urlopen(request, timeout=60)


def install_selected_model(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    destination_dir: Path | None = None,
    opener: DownloadOpener = _default_opener,
) -> tuple[Path, bool]:
    """Install and verify the selected model, returning path and download status."""

    manifest_path = manifest_path.resolve()
    model = load_selected_model(manifest_path)
    expected_size = model["sizeBytes"]
    expected_sha256 = model["sha256"]
    target_dir = (destination_dir or manifest_path.parent).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / model["filename"]

    if verify_checkpoint(
        target_path,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
    ):
        return target_path, False

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f"{model['filename']}.",
            suffix=".part",
            dir=target_dir,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            digest = hashlib.sha256()
            downloaded_size = 0
            with closing(opener(model["source"]["downloadUrl"])) as response:
                content_length = getattr(response, "headers", {}).get("Content-Length")
                if content_length is not None and int(content_length) != expected_size:
                    raise ValueError("download Content-Length does not match model manifest")
                while chunk := response.read(1024 * 1024):
                    downloaded_size += len(chunk)
                    if downloaded_size > expected_size:
                        raise ValueError("downloaded checkpoint exceeds manifest size")
                    digest.update(chunk)
                    temporary_file.write(chunk)

        if downloaded_size != expected_size:
            raise ValueError("downloaded checkpoint size does not match model manifest")
        if digest.hexdigest() != expected_sha256:
            raise ValueError("downloaded checkpoint SHA-256 does not match model manifest")
        os.replace(temporary_path, target_path)
        temporary_path = None
        return target_path, True
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify the checkpoint selected by model-manifest.json."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to model-manifest.json.",
    )
    args = parser.parse_args()

    target_path, downloaded = install_selected_model(args.manifest)
    action = "installed" if downloaded else "already verified"
    print(f"[OK] Selected model {action}: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
