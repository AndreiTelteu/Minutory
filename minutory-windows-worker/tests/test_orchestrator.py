from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path

import pytest
from conftest import pcm_wave

from minutory_worker.api import (
    ApiError,
    ArtifactState,
    ArtifactUploadResult,
    MeetingState,
    TransportFailure,
    WorkerApiClient,
)
from minutory_worker.domain import Stage, StageStatus, stream_sha256
from minutory_worker.media import CommandResult, MediaService
from minutory_worker.orchestrator import (
    ArtifactConflict,
    DataIntegrityError,
    Orchestrator,
    RemoteArtifactMissing,
)
from minutory_worker.presentation import QueueController, diagnostic_text
from minutory_worker.whisper import BackendResult, BackendSegment, WhisperService


class PipelineRunner:
    def __init__(self):
        self.probes = 0
        self.compresses = 0
        self.wavs = 0

    def run(self, command, **kwargs):
        if "-show_streams" in command:
            self.probes += 1
            return CommandResult(
                0,
                json.dumps(
                    {
                        "streams": [
                            {
                                "codec_type": "video",
                                "codec_name": "h264",
                                "width": 1920,
                                "height": 1080,
                                "avg_frame_rate": "30/1",
                            }
                        ],
                        "format": {
                            "duration": "10",
                            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                        },
                    }
                ),
                "",
            )
        if "-acodec" in command:
            self.wavs += 1
            Path(command[-1]).write_bytes(pcm_wave())
        else:
            self.compresses += 1
            Path(command[-1]).write_bytes(b"compressed-video")
        return CommandResult(0, "", "")


class PipelineBackend:
    model_name = "large-v3"

    def __init__(self):
        self.calls = 0

    def transcribe(self, audio_path, *, language, vad_filter, vad_parameters):
        self.calls += 1
        assert vad_parameters == {"min_silence_duration_ms": 500}
        return BackendResult(
            [BackendSegment(0, 1, "Salut")],
            "ro",
            0.99,
            1,
            {"device": "fake"},
        )


class FakeApi:
    def __init__(self, item):
        self.item = item
        self.meeting_id = 500
        self.created = 0
        self.reconciled = 0
        self.uploads: list[str] = []
        self.remote: dict[str, tuple[str, int] | None] = {
            "video": None,
            "audio": None,
            "transcript": None,
        }
        self.fail_audio_once = False
        self.response_mismatch: str | None = None
        self.drop_after_upload: str | None = None
        self.mutate_after_create: str | None = None

    def create_meeting(self, item):
        self.created += 1
        assert item.item_id == self.item.item_id
        self.item = item
        if self.mutate_after_create is not None:
            path = {
                "video": item.selected_video_path,
                "audio": item.wav_path,
                "transcript": item.transcript_path,
            }[self.mutate_after_create]
            Path(path).write_bytes(b"mutated-after-generation")
        return MeetingState(
            id=self.meeting_id,
            worker_item_id=item.item_id,
            client_id=item.client_id,
            title=item.title,
            meeting_at=item.meeting_at,
            duration_seconds=item.duration_seconds,
            start_transcript_server=False,
            artifacts={},
        )

    def upload_artifact(self, meeting_id, artifact, path, *, replace=False, on_progress=None):
        assert meeting_id == self.meeting_id
        assert not replace
        if on_progress is not None:
            on_progress(0.5)
        self.uploads.append(artifact)
        if artifact == "audio" and self.fail_audio_once:
            self.fail_audio_once = False
            raise ApiError("server_error", "temporary", 503, transient=True)
        digest = stream_sha256(path)
        byte_count = path.stat().st_size
        self.remote[artifact] = (digest, byte_count)
        if self.drop_after_upload == artifact:
            self.remote[artifact] = None
            self.drop_after_upload = None
        if self.response_mismatch == artifact:
            return ArtifactUploadResult("uploaded", "f" * 64, byte_count + 1)
        if on_progress is not None:
            on_progress(1.0)
        return ArtifactUploadResult("uploaded", digest, byte_count)

    def reconcile(self, meeting_id):
        self.reconciled += 1
        return MeetingState(
            id=meeting_id,
            worker_item_id=self.item.item_id,
            client_id=self.item.client_id,
            title=self.item.title,
            meeting_at=self.item.meeting_at,
            duration_seconds=self.item.duration_seconds,
            start_transcript_server=False,
            artifacts={
                name: ArtifactState(
                    value is not None,
                    value[0] if value is not None else None,
                    value[1] if value is not None else None,
                )
                for name, value in self.remote.items()
            },
        )


