"""Transactional coordination of SQLite metadata and filesystem media."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .media import MediaStore, QuarantinedMedia
from .repository import HistoryFilters, InspectionRecord, MediaType, SQLiteInspectionRepository, Status


@dataclass(frozen=True, slots=True)
class InspectionDraft:
    inspection_id: str
    timestamp: datetime
    filename: str
    image_width: int
    image_height: int
    defects: tuple[dict[str, Any], ...]
    total_defects: int
    quality_score: int
    status: Status
    model_id: str


class InspectionStorage:
    """Keep metadata and media consistent across normal failures and restarts."""

    def __init__(
        self,
        repository: SQLiteInspectionRepository,
        media: MediaStore,
    ) -> None:
        self.repository = repository
        self.media = media
        self._write_lock = threading.RLock()

    def initialize(self) -> dict[str, int]:
        with self._write_lock:
            self.repository.initialize()
            return self.media.reconcile(self.repository.media_paths())

    def create(
        self,
        draft: InspectionDraft,
        *,
        original_bytes: bytes,
        annotated_bytes: bytes,
        extension: str,
        media_type: MediaType,
    ) -> InspectionRecord:
        with self._write_lock:
            staged = self.media.stage_pair(
                draft.inspection_id,
                extension,
                original_bytes,
                annotated_bytes,
            )
            record = InspectionRecord(
                inspection_id=draft.inspection_id,
                timestamp=draft.timestamp,
                filename=draft.filename,
                image_width=draft.image_width,
                image_height=draft.image_height,
                defects=draft.defects,
                total_defects=draft.total_defects,
                quality_score=draft.quality_score,
                status=draft.status,
                model_id=draft.model_id,
                media_type=media_type,
                original_media_path=staged.original_relative_path,
                annotated_media_path=staged.annotated_relative_path,
            )
            promoted = False
            try:
                with self.repository.transaction() as connection:
                    self.repository.create(record, connection=connection)
                    self.media.promote(staged)
                    promoted = True
            except BaseException:
                self.media.discard_staged(staged)
                if promoted:
                    self.media.remove(
                        [record.original_media_path, record.annotated_media_path]
                    )
                raise
            return record

    def list(self, filters: HistoryFilters = HistoryFilters()) -> list[InspectionRecord]:
        return self.repository.list(filters)

    def get(self, inspection_id: str) -> InspectionRecord | None:
        return self.repository.get(inspection_id)

    def read_media(self, record: InspectionRecord) -> tuple[bytes, bytes]:
        with self._write_lock:
            return (
                self.media.read(record.original_media_path),
                self.media.read(record.annotated_media_path),
            )

    def get_with_media(
        self,
        inspection_id: str,
    ) -> tuple[InspectionRecord, bytes, bytes] | None:
        with self._write_lock:
            record = self.repository.get(inspection_id)
            if record is None:
                return None
            return (
                record,
                self.media.read(record.original_media_path),
                self.media.read(record.annotated_media_path),
            )

    def delete(self, inspection_id: str) -> InspectionRecord | None:
        with self._write_lock:
            quarantined: QuarantinedMedia | None = None
            record: InspectionRecord | None = None
            try:
                with self.repository.transaction() as connection:
                    record = self.repository.get(inspection_id, connection=connection)
                    if record is None:
                        return None
                    quarantined = self.media.quarantine(
                        [record.original_media_path, record.annotated_media_path]
                    )
                    self.repository.delete(inspection_id, connection=connection)
            except BaseException:
                if quarantined is not None:
                    self.media.restore(quarantined)
                raise
            if quarantined is not None:
                self.media.purge(quarantined)
            return record

    def clear(self) -> int:
        with self._write_lock:
            quarantined: QuarantinedMedia | None = None
            records: list[InspectionRecord] = []
            try:
                with self.repository.transaction() as connection:
                    records = self.repository.list(connection=connection)
                    relative_paths = [
                        path
                        for record in records
                        for path in (
                            record.original_media_path,
                            record.annotated_media_path,
                        )
                    ]
                    quarantined = self.media.quarantine(relative_paths)
                    self.repository.clear(connection=connection)
            except BaseException:
                if quarantined is not None:
                    self.media.restore(quarantined)
                raise
            if quarantined is not None:
                self.media.purge(quarantined)
            return len(records)
