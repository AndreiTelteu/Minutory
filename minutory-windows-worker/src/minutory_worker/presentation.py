from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .domain import STAGE_ORDER, SourceIdentity, Stage, StageStatus, WorkerItem
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
    metadata_locked: bool
    removable: bool
    retryable_artifacts: tuple[str, ...]


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
        default_preset: str = "balanced",
    ) -> None:
        self.store = store
        self.api = api
        self.timezone = timezone
        self.default_preset = default_preset

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

    def remove(self, item_id: str) -> None:
        if self.view(item_id).metadata_locked:
            self.store.delete_reconciled_item(item_id)
        else:
            self.store.delete_pre_server_item(item_id)

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
            estimate = estimate_output_bytes(float(item.duration_seconds), preset)
        return ItemView(
            item=item,
            stages=stages,
            completed_stages=completed,
            active_stage=active,
            status=status,
            probe_summary=probe_summary,
            estimated_size=human_bytes(estimate),
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
    """One long-lived execution lane; duplicate item starts are coalesced."""

    def __init__(self, orchestrator: Orchestrator, event_sink: EventSink | None = None) -> None:
        self.orchestrator = orchestrator
        self._event_sink = event_sink or (lambda _kind, _item_id, _value: None)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minutory-pipeline")
        self._lock = threading.RLock()
        self._scheduled: dict[str, str] = {}
        self._current_item: str | None = None
        self._current_stage: Stage | None = None
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
            future = self._executor.submit(self._run, item_id, operation)

            def done_callback(result: Future[WorkerItem]) -> None:
                self._done(item_id, operation, result)

            future.add_done_callback(done_callback)
            return True

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

    def _run(self, item_id: str, operation: str) -> WorkerItem:
        with self._lock:
            self._current_item = item_id
            self._cancel = threading.Event()
        self._event_sink("started", item_id, None)

        def stage_changed(stage: Stage, status: StageStatus) -> None:
            with self._lock:
                self._current_stage = stage if status is StageStatus.RUNNING else None
            self._event_sink("stage", item_id, (stage, status))

        last_percent = {"value": -1}

        def progress(fraction: float) -> None:
            percent = int(min(max(fraction, 0.0), 1.0) * 100)
            if percent != last_percent["value"]:
                last_percent["value"] = percent
                self._event_sink("progress", item_id, percent)

        if operation == "preflight":
            return self.orchestrator.preflight(item_id, on_stage=stage_changed)
        if operation.startswith("artifact:"):
            return self.orchestrator.retry_artifact(
                item_id,
                operation.removeprefix("artifact:"),
                on_stage=stage_changed,
            )
        return self.orchestrator.process(
            item_id,
            cancel=self._cancel,
            on_stage=stage_changed,
            on_progress=progress,
        )

    def _done(self, item_id: str, operation: str, future: Future[WorkerItem]) -> None:
        try:
            result: object | None = future.result()
            kind = {
                "preflight": "preflight_completed",
                "pipeline": "completed",
            }.get(operation, "artifact_completed")
        except Exception as exception:
            result = exception
            kind = "failed"
        with self._lock:
            self._scheduled.pop(item_id, None)
            if self._current_item == item_id:
                self._current_item = None
                self._current_stage = None
        self._event_sink(kind, item_id, result)

    def cancel_current_media(self) -> bool:
        with self._lock:
            if self._current_item is None or self._current_stage not in {Stage.SOURCE, Stage.WAV}:
                return False
            self._cancel.set()
            return True

    @property
    def transcription_active(self) -> bool:
        with self._lock:
            return self._current_stage is Stage.TRANSCRIBE

    @property
    def current_stage(self) -> Stage | None:
        with self._lock:
            return self._current_stage

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._scheduled)

    def is_scheduled(self, item_id: str) -> bool:
        with self._lock:
            return item_id in self._scheduled

    def close(self) -> bool:
        with self._lock:
            if self.transcription_active:
                return False
            self._closed = True
            if self._current_item is not None:
                self._cancel.set()
        self._executor.shutdown(wait=True, cancel_futures=True)
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
