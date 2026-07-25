from __future__ import annotations

import traceback
from datetime import UTC, datetime
from pathlib import Path

from .api import ApiError, WorkerApiClient
from .domain import (
    STAGE_ORDER,
    SourceIdentity,
    Stage,
    StageStatus,
    WorkerItem,
    dependent_stages,
    stream_sha256,
)
from .media import MediaService
from .state import StateStore
from .whisper import WhisperService


class PipelineError(RuntimeError):
    pass


class ArtifactConflict(PipelineError):
    pass


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
        if item.server_meeting_id is not None:
            raise ArtifactConflict(
                "Source file changed after the server meeting was created; "
                "create a new worker item instead of mutating uploaded history."
            )
        item.source = current
        item.duration_seconds = None
        item.selected_video_path = None
        item.wav_path = None
        item.transcript_path = None
        item.selected_video_sha256 = None
        item.audio_sha256 = None
        item.transcript_sha256 = None
        self.store.save_item(item)
        self.store.invalidate(item_id, dependent_stages(Stage.PROBE))
        return True

    def process(self, item_id: str) -> WorkerItem:
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
            self._run_stage(item_id, stage)
        return self.store.get_item(item_id)

    def _run_stage(self, item_id: str, stage: Stage) -> None:
        self.store.start_stage(item_id, stage)
        try:
            item = self.store.get_item(item_id)
            self._execute(item, stage)
            self.store.save_item(item)
            self.store.finish_stage(item_id, stage)
        except Exception as exception:
            diagnostic = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )
            user_error = self._user_error(exception)
            self.store.fail_stage(item_id, stage, user_error, diagnostic)
            raise

    def _execute(self, item: WorkerItem, stage: Stage) -> None:
        item_dir = self.work_dir / item.item_id
        item_dir.mkdir(parents=True, exist_ok=True)
        source = Path(item.source.path)
        if stage is Stage.PROBE:
            probe = self.media.probe(source)
            item.duration_seconds = round(probe.duration)
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
            )
            item.selected_video_path = str(selected)
            item.selected_video_sha256 = stream_sha256(selected)
        elif stage is Stage.WAV:
            wav = item_dir / "audio.wav"
            self.media.extract_wav(Path(_required(item.selected_video_path, "selected video")), wav)
            item.wav_path = str(wav)
            item.audio_sha256 = stream_sha256(wav)
        elif stage is Stage.TRANSCRIBE:
            transcript = item_dir / "transcript.json"
            self.whisper.transcribe(Path(_required(item.wav_path, "WAV")), transcript)
            item.transcript_path = str(transcript)
            item.transcript_sha256 = stream_sha256(transcript)
        elif stage is Stage.MEETING:
            meeting = self.api.create_meeting(item)
            item.server_meeting_id = int(meeting["id"])
        elif stage is Stage.VIDEO_UPLOAD:
            self.api.upload_artifact(
                _required_int(item.server_meeting_id, "server meeting"),
                "video",
                Path(_required(item.selected_video_path, "selected video")),
            )
        elif stage is Stage.AUDIO_UPLOAD:
            self.api.upload_artifact(
                _required_int(item.server_meeting_id, "server meeting"),
                "audio",
                Path(_required(item.wav_path, "WAV")),
            )
        elif stage is Stage.TRANSCRIPT_UPLOAD:
            self.api.upload_artifact(
                _required_int(item.server_meeting_id, "server meeting"),
                "transcript",
                Path(_required(item.transcript_path, "transcript")),
            )
        else:  # pragma: no cover
            raise AssertionError(stage)

    def _reconcile(self, item: WorkerItem) -> None:
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
        hashes = {
            "video": (Stage.VIDEO_UPLOAD, item.selected_video_sha256),
            "audio": (Stage.AUDIO_UPLOAD, item.audio_sha256),
            "transcript": (Stage.TRANSCRIPT_UPLOAD, item.transcript_sha256),
        }
        for artifact_name, (stage, local_hash) in hashes.items():
            artifact = remote.artifacts[artifact_name]
            if not artifact.uploaded:
                continue
            if local_hash is None or artifact.sha256 != local_hash:
                raise ArtifactConflict(
                    f"Server has a different {artifact_name} artifact; "
                    "replacement requires explicit operator action."
                )
            self.store.reconcile_success(item.item_id, stage)
        self.store.reconcile_success(item.item_id, Stage.MEETING)

    @staticmethod
    def _user_error(exception: Exception) -> str:
        if isinstance(exception, ApiError):
            return f"Server request failed ({exception.code}): {exception}"
        if isinstance(exception, ArtifactConflict):
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