def services(store, item, tmp_path):
    runner = PipelineRunner()
    backend = PipelineBackend()
    api = FakeApi(item)
    orchestrator = Orchestrator(
        store,
        MediaService(Path("ffprobe"), Path("ffmpeg"), runner),
        WhisperService(backend),
        api,
        tmp_path / "work",
    )
    return orchestrator, runner, backend, api


def test_complete_pipeline_and_resume_does_not_repeat_work(store, item, tmp_path) -> None:
    orchestrator, runner, backend, api = services(store, item, tmp_path)
    completed = orchestrator.process(item.item_id)
    assert completed.server_meeting_id == 500
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (3, 1, 1, 1)
    assert api.created == 1
    assert api.uploads == ["video", "audio", "transcript"]
    assert api.reconciled == 1
    orchestrator.process(item.item_id)
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (3, 1, 1, 1)
    assert api.created == 1
    assert api.uploads == ["video", "audio", "transcript"]
    assert api.reconciled == 2
    assert all(store.stage(item.item_id, stage)["status"] == StageStatus.SUCCEEDED for stage in Stage)


def test_failed_upload_resume_preserves_expensive_successes(store, item, tmp_path) -> None:
    orchestrator, runner, backend, api = services(store, item, tmp_path)
    api.fail_audio_once = True
    with pytest.raises(ApiError):
        orchestrator.process(item.item_id)
    assert store.stage(item.item_id, Stage.VIDEO_UPLOAD)["status"] == StageStatus.SUCCEEDED
    assert store.stage(item.item_id, Stage.AUDIO_UPLOAD)["status"] == StageStatus.FAILED
    assert store.stage(item.item_id, Stage.TRANSCRIPT_UPLOAD)["status"] == StageStatus.PENDING
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (3, 1, 1, 1)
    orchestrator.process(item.item_id)
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (3, 1, 1, 1)
    assert api.uploads == ["video", "audio", "audio", "transcript"]
    assert store.stage(item.item_id, Stage.AUDIO_UPLOAD)["attempts"] == 2


def test_reconcile_surfaces_remote_hash_conflict_without_replacement(store, item, tmp_path) -> None:
    orchestrator, _, _, api = services(store, item, tmp_path)
    completed = orchestrator.process(item.item_id)
    api.remote["video"] = ("f" * 64, 123)
    with pytest.raises(ArtifactConflict, match="replacement requires explicit"):
        orchestrator.process(completed.item_id)
    assert api.uploads == ["video", "audio", "transcript"]


def test_source_change_after_server_creation_preserves_history(store, item, tmp_path) -> None:
    orchestrator, _, _, _ = services(store, item, tmp_path)
    completed = orchestrator.process(item.item_id)
    before = store.get_item(item.item_id)
    Path(completed.source.path).write_bytes(b"different-source")
    with pytest.raises(ArtifactConflict, match="new worker item"):
        orchestrator.process(item.item_id)
    after = store.get_item(item.item_id)
    assert after.source == before.source
    assert after.server_meeting_id == before.server_meeting_id


