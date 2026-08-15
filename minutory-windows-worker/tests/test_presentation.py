from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from minutory_worker.domain import SourceIdentity, Stage, StageStatus, WorkerItem
from minutory_worker.presentation import (
    ProcessingCoordinator,
    QueueController,
    offset_iso_to_local,
    pipeline_progress,
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
    store.reconcile_success(item.item_id, Stage.PROBE)
    store.start_stage(item.item_id, Stage.MEETING)
    store.persist_stage_output(changed, Stage.MEETING)
    store.finish_stage(item.item_id, Stage.MEETING)
    with pytest.raises(StateError, match="cannot change"):
        queue.update_metadata(
            item.item_id,
            title="Conflict",
            local_datetime="2026-07-11T12:00:00",
            client_id=7,
        )
    assert store.get_item(item.item_id).title == "Manual title"


def test_new_item_renders_as_new(store: StateStore, item: WorkerItem) -> None:
    assert controller(store).view(item.item_id).status == "New"


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
    store.start_stage(item.item_id, Stage.PROBE)
    store.persist_stage_output(loaded, Stage.PROBE)
    store.finish_stage(item.item_id, Stage.PROBE)
    view = controller(store).view(item.item_id)
    assert view.probe_summary == "1:00 · 1920x1080 · 29.97 FPS"
    assert view.estimated_size == "37.6 MB"
    assert controller(store).set_preset(item.item_id, "quality")
    assert store.get_item(item.item_id).compression_preset == "quality"


def test_offset_iso_display_uses_configured_timezone() -> None:
    assert offset_iso_to_local("2026-07-10T10:03:47+00:00", "Europe/Bucharest") == "2026-07-10T13:03:47"


def test_pipeline_progress_is_segmented_and_combines_upload_bytes(store, item) -> None:
    view = controller(store).view(item.item_id)
    compression = pipeline_progress(view, (Stage.SOURCE, 40))
    assert [stage.key for stage in compression.stages] == [
        "audio",
        "compression",
        "transcript",
        "speakerid",
        "upload",
    ]
    assert compression.stages[1].fraction == pytest.approx(0.4)
    assert compression.overall_percent == 9

    view.item.selected_video_bytes = 100
    view.item.audio_bytes = 50
    view.item.transcript_bytes = 50
    view.item.speakers_bytes = 20
    succeeded = {
        Stage.PROBE,
        Stage.SOURCE,
        Stage.WAV,
        Stage.TRANSCRIBE,
        Stage.DIARIZE,
        Stage.MEETING,
        Stage.VIDEO_UPLOAD,
    }
    uploading = replace(
        view,
        stages=tuple(
            replace(stage, status=StageStatus.SUCCEEDED) if stage.stage in succeeded else stage
            for stage in view.stages
        ),
    )
    combined = pipeline_progress(uploading, (Stage.AUDIO_UPLOAD, 50))
    assert combined.stages[-1].fraction == pytest.approx(125 / 220)
    assert combined.overall_percent == 90

    uploading.item.compression_preset = "none"
    without_compression = pipeline_progress(uploading)
    assert [stage.key for stage in without_compression.stages] == [
        "audio",
        "transcript",
        "speakerid",
        "upload",
    ]


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
        self.stage_batches: list[tuple[Stage, ...]] = []
        self.concurrent = 0
        self.maximum_concurrent = 0
        self.release = threading.Event()
        self.started = threading.Event()
        self.fail_once: set[str] = set()

    def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
        self.calls.append(item_id)
        self.stage_batches.append(tuple(stages))
        if Stage.TRANSCRIBE in stages:
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

    def preflight(self, item_id, *, cancel=None, on_stage=None, on_progress=None):
        self.calls.append(f"preflight:{item_id}")
        on_stage(Stage.PROBE, StageStatus.RUNNING)
        self.started.set()
        self.release.wait(2)
        on_stage(Stage.PROBE, StageStatus.SUCCEEDED)
        return item_id

    def retry_artifact(self, item_id, artifact_name, *, on_stage=None, on_progress=None):
        self.calls.append(f"{artifact_name}:{item_id}")
        on_stage(Stage.AUDIO_UPLOAD, StageStatus.RUNNING)
        on_stage(Stage.AUDIO_UPLOAD, StageStatus.SUCCEEDED)
        return item_id


def wait_until(predicate, timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.01)


class OverlapOrchestrator:
    def __init__(self, items):
        self.store = FakeStore(items)
        self.io_entered = threading.Event()
        self.io_release = threading.Event()
        self.transcribe_overlap = threading.Event()
        self.calls: list[str] = []
        self._io_active = False
        self._gpu_count = 0
        self.concurrent = 0
        self.maximum_concurrent = 0

    def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
        self.calls.append(item_id)
        if Stage.TRANSCRIBE in stages:
            self._gpu_count += 1
            if self._gpu_count > 1:
                self.io_entered.wait(2)
            if self._io_active:
                self.transcribe_overlap.set()
            self.concurrent += 1
            self.maximum_concurrent = max(self.maximum_concurrent, self.concurrent)
            on_stage(Stage.TRANSCRIBE, StageStatus.RUNNING)
            on_stage(Stage.TRANSCRIBE, StageStatus.SUCCEEDED)
            self.concurrent -= 1
        elif Stage.MEETING in stages:
            self._io_active = True
            self.io_entered.set()
            self.io_release.wait(2)
            self._io_active = False
        return item_id

    def preflight(self, item_id, *, cancel=None, on_stage=None, on_progress=None):
        return item_id

    def retry_artifact(self, item_id, artifact_name, *, on_stage=None, on_progress=None):
        return item_id


class IsolatingOrchestrator:
    def __init__(self, items, fail_item_id):
        self.store = FakeStore(items)
        self.fail_item_id = fail_item_id
        self.io_entered = threading.Event()
        self.io_release = threading.Event()
        self.transcribe_started_during_io = threading.Event()
        self.calls: list[str] = []
        self._io_active = False
        self._gpu_count = 0

    def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
        self.calls.append(item_id)
        if Stage.TRANSCRIBE in stages:
            self._gpu_count += 1
            if self._gpu_count > 1:
                self.io_entered.wait(2)
            if self._io_active:
                self.transcribe_started_during_io.set()
            on_stage(Stage.TRANSCRIBE, StageStatus.RUNNING)
            on_stage(Stage.TRANSCRIBE, StageStatus.SUCCEEDED)
        elif Stage.MEETING in stages:
            if item_id == self.fail_item_id:
                self._io_active = True
                self.io_entered.set()
                self.io_release.wait(2)
                self._io_active = False
                raise RuntimeError("upload 503")
        return item_id

    def preflight(self, item_id, *, cancel=None, on_stage=None, on_progress=None):
        return item_id

    def retry_artifact(self, item_id, artifact_name, *, on_stage=None, on_progress=None):
        return item_id


def test_dual_lane_serializes_transcription_and_overlaps_uploads(item: WorkerItem) -> None:
    second = WorkerItem(source=item.source, title="Second")
    orchestrator = OverlapOrchestrator([item, second])
    coordinator = ProcessingCoordinator(orchestrator)
    assert coordinator.start(item.item_id)
    assert not coordinator.start(item.item_id)
    assert coordinator.start(second.item_id)
    assert orchestrator.transcribe_overlap.wait(2)
    orchestrator.io_release.set()
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.maximum_concurrent == 1
    assert orchestrator.calls.count(item.item_id) == 4
    assert orchestrator.calls.count(second.item_id) == 4
    assert coordinator.close()


def test_gpu_lane_follows_the_visible_processing_order(item: WorkerItem) -> None:
    orchestrator = SerialOrchestrator([item])
    orchestrator.release.set()
    coordinator = ProcessingCoordinator(orchestrator)
    assert coordinator.start(item.item_id)
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.stage_batches[:2] == [
        (Stage.PROBE, Stage.WAV),
        (Stage.SOURCE, Stage.TRANSCRIBE, Stage.DIARIZE),
    ]
    assert coordinator.close()


def test_io_lane_failure_does_not_block_gpu_lane(item: WorkerItem) -> None:
    second = WorkerItem(source=item.source, title="Second")
    orchestrator = IsolatingOrchestrator([item, second], fail_item_id=item.item_id)
    events: list[tuple[str, str]] = []
    coordinator = ProcessingCoordinator(
        orchestrator,
        event_sink=lambda kind, item_id, value: events.append((kind, item_id)),
    )
    assert coordinator.start(item.item_id)
    assert orchestrator.io_entered.wait(1)
    assert coordinator.start(second.item_id)
    assert orchestrator.transcribe_started_during_io.wait(1)
    orchestrator.io_release.set()
    wait_until(lambda: not coordinator.busy)
    assert ("failed", item.item_id) in events
    assert ("completed", second.item_id) in events
    assert coordinator.close()


def test_gpu_lane_failure_skips_io_and_retry_recovers(item: WorkerItem) -> None:
    orchestrator = SerialOrchestrator([item])
    orchestrator.release.set()
    orchestrator.fail_once.add(item.item_id)
    coordinator = ProcessingCoordinator(orchestrator)
    assert coordinator.start(item.item_id)
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.calls.count(item.item_id) == 2
    assert coordinator.start(item.item_id)
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.calls.count(item.item_id) == 6
    assert coordinator.close()


def test_preflight_and_artifact_dispatch_are_scheduled_and_deduplicated(item: WorkerItem) -> None:
    orchestrator = SerialOrchestrator([item])
    coordinator = ProcessingCoordinator(orchestrator)
    assert coordinator.preflight(item.item_id)
    assert orchestrator.started.wait(1)
    assert coordinator.is_scheduled(item.item_id)
    assert not coordinator.start(item.item_id)
    orchestrator.release.set()
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.calls == [f"preflight:{item.item_id}"]
    assert coordinator.retry_artifact(item.item_id, "audio")
    wait_until(lambda: not coordinator.busy)
    assert orchestrator.calls[-1] == f"audio:{item.item_id}"
    assert coordinator.close()


class MediaOrchestrator(SerialOrchestrator):
    def process_stages(self, item_id, stages, *, cancel=None, on_stage=None, on_progress=None):
        if Stage.SOURCE not in stages:
            return item_id
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


def test_cleanup_work_dir_on_remove(store: StateStore, item: WorkerItem, tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    item_work = work_dir / item.item_id
    item_work.mkdir(parents=True)
    (item_work / "audio.wav").write_bytes(b"wav")
    queue = QueueController(store, ClientApi(), timezone="Europe/Bucharest", work_dir=work_dir)
    queue.remove(item.item_id)
    assert not item_work.exists()


def test_cleanup_work_dir_preserves_running_item(store: StateStore, item: WorkerItem, tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    item_work = work_dir / item.item_id
    item_work.mkdir(parents=True)
    (item_work / "audio.wav").write_bytes(b"wav")
    store.start_stage(item.item_id, Stage.PROBE)
    queue = QueueController(store, ClientApi(), timezone="Europe/Bucharest", work_dir=work_dir)
    with pytest.raises(StateError, match="running"):
        queue.remove(item.item_id)
    assert item_work.exists()
