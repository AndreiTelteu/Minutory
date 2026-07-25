from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import pcm_wave

from minutory_worker.api import ApiError, ArtifactState, MeetingState
from minutory_worker.domain import Stage, StageStatus, stream_sha256
from minutory_worker.media import CommandResult, MediaService
from minutory_worker.orchestrator import ArtifactConflict, Orchestrator
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
                        "format": {"duration": "10"},
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
        return BackendResult([BackendSegment(0, 1, "Salut")], "ro", 0.99, 1, {"device": "fake"})


class FakeApi:
    def __init__(self, item):
        self.item = item
        self.meeting_id = 500
        self.created = 0
        self.reconciled = 0
        self.uploads: list[str] = []
        self.remote: dict[str, str | None] = {"video": None, "audio": None, "transcript": None}
        self.fail_audio_once = False

    def create_meeting(self, item):
        self.created += 1
        assert item.item_id == self.item.item_id
        self.item = item
        return {"id": self.meeting_id, "start_transcript_server": False}

    def upload_artifact(self, meeting_id, artifact, path, *, replace=False):
        assert meeting_id == self.meeting_id
        assert not replace
        self.uploads.append(artifact)
        if artifact == "audio" and self.fail_audio_once:
            self.fail_audio_once = False
            raise ApiError("server_error", "temporary", 503, transient=True)
        self.remote[artifact] = stream_sha256(path)
        return {"state": "uploaded", "sha256": self.remote[artifact], "bytes": path.stat().st_size}

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
                name: ArtifactState(digest is not None, digest, None) for name, digest in self.remote.items()
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
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (1, 1, 1, 1)
    assert api.created == 1
    assert api.uploads == ["video", "audio", "transcript"]
    orchestrator.process(item.item_id)
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (1, 1, 1, 1)
    assert api.created == 1
    assert api.uploads == ["video", "audio", "transcript"]
    assert api.reconciled == 1
    assert all(store.stage(item.item_id, stage)["status"] == StageStatus.SUCCEEDED for stage in Stage)


def test_failed_upload_resume_preserves_expensive_successes(store, item, tmp_path) -> None:
    orchestrator, runner, backend, api = services(store, item, tmp_path)
    api.fail_audio_once = True
    with pytest.raises(ApiError):
        orchestrator.process(item.item_id)
    assert store.stage(item.item_id, Stage.VIDEO_UPLOAD)["status"] == StageStatus.SUCCEEDED
    assert store.stage(item.item_id, Stage.AUDIO_UPLOAD)["status"] == StageStatus.FAILED
    assert store.stage(item.item_id, Stage.TRANSCRIPT_UPLOAD)["status"] == StageStatus.PENDING
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (1, 1, 1, 1)
    orchestrator.process(item.item_id)
    assert (runner.probes, runner.compresses, runner.wavs, backend.calls) == (1, 1, 1, 1)
    assert api.uploads == ["video", "audio", "audio", "transcript"]
    assert store.stage(item.item_id, Stage.AUDIO_UPLOAD)["attempts"] == 2


def test_reconcile_surfaces_remote_hash_conflict_without_replacement(store, item, tmp_path) -> None:
    orchestrator, _, _, api = services(store, item, tmp_path)
    completed = orchestrator.process(item.item_id)
    api.remote["video"] = "f" * 64
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
