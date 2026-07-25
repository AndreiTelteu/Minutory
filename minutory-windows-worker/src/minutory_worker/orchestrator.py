from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .api import ApiError, WorkerApiClient
from .domain import (
    STAGE_ORDER,
    SourceIdentity,
    Stage,
    StageStatus,
    WorkerItem,
    stream_sha256,
)
from .media import MediaService
from .state import StateError, StateStore
from .whisper import WhisperService


class PipelineError(RuntimeError):
    pass


class ArtifactConflict(PipelineError):
    pass


class DataIntegrityError(PipelineError):
    pass


class RemoteArtifactMissing(PipelineError):
    pass


ARTIFACT_STAGES: dict[str, tuple[Stage, Stage]] = {
    "video": (Stage.SOURCE, Stage.VIDEO_UPLOAD),
    "audio": (Stage.WAV, Stage.AUDIO_UPLOAD),
    "transcript": (Stage.TRANSCRIBE, Stage.TRANSCRIPT_UPLOAD),
}


class Orchestrator:
    def __init__(
        self,
        store: StateStore,
        media: MediaService,
        whisper: WhisperService,
        api: WorkerApiClient,
        work_dir: Path,
        *,
        video_codec: str = "h264_amf",
        fallback_video_codec: str = "libx264",
    ) -> None:
        self.store = store
        self.media = media
        self.whisper = whisper
        self.api = api
        self.work_dir = work_dir
        self.video_codec = video_codec
        self.fallback_video_codec = fallback_video_codec

    def refresh_source(self, item_id: str, *, hash_source: bool = False) -> bool:
        item = self.store.get_item(item_id)
        current = SourceIdentity.from_path(Path(item.source.path), hash_source=hash_source)
        comparable_hash_changed = (
            item.source.sha256 is not None
            and current.sha256 is not None
            and item.source.sha256 != current.sha256
        )
        changed = (
            current.path != item.source.path
            or current.size != item.source.size
            or current.mtime_ns != item.source.mtime_ns
            or comparable_hash_changed
        )
        if not changed:
            return False
        try:
            return self.store.replace_source_identity(
                item_id,
                expected=item.source,
                replacement=current,
            )
        except StateError as exception:
            if "server meeting attempt" in str(exception):
                raise ArtifactConflict(
                    "Source file changed after the server meeting was created; "
                    "create a new worker item instead of mutating uploaded history."
                ) from exception
            raise

    def preflight(
        self,
        item_id: str,
        *,
        on_stage: Callable[[Stage, StageStatus], None] | None = None,
    ) -> WorkerItem:
        """Run only the media probe so the operator can review metadata and size."""
        self.refresh_source(item_id)
        status = str(self.store.stage(item_id, Stage.PROBE)["status"])
        if status == StageStatus.SUCCEEDED.value:
            return self.store.get_item(item_id)
        if status == StageStatus.RUNNING.value:
            raise PipelineError("Stage probe is already running.")
        self._run_stage(item_id, Stage.PROBE, on_stage=on_stage)
        return self.store.get_item(item_id)

    def retry_artifact(
        self,
        item_id: str,
        artifact_name: str,
        *,
        on_stage: Callable[[Stage, StageStatus], None] | None = None,
    ) -> WorkerItem:
        """Reconcile, then upload only the explicitly requested local artifact."""
        if artifact_name not in ARTIFACT_STAGES:
            raise ValueError(f"Unsupported artifact {artifact_name!r}.")
        local_stage, upload_stage = ARTIFACT_STAGES[artifact_name]
        if self.store.stage(item_id, local_stage)["status"] != StageStatus.SUCCEEDED.value:
            raise PipelineError(
                f"{artifact_name.title()} cannot be retried before {local_stage.value} succeeds."
            )
        item = self.store.get_item(item_id)
        self._verify_local_artifact(*self._local_artifact(item, artifact_name)[:3])
        if item.server_meeting_id is None:
            raise PipelineError("Artifact upload requires an existing server meeting.")
        self._reconcile(item)
        if self.store.stage(item_id, upload_stage)["status"] != StageStatus.SUCCEEDED.value:
            self._run_stage(item_id, upload_stage, on_stage=on_stage)
        uploads = (Stage.VIDEO_UPLOAD, Stage.AUDIO_UPLOAD, Stage.TRANSCRIPT_UPLOAD)
        if all(
            self.store.stage(item_id, stage)["status"] == StageStatus.SUCCEEDED.value for stage in uploads
        ):
            final_status = self.store.stage(item_id, Stage.FINAL_RECONCILE)["status"]
            if final_status != StageStatus.SUCCEEDED.value:
                self._run_stage(item_id, Stage.FINAL_RECONCILE, on_stage=on_stage)
        return self.store.get_item(item_id)

    def process(
        self,
        item_id: str,
        *,
        cancel: threading.Event | None = None,
        on_stage: Callable[[Stage, StageStatus], None] | None = None,
    ) -> WorkerItem:
        self.refresh_source(item_id)
        item = self.store.get_item(item_id)
        if item.server_meeting_id is not None:
            self._reconcile(item)
            item = self.store.get_item(item_id)
        for stage in STAGE_ORDER:
            status = str(self.store.stage(item_id, stage)["status"])
            if status == StageStatus.SUCCEEDED.value:
                continue
            if status == StageStatus.RUNNING.value:
                raise PipelineError(f"Stage {stage.value} is already running.")
            self._run_stage(item_id, stage, cancel=cancel, on_stage=on_stage)
        return self.store.get_item(item_id)

    def process_next_stage(
        self,
        item_id: str,
        *,
        cancel: threading.Event | None = None,
        on_stage: Callable[[Stage, StageStatus], None] | None = None,
    ) -> Stage | None:
        self.refresh_source(item_id)
        item = self.store.get_item(item_id)
        if item.server_meeting_id is not None:
            self._reconcile(item)
        for stage in STAGE_ORDER:
            status = str(self.store.stage(item_id, stage)["status"])
            if status == StageStatus.SUCCEEDED.value:
                continue
            if status == StageStatus.RUNNING.value:
                raise PipelineError(f"Stage {stage.value} is already running.")
            self._run_stage(item_id, stage, cancel=cancel, on_stage=on_stage)
            return stage
        return None

    def _run_stage(
        self,
        item_id: str,
        stage: Stage,
        *,
        cancel: threading.Event | None = None,
        on_stage: Callable[[Stage, StageStatus], None] | None = None,
    ) -> None:
        self.store.start_stage(item_id, stage)
        if on_stage is not None:
            on_stage(stage, StageStatus.RUNNING)
        try:
            item = self.store.get_item(item_id)
            self._execute(item, stage, cancel=cancel)
            self.store.persist_stage_output(item, stage)
            self.store.finish_stage(item_id, stage)
            if on_stage is not None:
                on_stage(stage, StageStatus.SUCCEEDED)
        except Exception as exception:
            diagnostic = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )
            user_error = self._user_error(exception)
            self.store.fail_stage(item_id, stage, user_error, diagnostic)
            if on_stage is not None:
                on_stage(stage, StageStatus.FAILED)
            raise

    def _execute(self, item: WorkerItem, stage: Stage, *, cancel: threading.Event | None = None) -> None:
        item_dir = self.work_dir / item.item_id
        item_dir.mkdir(parents=True, exist_ok=True)
        source = Path(item.source.path)
        if stage is Stage.PROBE:
            probe = self.media.probe(source)
            item.duration_seconds = round(probe.duration)
            item.probe_width = probe.width
            item.probe_height = probe.height
            item.probe_fps = probe.fps
            item.probe_bitrate = probe.bitrate
        elif stage is Stage.SOURCE:
            extension = source.suffix.lower() or ".mp4"
            if item.compression_preset != "none":
                extension = ".mp4"
            selected = item_dir / f"video{extension}"
            self.media.select_video(
                source,
                selected,
                item.compression_preset,
                codec=self.video_codec,
                fallback_codec=self.fallback_video_codec,
                cancel=cancel,
            )
            item.selected_video_path = str(selected)
            item.selected_video_sha256 = stream_sha256(selected)
            item.selected_video_bytes = selected.stat().st_size
        elif stage is Stage.WAV:
            wav = item_dir / "audio.wav"
            self.media.extract_wav(
                Path(_required(item.selected_video_path, "selected video")),
                wav,
                cancel=cancel,
            )
            item.wav_path = str(wav)
            item.audio_sha256 = stream_sha256(wav)
            item.audio_bytes = wav.stat().st_size
        elif stage is Stage.TRANSCRIBE:
            transcript = item_dir / "transcript.json"
            self.whisper.transcribe(Path(_required(item.wav_path, "WAV")), transcript)
            item.transcript_path = str(transcript)
            item.transcript_sha256 = stream_sha256(transcript)
            item.transcript_bytes = transcript.stat().st_size
        elif stage is Stage.MEETING:
            meeting = self.api.create_meeting(item)
            item.server_meeting_id = meeting.id
        elif stage is Stage.VIDEO_UPLOAD:
            self._upload(item, "video")
        elif stage is Stage.AUDIO_UPLOAD:
            self._upload(item, "audio")
        elif stage is Stage.TRANSCRIPT_UPLOAD:
            self._upload(item, "transcript")
        elif stage is Stage.FINAL_RECONCILE:
            self._reconcile(item, final_stage_running=True)
        else:  # pragma: no cover
            raise AssertionError(stage)

    def _upload(self, item: WorkerItem, artifact_name: str) -> None:
        path, expected_hash, expected_bytes, _ = self._local_artifact(item, artifact_name)
        actual_hash, actual_bytes = self._verify_local_artifact(path, expected_hash, expected_bytes)
        result = self.api.upload_artifact(
            _required_int(item.server_meeting_id, "server meeting"),
            artifact_name,
            path,
        )
        if result.sha256 != actual_hash or result.bytes != actual_bytes:
            raise DataIntegrityError(
                f"Server {artifact_name} upload response does not match the uploaded artifact."
            )

    def _reconcile(self, item: WorkerItem, *, final_stage_running: bool = False) -> None:
        remote = self.api.reconcile(_required_int(item.server_meeting_id, "server meeting"))
        if remote.worker_item_id.lower() != item.item_id.lower():
            raise PipelineError("Server meeting belongs to a different worker item.")
        if remote.client_id != item.client_id or remote.title != item.title:
            raise ArtifactConflict("Server meeting metadata conflicts with local state.")
        if remote.start_transcript_server:
            raise ArtifactConflict("Server meeting unexpectedly owns transcription.")
        if remote.duration_seconds != item.duration_seconds or not _same_instant(
            remote.meeting_at, item.meeting_at
        ):
            raise ArtifactConflict("Server meeting time or duration conflicts with local state.")
        all_uploaded = True
        missing: list[tuple[str, Stage]] = []
        for artifact_name in ("video", "audio", "transcript"):
            _, local_hash, local_bytes, stage = self._local_artifact(item, artifact_name)
            artifact = remote.artifacts[artifact_name]
            if not artifact.uploaded:
                all_uploaded = False
                missing.append((artifact_name, stage))
                self.store.reset_remote_missing(item.item_id, stage)
                continue
            if (
                local_hash is None
                or local_bytes is None
                or artifact.sha256 != local_hash
                or artifact.bytes != local_bytes
            ):
                raise ArtifactConflict(
                    f"Server has a different {artifact_name} artifact; "
                    "replacement requires explicit operator action."
                )
            self.store.reconcile_success(item.item_id, stage)
        self.store.reconcile_success(item.item_id, Stage.MEETING)
        if all_uploaded:
            if not final_stage_running:
                self.store.reconcile_success(item.item_id, Stage.FINAL_RECONCILE)
        elif final_stage_running:
            names = ", ".join(name for name, _ in missing)
            raise RemoteArtifactMissing(f"Server final reconciliation reports missing artifacts: {names}.")

    @staticmethod
    def _local_artifact(
        item: WorkerItem,
        artifact_name: str,
    ) -> tuple[Path, str | None, int | None, Stage]:
        values = {
            "video": (
                item.selected_video_path,
                item.selected_video_sha256,
                item.selected_video_bytes,
                Stage.VIDEO_UPLOAD,
            ),
            "audio": (
                item.wav_path,
                item.audio_sha256,
                item.audio_bytes,
                Stage.AUDIO_UPLOAD,
            ),
            "transcript": (
                item.transcript_path,
                item.transcript_sha256,
                item.transcript_bytes,
                Stage.TRANSCRIPT_UPLOAD,
            ),
        }
        path, digest, byte_count, stage = values[artifact_name]
        return Path(_required(path, f"{artifact_name} artifact")), digest, byte_count, stage

    @staticmethod
    def _verify_local_artifact(
        path: Path,
        expected_hash: str | None,
        expected_bytes: int | None,
    ) -> tuple[str, int]:
        if not path.is_file() or expected_hash is None or expected_bytes is None:
            raise DataIntegrityError(f"Local artifact {path.name} is missing expected integrity data.")
        actual_bytes = path.stat().st_size
        actual_hash = stream_sha256(path)
        if actual_hash != expected_hash or actual_bytes != expected_bytes:
            raise DataIntegrityError(
                f"Local artifact {path.name} changed after generation; regenerate it before upload."
            )
        return actual_hash, actual_bytes

    @staticmethod
    def _user_error(exception: Exception) -> str:
        if isinstance(exception, ApiError):
            return f"Server request failed ({exception.code}): {exception}"
        if isinstance(exception, (ArtifactConflict, DataIntegrityError, RemoteArtifactMissing)):
            return str(exception)
        return str(exception) or exception.__class__.__name__


def _required(value: str | None, name: str) -> str:
    if value is None:
        raise PipelineError(f"Missing {name}.")
    return value


def _required_int(value: int | None, name: str) -> int:
    if value is None:
        raise PipelineError(f"Missing {name}.")
    return value


def _same_instant(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right

    def parse(value: str) -> datetime:
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            raise ArtifactConflict("Meeting datetime is missing a UTC offset.")
        return parsed.astimezone(UTC)

    try:
        return parse(left) == parse(right)
    except ValueError as exception:
        raise ArtifactConflict("Meeting datetime is invalid.") from exception
