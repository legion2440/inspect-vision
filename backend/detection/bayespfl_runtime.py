"""Pinned Bayes-PFL inference source installer and integrity checks."""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


BAYESPFL_SOURCE_COMMIT = "8f155a07e734913e021c33c469f16a1f75c60e5d"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BAYESPFL_RUNTIME_DIR = REPOSITORY_ROOT / "backend/detection/third_party/bayespfl/runtime"


@dataclass(frozen=True, slots=True)
class RuntimeSourceFile:
    path: str
    git_blob_sha1: str

    @property
    def download_url(self) -> str:
        return (
            "https://raw.githubusercontent.com/xiaozhen228/Bayes-PFL/"
            f"{BAYESPFL_SOURCE_COMMIT}/{self.path}"
        )


RUNTIME_SOURCE_FILES: tuple[RuntimeSourceFile, ...] = (
    RuntimeSourceFile("models/VPB.py", "007166e3b1d733da05b16efa4d67a29640051c51"),
    RuntimeSourceFile("models/PFL.py", "cc7f888300b531695c09c088ef7d22c07dc2ff0c"),
    RuntimeSourceFile("models/flows.py", "5a6a33f8c52ffc5da3756e19de3980605decabbb"),
    RuntimeSourceFile("models/model_CLIP.py", "a556f40aa8a1386f94f0a451e03db19697129183"),
    RuntimeSourceFile("models/transformer.py", "800c1c942c21169dbc863dd3113e56c88bf53c8f"),
    RuntimeSourceFile("models/simple_tokenizer.py", "75eba4437a2043ef1b258f14cf013db406aa87a2"),
    RuntimeSourceFile(
        "models/bpe_simple_vocab_16e6.txt.gz",
        "7b5088a527f720063f044eb928eee315f63b2fc0",
    ),
)

DownloadOpener = Callable[[str], BinaryIO]


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _file_matches(path: Path, expected_sha1: str) -> bool:
    if not path.is_file():
        return False
    return _git_blob_sha1(path.read_bytes()) == expected_sha1


def verify_bayespfl_runtime(runtime_dir: Path = BAYESPFL_RUNTIME_DIR) -> None:
    """Require the exact source blobs pinned from the selected upstream commit."""

    runtime_dir = runtime_dir.resolve()
    for source in RUNTIME_SOURCE_FILES:
        path = runtime_dir / source.path
        if not _file_matches(path, source.git_blob_sha1):
            raise FileNotFoundError(
                "Bayes-PFL runtime source is missing or failed integrity checks: "
                f"{source.path}"
            )


def _default_opener(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "Inspect-Vision/1.0"})
    return urllib.request.urlopen(request, timeout=60)


def install_bayespfl_runtime(
    runtime_dir: Path = BAYESPFL_RUNTIME_DIR,
    *,
    opener: DownloadOpener = _default_opener,
) -> tuple[Path, ...]:
    """Install exact upstream inference files without requiring an external Git checkout."""

    runtime_dir = runtime_dir.resolve()
    installed: list[Path] = []
    for source in RUNTIME_SOURCE_FILES:
        target = runtime_dir / source.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if _file_matches(target, source.git_blob_sha1):
            installed.append(target)
            continue

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f"{target.name}.",
                suffix=".part",
                dir=target.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                with closing(opener(source.download_url)) as response:
                    while chunk := response.read(1024 * 1024):
                        temporary_file.write(chunk)

            payload = temporary_path.read_bytes()
            if _git_blob_sha1(payload) != source.git_blob_sha1:
                raise ValueError(
                    "Downloaded Bayes-PFL runtime source failed Git blob verification: "
                    f"{source.path}"
                )
            os.replace(temporary_path, target)
            temporary_path = None
            installed.append(target)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    verify_bayespfl_runtime(runtime_dir)
    return tuple(installed)
