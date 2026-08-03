"""SQLite repository for inspection metadata and server-side history filters."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal


Status = Literal["passed", "failed"]
MediaType = Literal["image/jpeg", "image/png"]


def _canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("stored timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class HistoryFilters:
    """Validated filters applied together by SQLite."""

    from_date: date | None = None
    to_date: date | None = None
    defect_type: str | None = None
    query: str | None = None

    def __post_init__(self) -> None:
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must not be after to_date")
        if self.defect_type is not None and not self.defect_type:
            raise ValueError("defect_type must be non-empty when supplied")
        if self.query is not None and not self.query.strip():
            object.__setattr__(self, "query", None)


@dataclass(frozen=True, slots=True)
class InspectionRecord:
    """Persistence DTO independent of FastAPI and model-library objects."""

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
    media_type: MediaType
    original_media_path: str
    annotated_media_path: str

    def __post_init__(self) -> None:
        if not self.inspection_id or not self.filename or not self.model_id:
            raise ValueError("inspection_id, filename, and model_id must not be empty")
        _canonical_timestamp(self.timestamp)
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be positive")
        if self.total_defects != len(self.defects):
            raise ValueError("total_defects must equal the number of defects")
        if not 0 <= self.quality_score <= 100:
            raise ValueError("quality_score must be between zero and 100")
        expected_status = "passed" if self.total_defects == 0 else "failed"
        if self.status != expected_status:
            raise ValueError("status must be passed only for a clean inspection")
        if self.media_type not in {"image/jpeg", "image/png"}:
            raise ValueError("media_type must be image/jpeg or image/png")
        if not self.original_media_path or not self.annotated_media_path:
            raise ValueError("both media paths are required")
        for defect in self.defects:
            if not isinstance(defect, dict) or not isinstance(defect.get("type"), str):
                raise ValueError("each defect must contain a string type")


SCHEMA = """
CREATE TABLE IF NOT EXISTS inspections (
    inspection_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    filename TEXT NOT NULL,
    image_width INTEGER NOT NULL CHECK (image_width > 0),
    image_height INTEGER NOT NULL CHECK (image_height > 0),
    defects_json TEXT NOT NULL CHECK (json_valid(defects_json)),
    total_defects INTEGER NOT NULL CHECK (total_defects >= 0),
    quality_score INTEGER NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    status TEXT NOT NULL CHECK (status IN ('passed', 'failed')),
    model_id TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('image/jpeg', 'image/png')),
    original_media_path TEXT NOT NULL UNIQUE,
    annotated_media_path TEXT NOT NULL UNIQUE,
    CHECK (
        (total_defects = 0 AND status = 'passed') OR
        (total_defects > 0 AND status = 'failed')
    )
);
CREATE INDEX IF NOT EXISTS inspections_timestamp_idx
    ON inspections(timestamp DESC, inspection_id DESC);
CREATE INDEX IF NOT EXISTS inspections_filename_idx
    ON inspections(filename COLLATE NOCASE);
"""


class SQLiteInspectionRepository:
    """Small transaction-aware repository with one connection per operation."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(
        self,
        record: InspectionRecord,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is None:
            with self.transaction() as transaction:
                self.create(record, connection=transaction)
            return
        connection.execute(
            """
            INSERT INTO inspections (
                inspection_id, timestamp, filename, image_width, image_height,
                defects_json, total_defects, quality_score, status, model_id,
                media_type, original_media_path, annotated_media_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.inspection_id,
                _canonical_timestamp(record.timestamp),
                record.filename,
                record.image_width,
                record.image_height,
                json.dumps(record.defects, ensure_ascii=False, separators=(",", ":")),
                record.total_defects,
                record.quality_score,
                record.status,
                record.model_id,
                record.media_type,
                record.original_media_path,
                record.annotated_media_path,
            ),
        )

    def get(
        self,
        inspection_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> InspectionRecord | None:
        if connection is None:
            with closing(self._connect()) as read_connection:
                row = read_connection.execute(
                    "SELECT * FROM inspections WHERE inspection_id = ?",
                    (inspection_id,),
                ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM inspections WHERE inspection_id = ?",
                (inspection_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list(
        self,
        filters: HistoryFilters = HistoryFilters(),
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[InspectionRecord]:
        clauses: list[str] = []
        parameters: list[object] = []
        if filters.from_date:
            clauses.append("timestamp >= ?")
            parameters.append(
                _canonical_timestamp(datetime.combine(filters.from_date, datetime.min.time(), UTC))
            )
        if filters.to_date:
            clauses.append("timestamp < ?")
            parameters.append(
                _canonical_timestamp(
                    datetime.combine(filters.to_date + timedelta(days=1), datetime.min.time(), UTC)
                )
            )
        if filters.defect_type and filters.defect_type != "all":
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM json_each(inspections.defects_json) AS defect "
                "WHERE json_extract(defect.value, '$.type') = ?"
                ")"
            )
            parameters.append(filters.defect_type)
        if filters.query:
            clauses.append(
                "(instr(lower(inspection_id), lower(?)) > 0 "
                "OR instr(lower(filename), lower(?)) > 0)"
            )
            parameters.extend((filters.query, filters.query))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM inspections{where} ORDER BY timestamp DESC, inspection_id DESC"
        if connection is None:
            with closing(self._connect()) as read_connection:
                rows = read_connection.execute(sql, parameters).fetchall()
        else:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._row_to_record(row) for row in rows]

    def delete(
        self,
        inspection_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> bool:
        if connection is None:
            with self.transaction() as transaction:
                return self.delete(inspection_id, connection=transaction)
        cursor = connection.execute(
            "DELETE FROM inspections WHERE inspection_id = ?",
            (inspection_id,),
        )
        return cursor.rowcount > 0

    def clear(self, *, connection: sqlite3.Connection | None = None) -> int:
        if connection is None:
            with self.transaction() as transaction:
                return self.clear(connection=transaction)
        cursor = connection.execute("DELETE FROM inspections")
        return cursor.rowcount

    def media_paths(self) -> set[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT original_media_path, annotated_media_path FROM inspections"
            ).fetchall()
        return {
            value
            for row in rows
            for value in (row["original_media_path"], row["annotated_media_path"])
        }

    @staticmethod
    def _row_to_record(row: Mapping[str, Any]) -> InspectionRecord:
        defects = json.loads(row["defects_json"])
        if not isinstance(defects, list):
            raise ValueError("stored defects_json must contain an array")
        return InspectionRecord(
            inspection_id=row["inspection_id"],
            timestamp=_parse_timestamp(row["timestamp"]),
            filename=row["filename"],
            image_width=row["image_width"],
            image_height=row["image_height"],
            defects=tuple(defects),
            total_defects=row["total_defects"],
            quality_score=row["quality_score"],
            status=row["status"],
            model_id=row["model_id"],
            media_type=row["media_type"],
            original_media_path=row["original_media_path"],
            annotated_media_path=row["annotated_media_path"],
        )
