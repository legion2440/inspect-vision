from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.storage.media import MediaStore
from backend.storage.repository import SQLiteInspectionRepository
from backend.storage.service import InspectionDraft, InspectionStorage


def make_draft(inspection_id: str, *, clean: bool = False) -> InspectionDraft:
    defects = () if clean else (
        {
            "type": "scratches",
            "confidence": 0.9,
            "boundingBox": {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0},
        },
    )
    return InspectionDraft(
        inspection_id=inspection_id,
        timestamp=datetime(2026, 8, 3, 12, tzinfo=UTC),
        filename="safe.png",
        image_width=64,
        image_height=32,
        defects=defects,
        total_defects=len(defects),
        quality_score=100 if clean else 80,
        status="passed" if clean else "failed",
        model_id="neu-defect-yolov8",
    )


def make_storage(tmp_path: Path) -> InspectionStorage:
    return InspectionStorage(
        SQLiteInspectionRepository(tmp_path / "inspection.sqlite3"),
        MediaStore(tmp_path / "media"),
    )


def create_record(storage: InspectionStorage, inspection_id: str):
    return storage.create(
        make_draft(inspection_id),
        original_bytes=b"original bytes",
        annotated_bytes=b"annotated bytes",
        extension="png",
        media_type="image/png",
    )


def test_create_persists_byte_exact_pair_and_metadata(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    assert storage.initialize() == {"staging": 0, "quarantine": 0, "orphans": 0}

    record = create_record(storage, "insp_exact")

    assert storage.get(record.inspection_id) == record
    assert storage.read_media(record) == (b"original bytes", b"annotated bytes")
    assert record.original_media_path == "original/insp_exact.png"
    assert record.annotated_media_path == "annotated/insp_exact.png"


def test_delete_removes_metadata_and_media(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    storage.initialize()
    record = create_record(storage, "insp_delete")

    assert storage.delete(record.inspection_id) == record
    assert storage.get(record.inspection_id) is None
    assert not (storage.media.root / record.original_media_path).exists()
    assert not (storage.media.root / record.annotated_media_path).exists()
    assert storage.delete(record.inspection_id) is None


def test_clear_removes_all_metadata_and_media(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    storage.initialize()
    records = [create_record(storage, "insp_a"), create_record(storage, "insp_b")]

    assert storage.clear() == 2
    assert storage.list() == []
    for record in records:
        assert not (storage.media.root / record.original_media_path).exists()
        assert not (storage.media.root / record.annotated_media_path).exists()


def test_media_promotion_failure_rolls_back_database_and_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_storage(tmp_path)
    storage.initialize()

    def fail_promotion(_staged) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(storage.media, "promote", fail_promotion)

    with pytest.raises(OSError, match="disk unavailable"):
        create_record(storage, "insp_media_failure")

    assert storage.list() == []
    assert list(storage.media.original_directory.iterdir()) == []
    assert list(storage.media.annotated_directory.iterdir()) == []
    assert list(storage.media.staging_directory.iterdir()) == []


class CommitFailingRepository(SQLiteInspectionRepository):
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.rollback()
            raise sqlite3.OperationalError("simulated commit failure")
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def test_database_commit_failure_compensates_promoted_media(tmp_path: Path) -> None:
    repository = CommitFailingRepository(tmp_path / "inspection.sqlite3")
    repository.initialize()
    storage = InspectionStorage(repository, MediaStore(tmp_path / "media"))
    storage.media.initialize()

    with pytest.raises(sqlite3.OperationalError, match="simulated commit failure"):
        create_record(storage, "insp_commit_failure")

    stable_repository = SQLiteInspectionRepository(repository.database_path)
    assert stable_repository.list() == []
    assert list(storage.media.original_directory.iterdir()) == []
    assert list(storage.media.annotated_directory.iterdir()) == []


def test_delete_commit_failure_restores_media_and_metadata(tmp_path: Path) -> None:
    stable = make_storage(tmp_path)
    stable.initialize()
    record = create_record(stable, "insp_restore")
    failing = InspectionStorage(
        CommitFailingRepository(stable.repository.database_path),
        stable.media,
    )

    with pytest.raises(sqlite3.OperationalError, match="simulated commit failure"):
        failing.delete(record.inspection_id)

    assert stable.repository.get(record.inspection_id) == record
    assert stable.read_media(record) == (b"original bytes", b"annotated bytes")


def test_initialize_reconciles_interrupted_and_orphan_media(tmp_path: Path) -> None:
    storage = make_storage(tmp_path)
    storage.initialize()
    record = create_record(storage, "insp_keep")
    (storage.media.original_directory / "orphan.png").write_bytes(b"orphan")
    (storage.media.staging_directory / "interrupted.tmp").write_bytes(b"staged")
    quarantine = storage.media.quarantine([record.annotated_media_path])
    assert quarantine.entries

    result = storage.initialize()

    assert result == {"staging": 1, "quarantine": 1, "orphans": 1}
    assert (storage.media.root / record.original_media_path).exists()
    assert (storage.media.root / record.annotated_media_path).exists()
    assert not (storage.media.original_directory / "orphan.png").exists()


def test_media_paths_reject_traversal(tmp_path: Path) -> None:
    media = MediaStore(tmp_path / "media")
    media.initialize()

    with pytest.raises(ValueError, match="relative POSIX"):
        media.read("../secret.png")


def test_get_with_media_serializes_against_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_storage(tmp_path)
    storage.initialize()
    record = create_record(storage, "insp_concurrent_detail")
    read_started = threading.Event()
    release_read = threading.Event()
    original_read = storage.media.read
    read_count = 0
    count_lock = threading.Lock()

    def blocking_read(relative_path: str) -> bytes:
        nonlocal read_count
        with count_lock:
            read_count += 1
            first_read = read_count == 1
        if first_read:
            read_started.set()
            assert release_read.wait(timeout=5.0)
        return original_read(relative_path)

    monkeypatch.setattr(storage.media, "read", blocking_read)
    with ThreadPoolExecutor(max_workers=2) as executor:
        detail_future = executor.submit(storage.get_with_media, record.inspection_id)
        assert read_started.wait(timeout=5.0)
        delete_future = executor.submit(storage.delete, record.inspection_id)
        time.sleep(0.05)
        assert not delete_future.done()
        release_read.set()
        stored = detail_future.result(timeout=5.0)
        deleted = delete_future.result(timeout=5.0)

    assert stored == (record, b"original bytes", b"annotated bytes")
    assert deleted == record
    assert storage.get(record.inspection_id) is None
