from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from minutory_worker.cli import main as cli_main
from minutory_worker.domain import Stage, StageStatus, dependent_stages
from minutory_worker.orchestrator import Orchestrator
from minutory_worker.state import (
    SCHEMA_VERSION,
    StateError,
    StateOwnershipError,
    StateReader,
    StateStore,
)


def test_schema_version_round_trip_and_list(store: StateStore, item) -> None:
    assert store.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    loaded = store.get_item(item.item_id)
    assert loaded.source == item.source
    assert loaded.item_id == item.item_id
    assert store.list_items()[0].title == "Planning"


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    connection.close()
    with pytest.raises(StateError, match="newer"):
        StateStore(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 0")
    connection.close()
    reopened = StateStore(path)
    reopened.close()


def test_transitions_dependencies_attempts_and_retry(store: StateStore, item) -> None:
    with pytest.raises(StateError, match="requires probe"):
        store.start_stage(item.item_id, Stage.SOURCE)
    store.start_stage(item.item_id, Stage.PROBE)
    store.fail_stage(item.item_id, Stage.PROBE, "Probe failed", "technical detail")
    assert store.stage(item.item_id, Stage.PROBE)["attempts"] == 1
    store.start_stage(item.item_id, Stage.PROBE)
    store.finish_stage(item.item_id, Stage.PROBE)
    assert store.stage(item.item_id, Stage.PROBE)["attempts"] == 2
    with pytest.raises(StateError, match="cannot start"):
        store.start_stage(item.item_id, Stage.PROBE)


def test_stale_running_recovers_on_restart(tmp_path: Path, item) -> None:
    path = tmp_path / "state.sqlite3"
    first = StateStore(path)
    first.add_item(item)
    first.start_stage(item.item_id, Stage.PROBE)
    first.close()
    second = StateStore(path)
    try:
        stage = second.stage(item.item_id, Stage.PROBE)
        assert stage["status"] == StageStatus.FAILED.value
        assert "restart" in str(stage["user_error"])
        second.start_stage(item.item_id, Stage.PROBE)
    finally:
        second.close()


def test_schema_one_migrates_sizes_and_final_reconciliation(tmp_path: Path, item) -> None:
    path = tmp_path / "state.sqlite3"
    original = StateStore(path)
    original.add_item(item)
    original.close()
    connection = sqlite3.connect(path)
    connection.execute(
        "DELETE FROM stages WHERE stage = ?",
        (Stage.FINAL_RECONCILE.value,),
    )
    for column in ("selected_video_bytes", "audio_bytes", "transcript_bytes"):
        connection.execute(f"ALTER TABLE items DROP COLUMN {column}")
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    migrated = StateStore(path)
    try:
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert migrated.get_item(item.item_id).selected_video_bytes is None
        assert migrated.stage(item.item_id, Stage.FINAL_RECONCILE)["status"] == StageStatus.PENDING.value
    finally:
        migrated.close()


def test_transaction_rolls_back(store: StateStore) -> None:
    with pytest.raises(RuntimeError), store.transaction() as connection:
        connection.execute("UPDATE items SET title = 'changed'")
        raise RuntimeError("rollback")
    assert store.list_items()[0].title == "Planning"


def test_source_change_invalidates_only_dependency_graph(store: StateStore, item, source: Path) -> None:
    for stage in (Stage.PROBE, Stage.SOURCE, Stage.WAV, Stage.TRANSCRIBE, Stage.MEETING):
        store.reconcile_success(item.item_id, stage)
    source.write_bytes(b"changed-source")
    os.utime(source, None)
    orchestrator = Orchestrator(store, object(), object(), object(), source.parent / "work")
    assert orchestrator.refresh_source(item.item_id)
    assert dependent_stages(Stage.PROBE) == set(Stage)
    for stage in Stage:
        assert store.stage(item.item_id, stage)["status"] == StageStatus.PENDING.value
    loaded = store.get_item(item.item_id)
    assert loaded.server_meeting_id is None
    assert loaded.selected_video_sha256 is None


def test_single_writer_lock_prevents_active_stage_recovery(tmp_path: Path, item) -> None:
    path = tmp_path / "state.sqlite3"
    owner = StateStore(path)
    owner.add_item(item)
    owner.start_stage(item.item_id, Stage.PROBE)
    try:
        with pytest.raises(StateOwnershipError, match="owns"):
            StateStore(path)
        assert owner.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.RUNNING.value
    finally:
        owner.close()
    successor = StateStore(path)
    try:
        assert successor.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.FAILED.value
    finally:
        successor.close()


def test_read_only_diagnostics_do_not_recover_running_stage(tmp_path: Path, item) -> None:
    path = tmp_path / "state.sqlite3"
    owner = StateStore(path)
    owner.add_item(item)
    owner.start_stage(item.item_id, Stage.PROBE)
    reader = StateReader(path)
    try:
        assert reader.list_items()[0].item_id == item.item_id
        assert reader.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.RUNNING.value
        assert owner.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.RUNNING.value
    finally:
        reader.close()
        owner.close()


def test_list_state_cli_is_read_only_and_does_not_require_token(
    tmp_path: Path,
    item,
    monkeypatch,
    capsys,
) -> None:
    path = tmp_path / "state.sqlite3"
    owner = StateStore(path)
    owner.add_item(item)
    owner.start_stage(item.item_id, Stage.PROBE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINUTORY_API_TOKEN", raising=False)
    monkeypatch.setenv("MINUTORY_STATE_DB", str(path))
    monkeypatch.setattr("sys.argv", ["minutory-worker", "list-state"])
    try:
        assert cli_main() == 0
        assert item.item_id in capsys.readouterr().out
        assert owner.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.RUNNING.value
    finally:
        owner.close()


def test_compression_preset_mutation_is_transactional(store: StateStore, item) -> None:
    for stage in Stage:
        store.reconcile_success(item.item_id, stage)
    item = store.get_item(item.item_id)
    item.selected_video_path = "video.mp4"
    item.wav_path = "audio.wav"
    item.transcript_path = "transcript.json"
    item.selected_video_sha256 = "a" * 64
    item.audio_sha256 = "b" * 64
    item.transcript_sha256 = "c" * 64
    item.selected_video_bytes = 10
    item.audio_bytes = 20
    item.transcript_bytes = 30
    store.save_item(item)

    assert store.set_compression_preset(item.item_id, "quality")
    changed = store.get_item(item.item_id)
    assert changed.compression_preset == "quality"
    assert changed.duration_seconds == item.duration_seconds
    assert changed.selected_video_path is None
    assert changed.selected_video_sha256 is None
    assert store.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.SUCCEEDED.value
    assert store.stage(item.item_id, Stage.MEETING)["status"] == StageStatus.SUCCEEDED.value
    for stage in dependent_stages(Stage.SOURCE):
        assert store.stage(item.item_id, stage)["status"] == StageStatus.PENDING.value
    assert not store.set_compression_preset(item.item_id, "quality")


def test_preset_validation_and_post_server_refusal(store: StateStore, item) -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        store.set_compression_preset(item.item_id, "invalid")
    with pytest.raises(ValueError, match="Unsupported"):
        type(item)(source=item.source, title="Invalid", compression_preset="invalid")
    item.server_meeting_id = 91
    store.save_item(item)
    with pytest.raises(StateError, match="new worker item"):
        store.set_compression_preset(item.item_id, "compact")
    assert store.get_item(item.item_id).compression_preset == "balanced"


def test_worker_item_requires_canonical_uuid(item) -> None:
    with pytest.raises(ValueError, match="canonical"):
        type(item)(
            source=item.source,
            title="Uppercase UUID",
            item_id=item.item_id.upper(),
        )
