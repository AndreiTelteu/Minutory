from __future__ import annotations

import shutil
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .domain import GPU_STAGES, IO_STAGES, STAGE_ORDER, SourceIdentity, Stage, StageStatus, WorkerItem
from .filename_parser import local_datetime_to_offset_iso, parse_meeting_filename
from .media import PRESETS, estimate_output_bytes
from .orchestrator import Orchestrator
from .state import StateStore

SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".webm"})


@dataclass(frozen=True)
class ClientChoice:
    id: int
    name: str


@dataclass(frozen=True)
class StageView:
    stage: Stage
    status: StageStatus
    attempts: int
    user_error: str | None
    diagnostic: str | None


@dataclass(frozen=True)
class ItemView:
    item: WorkerItem
    stages: tuple[StageView, ...]
    completed_stages: int
    active_stage: Stage | None
    status: str
    probe_summary: str
    estimated_size: str
    final_size: str | None
    metadata_locked: bool
    removable: bool
    retryable_artifacts: tuple[str, ...]


@dataclass(frozen=True)
class PipelineStageProgress:
    key: str
    label: str
    weight: int
    fraction: float
    active: bool
    completed: bool


@dataclass(frozen=True)
class PipelineProgress:
    stages: tuple[PipelineStageProgress, ...]
    overall_percent: int


def pipeline_progress(
    view: ItemView,
    transient: tuple[Stage, int] | None = None,
) -> PipelineProgress:
    statuses = {stage.stage: stage.status for stage in view.stages}
    active_stage, active_percent = transient or (view.active_stage, 0)
    active_fraction = min(max(active_percent / 100, 0.0), 1.0)

    def stage_fraction(stage: Stage) -> float:
        if statuses[stage] is StageStatus.SUCCEEDED:
            return 1.0
        return active_fraction if active_stage is stage else 0.0

    audio_fraction = stage_fraction(Stage.WAV)
    upload_sizes = {
        Stage.VIDEO_UPLOAD: view.item.selected_video_bytes or 0,
        Stage.AUDIO_UPLOAD: view.item.audio_bytes or 0,
        Stage.TRANSCRIPT_UPLOAD: view.item.transcript_bytes or 0,
    }
    upload_total = sum(upload_sizes.values())
    uploaded = float(
        sum(size for stage, size in upload_sizes.items() if statuses[stage] is StageStatus.SUCCEEDED)
    )
    if active_stage in upload_sizes:
        uploaded += upload_sizes[active_stage] * active_fraction
    uploads_succeeded = all(statuses[stage] is StageStatus.SUCCEEDED for stage in upload_sizes)
    upload_fraction = uploaded / upload_total if upload_total else 0.0
    if statuses[Stage.FINAL_RECONCILE] is StageStatus.SUCCEEDED:
        upload_fraction = 1.0
    elif uploads_succeeded:
        upload_fraction = min(upload_fraction, 0.99)

    stages = [
        PipelineStageProgress(
            "audio",
            "Audio convert",
            5,
            audio_fraction,
            active_stage in {Stage.PROBE, Stage.WAV},
            statuses[Stage.WAV] is StageStatus.SUCCEEDED,
        )
    ]
    if view.item.compression_preset != "none":
        stages.append(
            PipelineStageProgress(
                "compression",
                "Compression",
                25,
                stage_fraction(Stage.SOURCE),
                active_stage is Stage.SOURCE,
                statuses[Stage.SOURCE] is StageStatus.SUCCEEDED,
            )
        )
    stages.extend(
        (
            PipelineStageProgress(
                "transcript",
                "Transcript",
                40,
                stage_fraction(Stage.TRANSCRIBE),
                active_stage is Stage.TRANSCRIBE,
                statuses[Stage.TRANSCRIBE] is StageStatus.SUCCEEDED,
            ),
            PipelineStageProgress(
                "upload",
                "Upload ingestion",
                30,
                upload_fraction,
                active_stage
                in {
                    Stage.MEETING,
                    Stage.VIDEO_UPLOAD,
                    Stage.AUDIO_UPLOAD,
                    Stage.TRANSCRIPT_UPLOAD,
                    Stage.FINAL_RECONCILE,
                },
                statuses[Stage.FINAL_RECONCILE] is StageStatus.SUCCEEDED,
            ),
        )
    )
    total_weight = sum(stage.weight for stage in stages)
    overall = round(sum(stage.weight * stage.fraction for stage in stages) / total_weight * 100)
    return PipelineProgress(tuple(stages), overall)