def test_reconcile_rejects_server_transcription_ownership(store, item, tmp_path) -> None:
    orchestrator, _, _, api = services(store, item, tmp_path)
    completed = orchestrator.process(item.item_id)
    original_reconcile = api.reconcile

    def unsafe(meeting_id):
        state = original_reconcile(meeting_id)
        return MeetingState(
            id=state.id,
            worker_item_id=state.worker_item_id,
            client_id=state.client_id,
            title=state.title,
            meeting_at=state.meeting_at,
            duration_seconds=state.duration_seconds,
            start_transcript_server=True,
            artifacts=state.artifacts,
        )

    api.reconcile = unsafe
    with pytest.raises(ArtifactConflict, match="owns transcription"):
        orchestrator.process(completed.item_id)


def test_remote_deletion_resets_success_and_reuploads_without_expensive_work(store, item, tmp_path) -> None:
    orchestrator, runner, backend, api = services(store, item, tmp_path)
    orchestrator.process(item.item_id)
    api.remote["video"] = None
    orchestrator.process(item.item_id)
    assert api.uploads == ["video", "audio", "transcript", "video"]
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (3, 1, 1, 1)
    assert store.stage(item.item_id, Stage.VIDEO_UPLOAD)["attempts"] == 2
    assert store.stage(item.item_id, Stage.FINAL_RECONCILE)["status"] == StageStatus.SUCCEEDED


def test_first_run_requires_remote_final_confirmation(store, item, tmp_path) -> None:
    orchestrator, _, _, api = services(store, item, tmp_path)
    api.drop_after_upload = "transcript"
    with pytest.raises(RemoteArtifactMissing, match="transcript"):
        orchestrator.process(item.item_id)
    assert api.reconciled == 1
    assert store.stage(item.item_id, Stage.TRANSCRIPT_UPLOAD)["status"] == StageStatus.PENDING
    assert store.stage(item.item_id, Stage.FINAL_RECONCILE)["status"] == StageStatus.FAILED
    orchestrator.process(item.item_id)
    assert api.uploads == ["video", "audio", "transcript", "transcript"]
    assert store.stage(item.item_id, Stage.FINAL_RECONCILE)["status"] == StageStatus.SUCCEEDED


def test_probe_preflight_stops_before_source(store, item, tmp_path) -> None:
    orchestrator, runner, backend, api = services(store, item, tmp_path)
    result = orchestrator.preflight(item.item_id)
    assert result.duration_seconds == 10
    assert store.stage(item.item_id, Stage.PROBE)["status"] == StageStatus.SUCCEEDED
    assert store.stage(item.item_id, Stage.SOURCE)["status"] == StageStatus.PENDING
    assert runner.compresses == 0
    assert backend.calls == 0
    assert api.created == 0


def test_preflight_eagerly_extracts_wav_and_pipeline_reuses_it(store, item, tmp_path) -> None:
    orchestrator, runner, _backend, api = services(store, item, tmp_path)
    result = orchestrator.preflight(item.item_id)
    assert store.stage(item.item_id, Stage.WAV)["status"] == StageStatus.SUCCEEDED
    assert store.stage(item.item_id, Stage.SOURCE)["status"] == StageStatus.PENDING
    assert result.wav_path is not None
    assert runner.wavs == 1
    completed = orchestrator.process(item.item_id)
    assert runner.wavs == 1
    assert completed.server_meeting_id == 500
    assert api.uploads == ["video", "audio", "transcript"]


def test_explicit_artifact_retry_uploads_only_requested_then_reconciles(store, item, tmp_path) -> None:
    orchestrator, runner, backend, api = services(store, item, tmp_path)
    orchestrator.process(item.item_id)
    before = (runner.probes, runner.compresses, runner.wavs, backend.calls)
    api.remote["audio"] = None
    orchestrator.retry_artifact(item.item_id, "audio")
    assert api.uploads == ["video", "audio", "transcript", "audio"]
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == before
    assert store.stage(item.item_id, Stage.FINAL_RECONCILE)["status"] == StageStatus.SUCCEEDED


