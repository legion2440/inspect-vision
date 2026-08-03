"""Crash-recoverable filesystem lifecycle for original and annotated media."""

from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
EXTENSIONS = {"jpg", "png"}


@dataclass(frozen=True, slots=True)
class StagedMedia:
    original_staging_path: Path
    annotated_staging_path: Path
    original_relative_path: str
    annotated_relative_path: str


@dataclass(frozen=True, slots=True)
class QuarantinedMedia:
    directory: Path
    entries: tuple[tuple[str, Path], ...]


class MediaStore:
    """Store only validated relative paths beneath an application-owned root."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.original_directory = self.root / "original"
        self.annotated_directory = self.root / "annotated"
        self.staging_directory = self.root / ".staging"
        self.quarantine_directory = self.root / ".quarantine"

    def initialize(self) -> None:
        for directory in (
            self.original_directory,
            self.annotated_directory,
            self.staging_directory,
            self.quarantine_directory,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def stage_pair(
        self,
        inspection_id: str,
        extension: str,
        original_bytes: bytes,
        annotated_bytes: bytes,
    ) -> StagedMedia:
        if not SAFE_ID_PATTERN.fullmatch(inspection_id):
            raise ValueError("inspection_id contains unsafe characters")
        normalized_extension = extension.lower().lstrip(".")
        if normalized_extension not in EXTENSIONS:
            raise ValueError("extension must be jpg or png")
        if not original_bytes or not annotated_bytes:
            raise ValueError("original and annotated media must not be empty")
        self.initialize()
        token = uuid.uuid4().hex
        original_stage = self.staging_directory / f"{token}.original"
        annotated_stage = self.staging_directory / f"{token}.annotated"
        try:
            self._write_exclusive(original_stage, original_bytes)
            self._write_exclusive(annotated_stage, annotated_bytes)
        except BaseException:
            self._unlink_if_present(original_stage)
            self._unlink_if_present(annotated_stage)
            raise
        return StagedMedia(
            original_staging_path=original_stage,
            annotated_staging_path=annotated_stage,
            original_relative_path=f"original/{inspection_id}.{normalized_extension}",
            annotated_relative_path=f"annotated/{inspection_id}.{normalized_extension}",
        )

    def promote(self, staged: StagedMedia) -> None:
        destinations = (
            (staged.original_staging_path, self._resolve_relative(staged.original_relative_path)),
            (staged.annotated_staging_path, self._resolve_relative(staged.annotated_relative_path)),
        )
        promoted: list[Path] = []
        try:
            for source, destination in destinations:
                if destination.exists():
                    raise FileExistsError(f"media already exists: {destination.name}")
                os.replace(source, destination)
                promoted.append(destination)
        except BaseException:
            for path in promoted:
                self._unlink_if_present(path)
            raise

    def discard_staged(self, staged: StagedMedia) -> None:
        self._unlink_if_present(staged.original_staging_path)
        self._unlink_if_present(staged.annotated_staging_path)

    def remove(self, relative_paths: tuple[str, ...] | list[str]) -> None:
        for relative_path in relative_paths:
            self._unlink_if_present(self._resolve_relative(relative_path))

    def read(self, relative_path: str) -> bytes:
        return self._resolve_relative(relative_path).read_bytes()

    def quarantine(self, relative_paths: tuple[str, ...] | list[str]) -> QuarantinedMedia:
        self.initialize()
        directory = self.quarantine_directory / uuid.uuid4().hex
        directory.mkdir(parents=False, exist_ok=False)
        entries: list[tuple[str, Path]] = []
        try:
            for relative_path in relative_paths:
                source = self._resolve_relative(relative_path)
                if not source.exists():
                    continue
                destination = directory / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
                entries.append((relative_path, destination))
        except BaseException:
            self.restore(QuarantinedMedia(directory=directory, entries=tuple(entries)))
            raise
        return QuarantinedMedia(directory=directory, entries=tuple(entries))

    def restore(self, quarantined: QuarantinedMedia) -> None:
        for relative_path, source in reversed(quarantined.entries):
            if source.exists():
                destination = self._resolve_relative(relative_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
        self._remove_tree_if_present(quarantined.directory)

    def purge(self, quarantined: QuarantinedMedia) -> None:
        self._remove_tree_if_present(quarantined.directory)

    def reconcile(self, referenced_paths: set[str]) -> dict[str, int]:
        """Remove interrupted staging/quarantine content and unreferenced final files."""

        self.initialize()
        normalized_references = {self._relative_value(path) for path in referenced_paths}
        removed_staging = self._clear_children(self.staging_directory)
        reconciled_quarantine = 0
        for batch in self.quarantine_directory.iterdir():
            if not batch.is_dir():
                batch.unlink()
                reconciled_quarantine += 1
                continue
            for quarantined_path in sorted(batch.rglob("*")):
                if not quarantined_path.is_file():
                    continue
                relative_path = quarantined_path.relative_to(batch).as_posix()
                if relative_path in normalized_references:
                    destination = self._resolve_relative(relative_path)
                    if not destination.exists():
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(quarantined_path, destination)
            shutil.rmtree(batch)
            reconciled_quarantine += 1
        removed_orphans = 0
        for directory in (self.original_directory, self.annotated_directory):
            for path in directory.iterdir():
                if not path.is_file():
                    continue
                relative_path = path.relative_to(self.root).as_posix()
                if relative_path not in normalized_references:
                    path.unlink()
                    removed_orphans += 1
        return {
            "staging": removed_staging,
            "quarantine": reconciled_quarantine,
            "orphans": removed_orphans,
        }

    def _resolve_relative(self, relative_path: str) -> Path:
        normalized = self._relative_value(relative_path)
        candidate = (self.root / Path(*PurePosixPath(normalized).parts)).resolve()
        if self.root not in candidate.parents:
            raise ValueError("media path escapes the configured root")
        return candidate

    @staticmethod
    def _relative_value(relative_path: str) -> str:
        if not relative_path or "\\" in relative_path or ":" in relative_path:
            raise ValueError("media path must be repository-style relative POSIX")
        value = PurePosixPath(relative_path)
        if value.is_absolute() or ".." in value.parts or value.as_posix() != relative_path:
            raise ValueError("media path must be repository-style relative POSIX")
        if value.parts[0] not in {"original", "annotated"} or len(value.parts) != 2:
            raise ValueError("media path must target original/ or annotated/")
        return value.as_posix()

    @staticmethod
    def _write_exclusive(path: Path, content: bytes) -> None:
        with path.open("xb") as binary_file:
            binary_file.write(content)
            binary_file.flush()
            os.fsync(binary_file.fileno())

    @staticmethod
    def _unlink_if_present(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _remove_tree_if_present(path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)

    @classmethod
    def _clear_children(cls, directory: Path) -> int:
        count = 0
        for child in directory.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            count += 1
        return count