@dataclass(frozen=True)
class AddResult:
    added: tuple[str, ...]
    existing: tuple[str, ...]
    errors: tuple[str, ...]


class ApiWithClients(Protocol):
    def list_clients(self) -> list[dict[str, object]]: ...


def _required_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid {label} in worker state.")
    return value


def human_bytes(byte_count: int | None) -> str:
    if byte_count is None:
        return "—"
    value = float(byte_count)
    units = ("B", "KB", "MB", "GB", "TB")
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"


def offset_iso_to_local(value: str | None, timezone: str) -> str:
    if value is None:
        return ""
    from zoneinfo import ZoneInfo

    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    return (
        datetime.fromisoformat(normalized)
        .astimezone(ZoneInfo(timezone))
        .replace(tzinfo=None)
        .isoformat(timespec="seconds")
    )


class QueueController:
    """Qt-independent queue presentation and transactional user mutations."""

    def __init__(
        self,
        store: StateStore,
        api: ApiWithClients,
        *,
        timezone: str,
        default_preset: str = "crf22",
        default_language: str = "ro",
        work_dir: Path | None = None,
        api_base_url: str | None = None,
    ) -> None:
        self.store = store
        self.api = api
        self.timezone = timezone
        self.default_preset = default_preset
        self.default_language = default_language
        self.work_dir = work_dir
        self.api_base_url = api_base_url.rstrip("/") if api_base_url else None

    def add_paths(self, paths: Iterable[str | Path]) -> AddResult:
        added: list[str] = []
        existing: list[str] = []
        errors: list[str] = []
        seen: set[str] = set()
        for raw in paths:
            path = Path(raw)
            try:
                canonical = path.resolve(strict=True)
            except OSError as exception:
                errors.append(f"{path}: file is unavailable ({exception}).")
                continue
            canonical_text = str(canonical)
            key = canonical_text.casefold()
            if key in seen:
                existing.append(canonical_text)
                continue
            seen.add(key)
            if not canonical.is_file():
                errors.append(f"{canonical}: not a file.")
                continue
            if canonical.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
                errors.append(f"{canonical.name}: unsupported video type.")
                continue
            prior = self.store.find_item_by_source_path(canonical_text)
            if prior is not None:
                existing.append(prior.item_id)
                continue
            suggestion = parse_meeting_filename(canonical_text)
            title = suggestion.title or canonical.stem
            meeting_at = None
            if suggestion.local_datetime is not None:
                try:
                    meeting_at = local_datetime_to_offset_iso(suggestion.local_datetime, self.timezone)
                except ValueError as exception:
                    errors.append(f"{canonical.name}: {exception}")
                    continue
            item = WorkerItem(
                source=SourceIdentity.from_path(canonical),
                title=title,
                meeting_at=meeting_at,
                compression_preset=self.default_preset,
                language=self.default_language,
            )
            self.store.add_item(item)
            added.append(item.item_id)
        return AddResult(tuple(added), tuple(existing), tuple(errors))

    def load_clients(self) -> tuple[ClientChoice, ...]:
        clients: list[ClientChoice] = []
        for raw in self.api.list_clients():
            client_id = raw.get("id")
            name = raw.get("name")
            if isinstance(client_id, bool) or not isinstance(client_id, int) or client_id <= 0:
                raise ValueError("Server returned an invalid client ID.")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Server returned an invalid client name.")
            clients.append(ClientChoice(client_id, name.strip()))
        return tuple(clients)

    def update_metadata(
        self,
        item_id: str,
        *,
        title: str,
        local_datetime: str | None,
        client_id: int | None,
    ) -> WorkerItem:
        local = local_datetime.strip() if local_datetime else ""
        meeting_at = local_datetime_to_offset_iso(local, self.timezone) if local else None
        return self.store.update_metadata(
            item_id,
            title=title,
            meeting_at=meeting_at,
            client_id=client_id,
        )

    def set_preset(self, item_id: str, preset: str) -> bool:
        return self.store.set_compression_preset(item_id, preset)

    def set_language(self, item_id: str, language: str) -> bool:
        return self.store.set_language(item_id, language)

    def remove(self, item_id: str) -> None:
        if self.view(item_id).metadata_locked:
            self.store.delete_reconciled_item(item_id)
        else:
            self.store.delete_pre_server_item(item_id)
        self._cleanup_work_dir(item_id)

    def _cleanup_work_dir(self, item_id: str) -> None:
        if self.work_dir is None:
            return
        shutil.rmtree(self.work_dir / item_id, ignore_errors=True)

    def views(self) -> tuple[ItemView, ...]:
        return tuple(self.view(item.item_id) for item in self.store.list_items())

    def view(self, item_id: str) -> ItemView:
        item = self.store.get_item(item_id)
        stages = tuple(
            StageView(
                stage=Stage(str(row["stage"])),
                status=StageStatus(str(row["status"])),
                attempts=_required_int(row["attempts"], "stage attempts"),
                user_error=str(row["user_error"]) if row["user_error"] else None,
                diagnostic=str(row["diagnostic"]) if row["diagnostic"] else None,
            )
            for row in self.store.stages(item_id)
        )
        active = next((stage.stage for stage in stages if stage.status is StageStatus.RUNNING), None)
        failed = next((stage for stage in stages if stage.status is StageStatus.FAILED), None)
        completed = sum(stage.status is StageStatus.SUCCEEDED for stage in stages)
        if completed == len(STAGE_ORDER):
            status = "Completed"
        elif active is not None:
            status = f"Processing · {active.value.replace('_', ' ')}"
        elif failed is not None:
            status = f"Needs attention · {failed.stage.value.replace('_', ' ')}"
        else:
            status = "Ready"
        probe_summary = "Waiting for media probe"
        if item.probe_width and item.probe_height and item.probe_fps is not None:
            minutes, seconds = divmod(item.duration_seconds or 0, 60)
            probe_summary = (
                f"{minutes:d}:{seconds:02d} · {item.probe_width}x{item.probe_height} · "
                f"{item.probe_fps:.2f} FPS"
            )
        estimate = item.source.size
        preset = PRESETS[item.compression_preset]
        if preset is not None and item.duration_seconds is not None:
            estimate = estimate_output_bytes(
                float(item.duration_seconds),
                preset,
                source_size=item.source.size,
                source_bitrate=item.probe_bitrate,
            )
        return ItemView(
            item=item,
            stages=stages,
            completed_stages=completed,
            active_stage=active,
            status=status,
            probe_summary=probe_summary,
            estimated_size=human_bytes(estimate),
            final_size=human_bytes(item.selected_video_bytes) if item.selected_video_bytes else None,
            metadata_locked=(
                item.server_meeting_id is not None
                or next(stage for stage in stages if stage.stage is Stage.MEETING).attempts > 0
            ),
            removable=(
                item.server_meeting_id is None
                and next(stage for stage in stages if stage.stage is Stage.MEETING).attempts == 0
            )
            or completed == len(STAGE_ORDER),
            retryable_artifacts=tuple(
                name
                for name, local_stage, upload_stage in (
                    ("video", Stage.SOURCE, Stage.VIDEO_UPLOAD),
                    ("audio", Stage.WAV, Stage.AUDIO_UPLOAD),
                    ("transcript", Stage.TRANSCRIBE, Stage.TRANSCRIPT_UPLOAD),
                )
                if item.server_meeting_id is not None
                and next(stage for stage in stages if stage.stage is local_stage).status
                is StageStatus.SUCCEEDED
                and (
                    next(stage for stage in stages if stage.stage is upload_stage).status
                    is StageStatus.FAILED
                    or (
                        next(stage for stage in stages if stage.stage is upload_stage).status
                        is StageStatus.PENDING
                        and next(stage for stage in stages if stage.stage is upload_stage).attempts > 0
                    )
                )
            ),
        )


