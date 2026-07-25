from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from minutory_worker.domain import SourceIdentity, Stage, StageStatus, WorkerItem
from minutory_worker.presentation import (
    ProcessingCoordinator,
    QueueController,
    offset_iso_to_local,
)
from minutory_worker.state import StateError, StateStore


def test_gui_entry_module_imports_without_eager_qt_or_gpu_import() -> None:
    from minutory_worker.gui import app

    assert callable(app.main)


class ClientApi:
    def __init__(self, clients=None):
        self.clients = clients or [{"id": 2, "name": "Acme"}, {"id": 7, "name": "Zenith"}]

    def list_clients(self):
        return self.clients


def controller(store: StateStore) -> QueueController:
    return QueueController(store, ClientApi(), timezone="Europe/Bucharest")


def test_add_paths_deduplicates_canonical_identity_and_rejects_unsupported(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state.sqlite3")
    try:
        video = tmp_path / "2026-07-10 13-03-47 Planning Fast 1080p30.mp4"
        video.write_bytes(b"video")
        text = tmp_path / "notes.txt"
        text.write_text("notes")
        result = controller(state).add_paths([video, video.parent / "." / video.name, text])
        assert len(result.added) == 1
        assert len(result.existing) == 1
        assert result.errors == ("notes.txt: unsupported video type.",)
        item = state.get_item(result.added[0])
        assert item.source.path == str(video.resolve())
        assert item.title == "Planning"
        assert item.meeting_at == "2026-07-10T13:03:47+03:00"
    finally:
        state.close()


def test_dst_gap_is_rejected_before_queue_persistence(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state.sqlite3")
    try:
        video = tmp_path / "2026-03-29 03-30-00 Gap.mp4"
        video.write_bytes(b"video")
        result = controller(state).add_paths([video])
        assert not result.added
        assert "DST transition" in result.errors[0]
        assert state.list_items() == []
    finally:
        state.close()


def test_metadata_ownership_nullable_datetime_and_post_meeting_refusal(
    store: StateStore, item: WorkerItem
) -> None:
    queue = controller(store)
    changed = queue.update_metadata(
        item.item_id,
        title="Manual title",
        local_datetime=None,
        client_id=7,
    )
    assert changed.title == "Manual title"
    assert changed.title_manually_edited
    assert changed.meeting_at is None
    assert changed.meeting_at_manually_edited
    changed.server_meeting_id = 91
    store.save_item(changed)
    with pytest.raises(StateError, match="cannot change"):
        queue.update_metadata(
            item.item_id,
            title="Conflict",
            local_datetime="2026-07-11T12:00:00",
            client_id=7,
        )
    assert store.get_item(item.item_id).title == "Manual title"


def test_client_loading_queue_restore_and_state_render(tmp_path: Path, source: Path) -> None:
    path = tmp_path / "state.sqlite3"
    state = StateStore(path)
    queued = WorkerItem(source=SourceIdentity.from_path(source), title="Restored", client_id=2)
    state.add_item(queued)
    state.start_stage(queued.item_id, Stage.PROBE)
    state.fail_stage(queued.item_id, Stage.PROBE, "Unreadable video", "ffprobe details")
    assert [choice.name for choice in controller(state).load_clients()] == ["Acme", "Zenith"]
    state.close()

    restored = StateStore(path)
    try:
        view = controller(restored).view(queued.item_id)
        assert view.status == "Needs attention · probe"
        assert view.stages[0].attempts == 1
        assert view.stages[0].diagnostic == "ffprobe details"
        assert view.item.source.path == str(source.resolve())
        assert view.estimated_size.endswith("B")
    finally:
        restored.close()


def test_probe_render_and_transactional_preset_mutation(store: StateStore, item: WorkerItem) -> None:
    loaded = store.get_item(item.item_id)
    loaded.duration_seconds = 60
    loaded.probe_width = 1920
    loaded.probe_height = 1080
    loaded.probe_fps = 29.97
    store.save_item(loaded)
    view = controller(store).view(item.item_id)
    assert view.probe_summary == "1:00 · 1920x1080 · 29.97 FPS"
    assert view.estimated_size == "37.6 MB"
    assert controller(store).set_preset(item.item_id, "quality")
    assert store.get_item(item.item_id).compression_preset == "quality"


def test_offset_iso_display_uses_configured_timezone() -> None:
    assert offset_iso_to_local("2026-07-10T10:03:47+00:00", "Europe/Bucharest") == "2026-07-10T13:03:47"


class FakeStore:
    def __init__(self, items):
        self._items = items

    def list_items(self):
        return self._items

    def stages(self, _item_id):
        return [{"status": StageStatus.PENDING.value}]


class SerialOrchestrator:
    def __init__(self, items):
        self.store = FakeStore(items)
        self.calls: list[str] = []
        self.concurrent = 0
        self.maximum_concurrent = 0
        self.release = threading.Event()
        self.started = threading.Event()
        self.fail_once: set[str] = set()

    def process(self, item_id, *, cancel, on_stage):
        self.calls.append(item_id)
        self.concurrent += 1
        self.maximum_concurrent = max(self.maximum_concurrent, self.concurrent)
        on_stage(Stage.TRANSCRIBE, StageStatus.RUNNING)
        self.started.set()
        self.release.wait(2)
        on_stage(Stage.TRANSCRIBE, StageStatus.SUCCEEDED)
        self.concurrent -= 1
        if item_id in self.fail_once:
            self.fail_once.remove(item_id)
            raise RuntimeError("retry me")
        return item_id


def wait_until(predicate, timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.01)


def test_background_serialization_duplicate_start_retry_and_close_safety(item: WorkerItem) -> None:
    second = WorkerItem(source=item.source, title="Second")
    orchestrator = SerialOrchestrator([item, second])
    coordinator = ProcessingCoordinator(orchestrator)
    assert coordinator.start(item.item_id)
    assert not coordinator.start(item.item_id)
    assert coordinator.start(second.item_id)
    assert orchestrator.started.wait(1)
    assert coordinator.transcription_active
    assert not coordinator.close()
    orchestrator.release.set()
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.calls == [item.item_id, second.item_id]
    assert orchestrator.maximum_concurrent == 1

    orchestrator.release.set()
    orchestrator.fail_once.add(item.item_id)
    assert coordinator.start(item.item_id)
    wait_until(lambda: not coordinator.busy)
    assert coordinator.start(item.item_id)
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.calls.count(item.item_id) == 3
    assert coordinator.close()


class MediaOrchestrator(SerialOrchestrator):
    def process(self, item_id, *, cancel, on_stage):
        on_stage(Stage.SOURCE, StageStatus.RUNNING)
        self.started.set()
        assert cancel.wait(1)
        on_stage(Stage.SOURCE, StageStatus.FAILED)
        return item_id


def test_media_cancellation_is_scoped_to_supported_stage(item: WorkerItem) -> None:
    orchestrator = MediaOrchestrator([item])
    coordinator = ProcessingCoordinator(orchestrator)
    assert coordinator.start(item.item_id)
    assert orchestrator.started.wait(1)
    assert coordinator.cancel_current_media()
    wait_until(lambda: not coordinator.busy)
    assert coordinator.close()
