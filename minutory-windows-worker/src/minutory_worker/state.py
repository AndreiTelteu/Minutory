from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .domain import STAGE_DEPENDENCIES, STAGE_ORDER, SourceIdentity, Stage, StageStatus, WorkerItem

SCHEMA_VERSION = 1


class StateError(RuntimeError):
    pass


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._migrate()
        self.recover_stale_running()

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield self._connection
            except BaseException:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def _migrate(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
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
                        duration_seconds INTEGER,
                        selected_video_path TEXT,
                        wav_path TEXT,
                        transcript_path TEXT,
                        selected_video_sha256 TEXT,
                        audio_sha256 TEXT,
                        transcript_sha256 TEXT,
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

    def add_item(self, item: WorkerItem) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO items (
                    item_id, source_path, source_size, source_mtime_ns, source_sha256,
                    title, title_manually_edited, meeting_at, meeting_at_manually_edited,
                    client_id, compression_preset
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            connection.executemany(
                "INSERT INTO stages (item_id, stage, status) VALUES (?, ?, ?)",
                [(item.item_id, stage.value, StageStatus.PENDING.value) for stage in STAGE_ORDER],
            )

    def save_item(self, item: WorkerItem) -> None:
        values = asdict(item)
        source = values.pop("source")
        columns = [
            "title",
            "title_manually_edited",
            "meeting_at",
            "meeting_at_manually_edited",
            "client_id",
            "compression_preset",
            "duration_seconds",
            "selected_video_path",
            "wav_path",
            "transcript_path",
            "selected_video_sha256",
            "audio_sha256",
            "transcript_sha256",
            "server_meeting_id",
        ]
        with self.transaction() as connection:
            cursor = connection.execute(
                f"UPDATE items SET {', '.join(f'{column} = ?' for column in columns)}, "
                "updated_at = CURRENT_TIMESTAMP WHERE item_id = ?",
                [values[column] for column in columns] + [item.item_id],
            )
            if cursor.rowcount != 1:
                raise StateError(f"Unknown item {item.item_id}.")
            connection.execute(
                """
                UPDATE items SET source_path = ?, source_size = ?, source_mtime_ns = ?,
                    source_sha256 = ? WHERE item_id = ?
                """,
                (source["path"], source["size"], source["mtime_ns"], source["sha256"], item.item_id),
            )

    def get_item(self, item_id: str) -> WorkerItem:
        row = self._connection.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
        if row is None:
            raise StateError(f"Unknown item {item_id}.")
        return WorkerItem(
            item_id=row["item_id"],
            source=SourceIdentity(
                row["source_path"], row["source_size"], row["source_mtime_ns"], row["source_sha256"]
            ),
            title=row["title"],
            title_manually_edited=bool(row["title_manually_edited"]),
            meeting_at=row["meeting_at"],
            meeting_at_manually_edited=bool(row["meeting_at_manually_edited"]),
            client_id=row["client_id"],
            compression_preset=row["compression_preset"],
            duration_seconds=row["duration_seconds"],
            selected_video_path=row["selected_video_path"],
            wav_path=row["wav_path"],
            transcript_path=row["transcript_path"],
            selected_video_sha256=row["selected_video_sha256"],
            audio_sha256=row["audio_sha256"],
            transcript_sha256=row["transcript_sha256"],
            server_meeting_id=row["server_meeting_id"],
        )

    def list_items(self) -> list[WorkerItem]:
        rows = self._connection.execute("SELECT item_id FROM items ORDER BY created_at, item_id").fetchall()
        return [self.get_item(row["item_id"]) for row in rows]

    def stage(self, item_id: str, stage: Stage) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM stages WHERE item_id = ? AND stage = ?", (item_id, stage.value)
        ).fetchone()
        if row is None:
            raise StateError(f"Unknown stage {stage.value} for {item_id}.")
        return dict(row)

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
        stages = self._connection.execute(
            "SELECT stage, status, attempts FROM stages WHERE item_id = ? ORDER BY rowid", (item_id,)
        ).fetchall()
        return json.dumps([dict(row) for row in stages], sort_keys=True)