def test_meeting_stage_refuses_concurrent_metadata_and_persists_only_meeting_id(
    store, item, tmp_path
) -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingApi:
        def create_meeting(self, stage_item):
            assert stage_item.client_id == 52
            entered.set()
            assert release.wait(2)
            return MeetingState(
                id=700,
                worker_item_id=stage_item.item_id,
                client_id=52,
                title=stage_item.title,
                meeting_at=stage_item.meeting_at,
                duration_seconds=stage_item.duration_seconds,
                start_transcript_server=False,
                artifacts={},
            )

    store.reconcile_success(item.item_id, Stage.PROBE)
    orchestrator = Orchestrator(store, object(), object(), BlockingApi(), tmp_path / "work")
    errors: list[BaseException] = []

    def run() -> None:
        try:
            orchestrator._run_stage(item.item_id, Stage.MEETING)
        except BaseException as exception:
            errors.append(exception)

    thread = threading.Thread(target=run)
    thread.start()
    assert entered.wait(1)
    with pytest.raises(Exception, match="while processing"):
        store.update_metadata(
            item.item_id,
            title="Wrong client race",
            meeting_at=item.meeting_at,
            client_id=7,
        )
    release.set()
    thread.join(2)
    assert not errors
    persisted = store.get_item(item.item_id)
    assert persisted.client_id == 52
    assert persisted.title == "Planning"
    assert persisted.server_meeting_id == 700


def test_transport_token_never_reaches_persisted_or_gui_diagnostics(store, item, tmp_path) -> None:
    token = "review-token-never-display"

    class LeakingTransport:
        def request(self, *args, **kwargs):
            raise TransportFailure(f"socket failed with Bearer {token}")

    api = WorkerApiClient(
        "https://example.test",
        token,
        LeakingTransport(),
        max_attempts=1,
        sleeper=lambda _: None,
    )
    store.reconcile_success(item.item_id, Stage.PROBE)
    orchestrator = Orchestrator(store, object(), object(), api, tmp_path / "work")
    with pytest.raises(ApiError) as caught:
        orchestrator._run_stage(item.item_id, Stage.MEETING)
    formatted = "".join(
        traceback.format_exception(type(caught.value), caught.value, caught.value.__traceback__)
    )
    row = store.stage(item.item_id, Stage.MEETING)

    class ClientApi:
        def list_clients(self):
            return []

    view = QueueController(store, ClientApi(), timezone="Europe/Bucharest").view(item.item_id)
    copied = diagnostic_text(view)
    for rendered in (
        str(caught.value),
        repr(caught.value),
        formatted,
        str(row["diagnostic"]),
        copied,
    ):
        assert token not in rendered


@pytest.mark.parametrize("artifact", ["video", "audio", "transcript"])
def test_upload_response_integrity_mismatch_fails_stage(store, item, tmp_path, artifact) -> None:
    orchestrator, _, _, api = services(store, item, tmp_path)
    api.response_mismatch = artifact
    with pytest.raises(DataIntegrityError, match="response"):
        orchestrator.process(item.item_id)
    stage = {
        "video": Stage.VIDEO_UPLOAD,
        "audio": Stage.AUDIO_UPLOAD,
        "transcript": Stage.TRANSCRIPT_UPLOAD,
    }[artifact]
    assert store.stage(item.item_id, stage)["status"] == StageStatus.FAILED
    assert store.stage(item.item_id, Stage.FINAL_RECONCILE)["status"] == StageStatus.PENDING


@pytest.mark.parametrize("artifact", ["video", "audio", "transcript"])
def test_generated_file_mutation_is_detected_before_upload(store, item, tmp_path, artifact) -> None:
    orchestrator, _, _, api = services(store, item, tmp_path)
    api.mutate_after_create = artifact
    with pytest.raises(DataIntegrityError, match="changed after generation"):
        orchestrator.process(item.item_id)
    assert artifact not in api.uploads
