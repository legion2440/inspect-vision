from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from scripts.install_selected_model import install_selected_model, load_selected_model


class DownloadResponse(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def write_manifest(path: Path, payload: bytes) -> None:
    revision = "a" * 40
    path.write_text(
        json.dumps(
            {
                "selectedModelId": "selected",
                "models": [
                    {
                        "id": "selected",
                        "filename": "selected.pt",
                        "sizeBytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "source": {
                            "downloadUrl": f"https://example.test/models/{revision}/selected.pt",
                            "revision": revision,
                        },
                    },
                    {
                        "id": "alternative",
                        "filename": "alternative.pt",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_installer_downloads_only_selected_model_and_verifies_bytes(tmp_path: Path) -> None:
    payload = b"selected checkpoint bytes"
    manifest_path = tmp_path / "model-manifest.json"
    destination = tmp_path / "models"
    write_manifest(manifest_path, payload)

    target, downloaded = install_selected_model(
        manifest_path,
        destination_dir=destination,
        opener=lambda _url: DownloadResponse(payload),
    )

    assert downloaded is True
    assert target.name == "selected.pt"
    assert target.read_bytes() == payload
    assert not (destination / "alternative.pt").exists()
    assert not list(destination.glob("*.part"))

    target_again, downloaded_again = install_selected_model(
        manifest_path,
        destination_dir=destination,
        opener=lambda _url: pytest.fail("verified checkpoint must not be downloaded again"),
    )
    assert target_again == target
    assert downloaded_again is False


def test_installer_rejects_bad_hash_and_cleans_temporary_file(tmp_path: Path) -> None:
    payload = b"expected bytes"
    manifest_path = tmp_path / "model-manifest.json"
    destination = tmp_path / "models"
    write_manifest(manifest_path, payload)

    with pytest.raises(ValueError, match="SHA-256"):
        install_selected_model(
            manifest_path,
            destination_dir=destination,
            opener=lambda _url: DownloadResponse(b"wrong payload".ljust(len(payload), b"!")),
        )

    assert not (destination / "selected.pt").exists()
    assert not list(destination.glob("*.part"))


def test_installer_rejects_actual_size_mismatch(tmp_path: Path) -> None:
    payload = b"expected bytes"
    manifest_path = tmp_path / "model-manifest.json"
    destination = tmp_path / "models"
    write_manifest(manifest_path, payload)
    response = DownloadResponse(payload[:-1])
    response.headers = {}

    with pytest.raises(ValueError, match="size"):
        install_selected_model(
            manifest_path,
            destination_dir=destination,
            opener=lambda _url: response,
        )

    assert not (destination / "selected.pt").exists()
    assert not list(destination.glob("*.part"))


def test_selected_download_url_must_include_pinned_revision(tmp_path: Path) -> None:
    payload = b"checkpoint"
    manifest_path = tmp_path / "model-manifest.json"
    write_manifest(manifest_path, payload)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["models"][0]["source"]["downloadUrl"] = "https://example.test/latest/model.pt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match="pinned revision"):
        load_selected_model(manifest_path)