EventSink = Callable[[str, str, object | None], None]


class ProcessingCoordinator:
    """Two execution lanes: a sequential GPU lane and a concurrent IO lane.

    The GPU lane runs probe/source/wav/transcribe for one item at a time so only
    one ASR model lives in VRAM. As soon as an item finishes transcribing, the GPU
    lane starts the next item while the finished item's meeting creation and uploads
    proceed on the IO lane.
    """

    def __init__(self, orchestrator: Orchestrator, event_sink: EventSink | None = None) -> None:
        self.orchestrator = orchestrator
        self._event_sink = event_sink or (lambda _kind, _item_id, _value: None)
        self._gpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minutory-gpu")
        self._io_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="minutory-io")
        self._lock = threading.RLock()
        self._scheduled: dict[str, str] = {}
        self._gpu_item: str | None = None
        self._gpu_stage: Stage | None = None
        self._io_stages: dict[str, Stage | None] = {}
        self._progress: dict[str, tuple[Stage, int]] = {}
        self._cancel = threading.Event()
        self._closed = False

    def start(self, item_id: str) -> bool:
        return self._submit(item_id, "pipeline")

    def preflight(self, item_id: str) -> bool:
        return self._submit(item_id, "preflight")

    def retry_artifact(self, item_id: str, artifact_name: str) -> bool:
        if artifact_name not in {"video", "audio", "transcript"}:
            raise ValueError(f"Unsupported artifact {artifact_name!r}.")
        return self._submit(item_id, f"artifact:{artifact_name}")

    def _submit(self, item_id: str, operation: str) -> bool:
        with self._lock:
            if self._closed or item_id in self._scheduled:
                return False
            self._scheduled[item_id] = operation
            if operation == "pipeline":
                self._submit_gpu(item_id, "pipeline")
            elif operation == "preflight":
                self._submit_gpu(item_id, "preflight")
            else:
                self._submit_io(item_id, operation)
            return True

    def _submit_gpu(self, item_id: str, operation: str) -> None:
        future = self._gpu_executor.submit(self._run_gpu, item_id, operation)
        future.add_done_callback(lambda result: self._gpu_done(item_id, operation, result))

    def _submit_io(self, item_id: str, operation: str) -> None:
        with self._lock:
            if self._closed:
                self._scheduled.pop(item_id, None)
                self._event_sink("deferred", item_id, "Item deferred — will resume on next start.")
                return
            future = self._io_executor.submit(self._run_io, item_id, operation)
        future.add_done_callback(lambda result: self._io_done(item_id, operation, result))

    def start_pending(self) -> int:
        count = 0
        for item in self.orchestrator.store.list_items():
            stages = self.orchestrator.store.stages(item.item_id)
            if any(row["status"] != StageStatus.SUCCEEDED.value for row in stages):
                count += int(self.start(item.item_id))
        return count

    def preflight_unprobed(self) -> int:
        count = 0
        for item in self.orchestrator.store.list_items():
            if (
                self.orchestrator.store.stage(item.item_id, Stage.PROBE)["status"]
                != StageStatus.SUCCEEDED.value
            ):
                count += int(self.preflight(item.item_id))
        return count

    def _run_gpu(self, item_id: str, operation: str) -> WorkerItem:
        with self._lock:
            self._gpu_item = item_id
            self._gpu_stage = None
            self._cancel = threading.Event()
            cancel = self._cancel
        self._event_sink("started", item_id, None)

        def stage_changed(stage: Stage, status: StageStatus) -> None:
            with self._lock:
                self._gpu_stage = stage if status is StageStatus.RUNNING else None
                if status is StageStatus.RUNNING:
                    self._progress[item_id] = (stage, 0)
                else:
                    current = self._progress.get(item_id)
                    if current is not None and current[0] is stage:
                        self._progress.pop(item_id, None)
            self._event_sink("stage", item_id, (stage, status))

        last_percent = {"value": -1}

        def progress(fraction: float) -> None:
            percent = int(min(max(fraction, 0.0), 1.0) * 100)
            if percent != last_percent["value"]:
                last_percent["value"] = percent
                with self._lock:
                    stage = self._gpu_stage
                    if stage is not None:
                        self._progress[item_id] = (stage, percent)
                if stage is not None:
                    self._event_sink("progress", item_id, (stage, percent))

        try:
            if operation == "preflight":
                return self.orchestrator.preflight(
                    item_id,
                    cancel=cancel,
                    on_stage=stage_changed,
                    on_progress=progress,
                )
            return self.orchestrator.process_stages(
                item_id,
                GPU_STAGES,
                cancel=cancel,
                on_stage=stage_changed,
                on_progress=progress,
            )
        finally:
            with self._lock:
                self._gpu_item = None
                self._gpu_stage = None

    def _run_io(self, item_id: str, operation: str) -> WorkerItem:
        if operation.startswith("artifact:"):
            self._event_sink("started", item_id, None)

        def stage_changed(stage: Stage, status: StageStatus) -> None:
            with self._lock:
                self._io_stages[item_id] = stage if status is StageStatus.RUNNING else None
                if status is StageStatus.RUNNING:
                    self._progress[item_id] = (stage, 0)
                else:
                    current = self._progress.get(item_id)
                    if current is not None and current[0] is stage:
                        self._progress.pop(item_id, None)
            self._event_sink("stage", item_id, (stage, status))

        last_percent = {"value": -1}

        def progress(fraction: float) -> None:
            percent = int(min(max(fraction, 0.0), 1.0) * 100)
            if percent != last_percent["value"]:
                last_percent["value"] = percent
                with self._lock:
                    stage = self._io_stages.get(item_id)
                    if stage is not None:
                        self._progress[item_id] = (stage, percent)
                if stage is not None:
                    self._event_sink("progress", item_id, (stage, percent))

        try:
            if operation.startswith("artifact:"):
                return self.orchestrator.retry_artifact(
                    item_id,
                    operation.removeprefix("artifact:"),
                    on_stage=stage_changed,
                    on_progress=progress,
                )
            return self.orchestrator.process_stages(
                item_id,
                IO_STAGES,
                on_stage=stage_changed,
                on_progress=progress,
            )
        finally:
            with self._lock:
                self._io_stages.pop(item_id, None)

    def _gpu_done(self, item_id: str, operation: str, future: Future[WorkerItem]) -> None:
        try:
            result: object = future.result()
        except Exception as exception:
            self._finalize(item_id, "failed", exception)
            return
        if operation == "pipeline":
            self._submit_io(item_id, "pipeline-io")
            return
        self._finalize(item_id, "preflight_completed", result)

    def _io_done(self, item_id: str, operation: str, future: Future[WorkerItem]) -> None:
        try:
            result: object = future.result()
            kind = "artifact_completed" if operation.startswith("artifact:") else "completed"
        except Exception as exception:
            result = exception
            kind = "failed"
        self._finalize(item_id, kind, result)

    def _finalize(self, item_id: str, kind: str, result: object) -> None:
        with self._lock:
            self._scheduled.pop(item_id, None)
        self._event_sink(kind, item_id, result)

    def cancel_current_media(self) -> bool:
        with self._lock:
            if self._gpu_item is None or self._gpu_stage not in {Stage.SOURCE, Stage.WAV}:
                return False
            self._cancel.set()
            return True

    @property
    def transcription_active(self) -> bool:
        with self._lock:
            return self._gpu_stage is Stage.TRANSCRIBE

    @property
    def current_stage(self) -> Stage | None:
        with self._lock:
            if self._gpu_stage is not None:
                return self._gpu_stage
            for stage in self._io_stages.values():
                if stage is not None:
                    return stage
            return None

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._scheduled)

    def is_scheduled(self, item_id: str) -> bool:
        with self._lock:
            return item_id in self._scheduled

    def active_stage(self, item_id: str) -> Stage | None:
        with self._lock:
            if self._gpu_item == item_id:
                return self._gpu_stage
            return self._io_stages.get(item_id)

    def item_progress(self, item_id: str) -> tuple[Stage, int] | None:
        with self._lock:
            return self._progress.get(item_id)

    def close(self) -> bool:
        with self._lock:
            if self._gpu_stage is Stage.TRANSCRIBE:
                return False
            self._closed = True
            if self._gpu_item is not None:
                self._cancel.set()
        self._gpu_executor.shutdown(wait=True, cancel_futures=True)
        self._io_executor.shutdown(wait=True, cancel_futures=True)
        return True


def diagnostic_text(view: ItemView) -> str:
    lines = [
        f"Item: {view.item.item_id}",
        f"Source: {view.item.source.path}",
        f"Meeting: {view.item.server_meeting_id or 'not created'}",
        f"Rendered: {datetime.now(UTC).isoformat(timespec='seconds')}",
    ]
    for stage in view.stages:
        lines.append(
            f"{stage.stage.value}: {stage.status.value}; attempts={stage.attempts}"
            + (f"; error={stage.user_error}" if stage.user_error else "")
            + (f"\n{stage.diagnostic}" if stage.diagnostic else "")
        )
    return "\n".join(lines)
