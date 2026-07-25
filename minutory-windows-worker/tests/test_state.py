from __future__ import annotations

import os
from pathlib import Path

import pytest

from minutory_worker.domain import Stage, StageStatus, dependent_stages
from minutory_worker.orchestrator import Orchestrator
from minutory_worker.state import SCHEMA_VERSION, StateError, StateStore


def test_schema_version_round_trip_and_list(store: StateStore, item) -> None:
    assert store._connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    loaded = store.get_item(item.item_id)
    assert loaded.source == item.source
    assert loaded.item_id == item.item_id
    assert store.list_items()[0].title == "Planning"


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    import sqlite3

    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    connection.close()
    with pytest.raises(StateError, match="newer"):
        StateStore(path)


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
