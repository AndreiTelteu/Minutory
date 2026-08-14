from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, cast

from .domain import (
    COMPRESSION_PRESETS,
    STAGE_DEPENDENCIES,
    STAGE_ORDER,
    SUPPORTED_LANGUAGES,
    SourceIdentity,
    Stage,
    StageStatus,
    WorkerItem,
    dependent_stages,
)

SCHEMA_VERSION = 6

STAGE_OUTPUT_COLUMNS: dict[Stage, tuple[str, ...]] = {
    Stage.PROBE: (
        "duration_seconds",
        "probe_width",
        "probe_height",
        "probe_fps",
        "probe_bitrate",
    ),
    Stage.SOURCE: (
        "selected_video_path",
        "selected_video_sha256",
        "selected_video_bytes",
    ),
    Stage.WAV: ("wav_path", "audio_sha256", "audio_bytes"),
    Stage.TRANSCRIBE: ("transcript_path", "transcript_sha256", "transcript_bytes"),
    Stage.DIARIZE: ("speakers_path", "speakers_sha256", "speakers_bytes"),
    Stage.MERGE: ("transcript_path", "transcript_sha256", "transcript_bytes"),
    Stage.MEETING: ("server_meeting_id",),
    Stage.VIDEO_UPLOAD: (),
    Stage.AUDIO_UPLOAD: (),
    Stage.TRANSCRIPT_UPLOAD: (),
    Stage.SPEAKERS_UPLOAD: (),
    Stage.FINAL_RECONCILE: (),
}


class StateError(RuntimeError):
    pass


class StateOwnershipError(StateError):
    pass


class _ProcessLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream: BinaryIO | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if stream.seek(0, os.SEEK_END) == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                windows_locking = cast(Any, msvcrt)
                windows_locking.locking(stream.fileno(), windows_locking.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
        except (OSError, ImportError) as exception:
            stream.close()
            raise StateOwnershipError(
                f"Another worker owns state database {self.path.with_suffix('')}."
            ) from exception
        self._stream = stream

    def release(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                windows_locking = cast(Any, msvcrt)
                windows_locking.locking(stream.fileno(), windows_locking.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
        finally:
            stream.close()
            self._stream = None


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._process_lock = _ProcessLock(path.with_name(f"{path.name}.lock"))
        self._connection: sqlite3.Connection | None = None
        self._closed = False
        self._process_lock.acquire()
        try:
            connection = sqlite3.connect(
                path,
                timeout=30,
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection = connection
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 30000")
            self._migrate()
            self.recover_stale_running()
        except BaseException:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._process_lock.release()
            raise

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
        finally:
            self._process_lock.release()
            self._closed = True

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise StateError("State store is closed.")
        return self._connection

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self.connection
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def _migrate(self) -> None:
        version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise StateError(f"State schema {version} is newer than supported schema {SCHEMA_VERSION}.")
        if version == 0:
            with self.transaction() as connection:
                connection.execute(
                    """
                    CREATE TABLE items (
                        item_id TEXT PRIMARY KEY,
                        source_path TEXT NOT NULL,
                        source_size INTEGER NOT NULL,
                        source_mtime_ns INTEGER NOT NULL,
                        source_sha256 TEXT,
                        title TEXT NOT NULL,
                        title_manually_edited INTEGER NOT NULL DEFAULT 0,
                        meeting_at TEXT,
                        meeting_at_manually_edited INTEGER NOT NULL DEFAULT 0,
                        client_id INTEGER,
                        compression_preset TEXT NOT NULL,
                        language TEXT NOT NULL DEFAULT 'ro',
                        duration_seconds INTEGER,
                        probe_width INTEGER,
                        probe_height INTEGER,
                        probe_fps REAL,
                        probe_bitrate INTEGER,
                        selected_video_path TEXT,
                        wav_path TEXT,
                        transcript_path TEXT,
                        speakers_path TEXT,
                        selected_video_sha256 TEXT,
                        audio_sha256 TEXT,
                        transcript_sha256 TEXT,
                        speakers_sha256 TEXT,
                        selected_video_bytes INTEGER,
                        audio_bytes INTEGER,
                        transcript_bytes INTEGER,
                        speakers_bytes INTEGER,
                        server_meeting_id INTEGER,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE stages (
                        item_id TEXT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
                        stage TEXT NOT NULL,
                        status TEXT NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        user_error TEXT,
                        diagnostic TEXT,
                        started_at TEXT,
                        completed_at TEXT,
                        PRIMARY KEY (item_id, stage)
                    )
                    """
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            version = SCHEMA_VERSION
        if version == 1:
            with self.transaction() as connection:
                existing_columns = {
                    str(row["name"]) for row in connection.execute("PRAGMA table_info(items)")
                }
                for column in ("selected_video_bytes", "audio_bytes", "transcript_bytes"):
                    if column not in existing_columns:
                        connection.execute(f"ALTER TABLE items ADD COLUMN {column} INTEGER")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO stages (item_id, stage, status)
                    SELECT item_id, ?, ? FROM items
                    """,
                    (Stage.FINAL_RECONCILE.value, StageStatus.PENDING.value),
                )
                connection.execute("PRAGMA user_version = 2")
            version = 2
        if version == 2:
            with self.transaction() as connection:
                existing_columns = {
                    str(row["name"]) for row in connection.execute("PRAGMA table_info(items)")
                }
                for column, kind in (
                    ("probe_width", "INTEGER"),
                    ("probe_height", "INTEGER"),
                    ("probe_fps", "REAL"),
                    ("probe_bitrate", "INTEGER"),
                ):
                    if column not in existing_columns:
                        connection.execute(f"ALTER TABLE items ADD COLUMN {column} {kind}")
                connection.execute("PRAGMA user_version = 3")
            version = 3
        if version == 3:
            with self.transaction() as connection:
                existing_columns = {
                    str(row["name"]) for row in connection.execute("PRAGMA table_info(items)")
                }
                if "language" not in existing_columns:
                    connection.execute("ALTER TABLE items ADD COLUMN language TEXT NOT NULL DEFAULT 'ro'")
                connection.execute("PRAGMA user_version = 4")
            version = 4
        if version == 4:
            with self.transaction() as connection:
                existing_columns = {
                    str(row["name"]) for row in connection.execute("PRAGMA table_info(items)")
                }
                for column, kind in (
                    ("speakers_path", "TEXT"),
                    ("speakers_sha256", "TEXT"),
                    ("speakers_bytes", "INTEGER"),
                ):
                    if column not in existing_columns:
                        connection.execute(f"ALTER TABLE items ADD COLUMN {column} {kind}")
                connection.executemany(
                    "INSERT OR IGNORE INTO stages (item_id, stage, status) VALUES (?, ?, ?)",
                    [
                        (row["item_id"], Stage.DIARIZE.value, StageStatus.PENDING.value)
                        for row in connection.execute("SELECT item_id FROM items")
                    ]
                    + [
                        (row["item_id"], Stage.SPEAKERS_UPLOAD.value, StageStatus.PENDING.value)
                        for row in connection.execute("SELECT item_id FROM items")
                    ],
                )
                connection.execute("PRAGMA user_version = 5")
            version = 5
        if version == 5:
            with self.transaction() as connection:
                connection.executemany(
                    "INSERT OR IGNORE INTO stages (item_id, stage, status) VALUES (?, ?, ?)",
                    [
                        (row["item_id"], Stage.MERGE.value, StageStatus.PENDING.value)
                        for row in connection.execute("SELECT item_id FROM items")
                    ],
                )
                # Existing raw transcripts predate speaker-aware merging. They must be
                # regenerated locally before another upload can be trusted.
                connection.execute(
                    "UPDATE stages SET status = ? WHERE stage IN (?, ?)",
                    (StageStatus.PENDING.value, Stage.MERGE.value, Stage.TRANSCRIPT_UPLOAD.value),
                )
                connection.execute("PRAGMA user_version = 6")
            version = 6

    def add_item(self, item: WorkerItem) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO items (
                    item_id, source_path, source_size, source_mtime_ns, source_sha256,
                    title, title_manually_edited, meeting_at, meeting_at_manually_edited,
                    client_id, compression_preset, language
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.item_id,
                    item.source.path,
                    item.source.size,
                    item.source.mtime_ns,
                    item.source.sha256,
                    item.title,
                    item.title_manually_edited,
                    item.meeting_at,
                    item.meeting_at_manually_edited,
                    item.client_id,
                    item.compression_preset,
                    item.language,
                ),
            )
            connection.executemany(
                "INSERT INTO stages (item_id, stage, status) VALUES (?, ?, ?)",
                [(item.item_id, stage.value, StageStatus.PENDING.value) for stage in STAGE_ORDER],
            )

    def persist_stage_output(self, item: WorkerItem, stage: Stage) -> None:
        """Persist only columns owned by a currently running stage."""
        columns = STAGE_OUTPUT_COLUMNS[stage]
        with self.transaction() as connection:
            status = connection.execute(
                "SELECT status FROM stages WHERE item_id = ? AND stage = ?",
                (item.item_id, stage.value),
            ).fetchone()
            if status is None or status["status"] != StageStatus.RUNNING.value:
                raise StateError(f"Stage {stage.value} is not running.")
            if not columns:
                return
            cursor = connection.execute(
                f"UPDATE items SET {', '.join(f'{column} = ?' for column in columns)}, "
                "updated_at = CURRENT_TIMESTAMP WHERE item_id = ?",
                [getattr(item, column) for column in columns] + [item.item_id],
            )
            if cursor.rowcount != 1:
                raise StateError(f"Unknown item {item.item_id}.")

    def replace_source_identity(
        self,
        item_id: str,
        *,
        expected: SourceIdentity,
        replacement: SourceIdentity,
    ) -> bool:
        """Replace changed source identity and invalidate every derived stage atomically."""
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT items.*, stages.attempts AS meeting_attempts
                FROM items JOIN stages ON stages.item_id = items.item_id AND stages.stage = ?
                WHERE items.item_id = ?
                """,
                (Stage.MEETING.value, item_id),
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown item {item_id}.")
            stored = SourceIdentity(
                path=str(row["source_path"]),
                size=int(row["source_size"]),
                mtime_ns=int(row["source_mtime_ns"]),
                sha256=str(row["source_sha256"]) if row["source_sha256"] else None,
            )
            if stored != expected:
                raise StateError("Source identity changed concurrently; refresh and try again.")
            if stored == replacement:
                return False
            if row["server_meeting_id"] is not None or row["meeting_attempts"] > 0:
                raise StateError(
                    "Source cannot change after a server meeting attempt; create a new worker item."
                )
            self._refuse_running(connection, item_id, "Source cannot change while processing.")
            connection.execute(
                """
                UPDATE items SET source_path = ?, source_size = ?, source_mtime_ns = ?,
                    source_sha256 = ?, duration_seconds = NULL, probe_width = NULL,
                    probe_height = NULL, probe_fps = NULL, probe_bitrate = NULL,
                    selected_video_path = NULL, selected_video_sha256 = NULL,
                    selected_video_bytes = NULL, wav_path = NULL, audio_sha256 = NULL,
                    audio_bytes = NULL, transcript_path = NULL, transcript_sha256 = NULL,
                    transcript_bytes = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
                """,
                (
                    replacement.path,
                    replacement.size,
                    replacement.mtime_ns,
                    replacement.sha256,
                    item_id,
                ),
            )
            connection.execute(
                """
                UPDATE stages SET status = ?, user_error = NULL, diagnostic = NULL,
                    started_at = NULL, completed_at = NULL WHERE item_id = ?
                """,
                (StageStatus.PENDING.value, item_id),
            )
            return True

    def get_item(self, item_id: str) -> WorkerItem:
        with self._lock:
            row = self.connection.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
            if row is None:
                raise StateError(f"Unknown item {item_id}.")
            return _item_from_row(row)

    def list_items(self) -> list[WorkerItem]:
        with self._lock:
            rows = self.connection.execute("SELECT * FROM items ORDER BY rowid").fetchall()
            return [_item_from_row(row) for row in rows]

    def stage(self, item_id: str, stage: Stage) -> dict[str, object]:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM stages WHERE item_id = ? AND stage = ?", (item_id, stage.value)
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown stage {stage.value} for {item_id}.")
            return dict(row)

    def stages(self, item_id: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM stages WHERE item_id = ? ORDER BY rowid", (item_id,)
            ).fetchall()
            if not rows:
                raise StateError(f"Unknown item {item_id}.")
            return [dict(row) for row in rows]

    def find_item_by_source_path(self, source_path: str) -> WorkerItem | None:
        canonical = str(Path(source_path).resolve())
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM items WHERE source_path = ? COLLATE NOCASE ORDER BY created_at LIMIT 1",
                (canonical,),
            ).fetchone()
            return _item_from_row(row) if row is not None else None

    def update_metadata(
        self,
        item_id: str,
        *,
        title: str,
        meeting_at: str | None,
        client_id: int | None,
        title_manually_edited: bool = True,
        meeting_at_manually_edited: bool = True,
    ) -> WorkerItem:
        normalized_title = title.strip()
        if not normalized_title or len(normalized_title) > 255:
            raise ValueError("Title must contain between 1 and 255 characters.")
        if client_id is not None and client_id <= 0:
            raise ValueError("Client ID must be positive.")
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT items.server_meeting_id, stages.attempts AS meeting_attempts
                FROM items JOIN stages ON stages.item_id = items.item_id AND stages.stage = ?
                WHERE items.item_id = ?
                """,
                (Stage.MEETING.value, item_id),
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown item {item_id}.")
            self._refuse_running(connection, item_id, "Metadata cannot change while processing.")
            if row["server_meeting_id"] is not None or row["meeting_attempts"] > 0:
                raise StateError(
                    "Metadata cannot change after a server meeting attempt; create a new worker item."
                )
            connection.execute(
                """
                UPDATE items SET title = ?, title_manually_edited = ?, meeting_at = ?,
                    meeting_at_manually_edited = ?, client_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
                """,
                (
                    normalized_title,
                    title_manually_edited,
                    meeting_at,
                    meeting_at_manually_edited,
                    client_id,
                    item_id,
                ),
            )
        return self.get_item(item_id)

    def delete_pre_server_item(self, item_id: str) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT items.server_meeting_id, stages.attempts AS meeting_attempts
                FROM items JOIN stages ON stages.item_id = items.item_id AND stages.stage = ?
                WHERE items.item_id = ?
                """,
                (Stage.MEETING.value, item_id),
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown item {item_id}.")
            if row["server_meeting_id"] is not None or row["meeting_attempts"] > 0:
                raise StateError("Items with a server meeting attempt cannot be removed.")
            self._refuse_running(connection, item_id, "A running item cannot be removed.")
            connection.execute("DELETE FROM items WHERE item_id = ?", (item_id,))

    def delete_reconciled_item(self, item_id: str) -> None:
        with self.transaction() as connection:
            rows = connection.execute("SELECT status FROM stages WHERE item_id = ?", (item_id,)).fetchall()
            if not rows:
                raise StateError(f"Unknown item {item_id}.")
            if any(row["status"] != StageStatus.SUCCEEDED.value for row in rows):
                raise StateError("Only fully completed items can be cleared.")
            self._refuse_running(connection, item_id, "A running item cannot be removed.")
            connection.execute("DELETE FROM items WHERE item_id = ?", (item_id,))

    def start_stage(self, item_id: str, stage: Stage) -> None:
        with self.transaction() as connection:
            status = connection.execute(
                "SELECT status FROM stages WHERE item_id = ? AND stage = ?", (item_id, stage.value)
            ).fetchone()
            if status is None or status["status"] not in {
                StageStatus.PENDING.value,
                StageStatus.FAILED.value,
            }:
                raise StateError(
                    f"Stage {stage.value} cannot start from {status['status'] if status else 'missing'}."
                )
            for dependency in STAGE_DEPENDENCIES[stage]:
                dependency_status = connection.execute(
                    "SELECT status FROM stages WHERE item_id = ? AND stage = ?",
                    (item_id, dependency.value),
                ).fetchone()
                if dependency_status is None or dependency_status["status"] != StageStatus.SUCCEEDED.value:
                    raise StateError(f"Stage {stage.value} requires {dependency.value}.")
            connection.execute(
                """
                UPDATE stages SET status = ?, attempts = attempts + 1, user_error = NULL,
                    diagnostic = NULL, started_at = CURRENT_TIMESTAMP, completed_at = NULL
                WHERE item_id = ? AND stage = ?
                """,
                (StageStatus.RUNNING.value, item_id, stage.value),
            )

    def finish_stage(self, item_id: str, stage: Stage) -> None:
        self._transition_running(
            item_id,
            stage,
            "status = ?, completed_at = CURRENT_TIMESTAMP",
            (StageStatus.SUCCEEDED.value,),
        )

    def fail_stage(self, item_id: str, stage: Stage, user_error: str, diagnostic: str) -> None:
        self._transition_running(
            item_id,
            stage,
            "status = ?, user_error = ?, diagnostic = ?, completed_at = CURRENT_TIMESTAMP",
            (StageStatus.FAILED.value, user_error[:1000], diagnostic[:8000]),
        )

    def _transition_running(
        self, item_id: str, stage: Stage, update: str, values: tuple[object, ...]
    ) -> None:
        with self.transaction() as connection:
            cursor = connection.execute(
                f"UPDATE stages SET {update} WHERE item_id = ? AND stage = ? AND status = ?",
                (*values, item_id, stage.value, StageStatus.RUNNING.value),
            )
            if cursor.rowcount != 1:
                raise StateError(f"Stage {stage.value} is not running.")

    def invalidate(self, item_id: str, stages: set[Stage]) -> None:
        with self.transaction() as connection:
            connection.executemany(
                """
                UPDATE stages SET status = ?, user_error = NULL, diagnostic = NULL,
                    started_at = NULL, completed_at = NULL WHERE item_id = ? AND stage = ?
                """,
                [(StageStatus.PENDING.value, item_id, stage.value) for stage in stages],
            )

    def reset_remote_missing(self, item_id: str, upload_stage: Stage) -> None:
        if upload_stage not in {
            Stage.VIDEO_UPLOAD,
            Stage.AUDIO_UPLOAD,
            Stage.TRANSCRIPT_UPLOAD,
            Stage.SPEAKERS_UPLOAD,
        }:
            raise StateError("Only upload stages can be reset after remote deletion.")
        with self.transaction() as connection:
            connection.executemany(
                """
                UPDATE stages SET status = ?, user_error = NULL, diagnostic = NULL,
                    started_at = NULL, completed_at = NULL
                WHERE item_id = ? AND stage = ? AND status != ?
                """,
                [
                    (
                        StageStatus.PENDING.value,
                        item_id,
                        upload_stage.value,
                        StageStatus.RUNNING.value,
                    ),
                    (
                        StageStatus.PENDING.value,
                        item_id,
                        Stage.FINAL_RECONCILE.value,
                        StageStatus.RUNNING.value,
                    ),
                ],
            )

    def set_compression_preset(self, item_id: str, preset: str) -> bool:
        if preset not in COMPRESSION_PRESETS:
            raise ValueError(f"Unsupported compression preset {preset!r}.")
        stages = dependent_stages(Stage.SOURCE)
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT items.compression_preset, items.server_meeting_id,
                    stages.attempts AS meeting_attempts
                FROM items JOIN stages ON stages.item_id = items.item_id AND stages.stage = ?
                WHERE items.item_id = ?
                """,
                (Stage.MEETING.value, item_id),
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown item {item_id}.")
            self._refuse_running(connection, item_id, "Compression cannot change while processing.")
            if row["compression_preset"] == preset:
                return False
            if row["server_meeting_id"] is not None or row["meeting_attempts"] > 0:
                raise StateError(
                    "Compression cannot change after a server meeting attempt; create a new worker item."
                )
            connection.execute(
                """
                UPDATE items SET compression_preset = ?,
                    selected_video_path = NULL, selected_video_sha256 = NULL,
                    selected_video_bytes = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
                """,
                (preset, item_id),
            )
            connection.executemany(
                """
                UPDATE stages SET status = ?, user_error = NULL, diagnostic = NULL,
                    started_at = NULL, completed_at = NULL
                WHERE item_id = ? AND stage = ?
                """,
                [(StageStatus.PENDING.value, item_id, stage.value) for stage in stages],
            )
            return True

    def set_language(self, item_id: str, language: str) -> bool:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language {language!r}.")
        stages = dependent_stages(Stage.TRANSCRIBE)
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT items.language, stages.status AS transcript_upload_status
                FROM items JOIN stages ON stages.item_id = items.item_id AND stages.stage = ?
                WHERE items.item_id = ?
                """,
                (Stage.TRANSCRIPT_UPLOAD.value, item_id),
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown item {item_id}.")
            self._refuse_running(connection, item_id, "Language cannot change while processing.")
            if row["language"] == language:
                return False
            if row["transcript_upload_status"] == StageStatus.SUCCEEDED.value:
                raise StateError(
                    "Language cannot change after the transcript was uploaded; create a new worker item."
                )
            connection.execute(
                "UPDATE items SET language = ?, updated_at = CURRENT_TIMESTAMP WHERE item_id = ?",
                (language, item_id),
            )
            connection.executemany(
                """
                UPDATE stages SET status = ?, user_error = NULL, diagnostic = NULL,
                    started_at = NULL, completed_at = NULL
                WHERE item_id = ? AND stage = ?
                """,
                [(StageStatus.PENDING.value, item_id, stage.value) for stage in stages],
            )
            return True

    @staticmethod
    def _refuse_running(
        connection: sqlite3.Connection,
        item_id: str,
        message: str,
    ) -> None:
        running = connection.execute(
            "SELECT 1 FROM stages WHERE item_id = ? AND status = ? LIMIT 1",
            (item_id, StageStatus.RUNNING.value),
        ).fetchone()
        if running is not None:
            raise StateError(message)

    def reconcile_success(self, item_id: str, stage: Stage) -> None:
        """Record durable server success without pretending a local attempt ran."""
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT status FROM stages WHERE item_id = ? AND stage = ?", (item_id, stage.value)
            ).fetchone()
            if row is None:
                raise StateError(f"Unknown stage {stage.value}.")
            if row["status"] == StageStatus.RUNNING.value:
                raise StateError(f"Cannot reconcile running stage {stage.value}.")
            connection.execute(
                """
                UPDATE stages SET status = ?, user_error = NULL, diagnostic = NULL,
                    completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)
                WHERE item_id = ? AND stage = ?
                """,
                (StageStatus.SUCCEEDED.value, item_id, stage.value),
            )

    def recover_stale_running(self) -> int:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE stages SET status = ?, user_error = ?,
                    diagnostic = ?, completed_at = CURRENT_TIMESTAMP
                WHERE status = ?
                """,
                (
                    StageStatus.FAILED.value,
                    "Interrupted by worker restart; retry this stage.",
                    "Recovered stale running state during startup.",
                    StageStatus.RUNNING.value,
                ),
            )
            return cursor.rowcount

    def snapshot(self, item_id: str) -> str:
        return json.dumps(
            [{key: row[key] for key in ("stage", "status", "attempts")} for row in self.stages(item_id)],
            sort_keys=True,
        )


class StateReader:
    """Read-only diagnostics that never migrate, recover, or acquire writer ownership."""

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise StateError(f"State database {path} does not exist.")
        uri = f"{path.resolve().as_uri()}?mode=ro"
        try:
            self._connection = sqlite3.connect(uri, uri=True, timeout=1, isolation_level=None)
            self._connection.row_factory = sqlite3.Row
            version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
            if version != SCHEMA_VERSION:
                raise StateError(
                    f"State schema {version} cannot be read by schema {SCHEMA_VERSION} diagnostics."
                )
        except BaseException:
            if hasattr(self, "_connection"):
                self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def get_item(self, item_id: str) -> WorkerItem:
        row = self._connection.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
        if row is None:
            raise StateError(f"Unknown item {item_id}.")
        return _item_from_row(row)

    def list_items(self) -> list[WorkerItem]:
        rows = self._connection.execute("SELECT item_id FROM items ORDER BY rowid").fetchall()
        return [self.get_item(row["item_id"]) for row in rows]

    def stage(self, item_id: str, stage: Stage) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM stages WHERE item_id = ? AND stage = ?",
            (item_id, stage.value),
        ).fetchone()
        if row is None:
            raise StateError(f"Unknown stage {stage.value} for {item_id}.")
        return dict(row)


def _item_from_row(row: sqlite3.Row) -> WorkerItem:
    return WorkerItem(
        item_id=row["item_id"],
        source=SourceIdentity(
            row["source_path"],
            row["source_size"],
            row["source_mtime_ns"],
            row["source_sha256"],
        ),
        title=row["title"],
        title_manually_edited=bool(row["title_manually_edited"]),
        meeting_at=row["meeting_at"],
        meeting_at_manually_edited=bool(row["meeting_at_manually_edited"]),
        client_id=row["client_id"],
        compression_preset=row["compression_preset"],
        language=row["language"],
        duration_seconds=row["duration_seconds"],
        probe_width=row["probe_width"],
        probe_height=row["probe_height"],
        probe_fps=row["probe_fps"],
        probe_bitrate=row["probe_bitrate"],
        selected_video_path=row["selected_video_path"],
        wav_path=row["wav_path"],
        transcript_path=row["transcript_path"],
        speakers_path=row["speakers_path"],
        selected_video_sha256=row["selected_video_sha256"],
        audio_sha256=row["audio_sha256"],
        transcript_sha256=row["transcript_sha256"],
        speakers_sha256=row["speakers_sha256"],
        selected_video_bytes=row["selected_video_bytes"],
        audio_bytes=row["audio_bytes"],
        transcript_bytes=row["transcript_bytes"],
        speakers_bytes=row["speakers_bytes"],
        server_meeting_id=row["server_meeting_id"],
    )
