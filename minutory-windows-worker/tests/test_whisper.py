from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from minutory_worker.config import WorkerConfig
from minutory_worker.runtime import build_orchestrator
from minutory_worker.whisper import (
    BackendResult,
    BackendSegment,
    FasterWhisperBackend,
    TranscriptError,
    WhisperService,
    normalize_transcript,
)


class FakeBackend:
    model_name = "large-v3"

    def __init__(self, result: BackendResult):
        self.result = result
        self.calls = 0

    def transcribe(
        self, audio_path: Path, *, language: str, vad_filter: bool, vad_parameters
    ) -> BackendResult:
        self.calls += 1
        assert language == "ro"
        assert vad_filter
        assert vad_parameters == {"min_silence_duration_ms": 500}
        return self.result


def valid_result() -> BackendResult:
    return BackendResult(
        segments=[
            BackendSegment(0, 1.5, " Bună ", " Speaker 1 "),
            BackendSegment(1.5, 2, "ziua", None),
        ],
        language="ro",
        language_probability=0.99,
        duration=2,
        runtime={"device": "cuda", "compute_type": "float16"},
    )


def test_normalized_exact_contract_and_atomic_write(tmp_path: Path) -> None:
    backend = FakeBackend(valid_result())
    destination = tmp_path / "transcript.json"
    document = WhisperService(backend).transcribe(tmp_path / "audio.wav", destination)
    assert list(document) == [
        "driver",
        "model",
        "language",
        "language_probability",
        "duration",
        "runtime",
        "segments",
    ]
    assert document["driver"] == "faster-whisper-windows"
    assert document["segments"][0] == {
        "start": 0.0,
        "end": 1.5,
        "text": "Bună",
        "speaker": "Speaker 1",
    }
    assert json.loads(destination.read_text()) == document


@pytest.mark.parametrize(
    "result",
    [
        BackendResult([BackendSegment(-1, 1, "x")], "ro", 1, 1, {}),
        BackendResult([BackendSegment(2, 1, "x")], "ro", 1, 2, {}),
        BackendResult([BackendSegment(1, 2, "x"), BackendSegment(0, 1, "y")], "ro", 1, 2, {}),
        BackendResult([BackendSegment(0, 1, " ")], "ro", 1, 1, {}),
        BackendResult([], "ro", 2, 1, {}),
        BackendResult([], "ro", 1, math.inf, {}),
    ],
)
def test_transcript_validation(result: BackendResult) -> None:
    with pytest.raises(TranscriptError):
        normalize_transcript(result, model="large-v3")


def test_invalid_transcript_preserves_known_good_file(tmp_path: Path) -> None:
    destination = tmp_path / "transcript.json"
    destination.write_text('{"known":"good"}')
    backend = FakeBackend(BackendResult([BackendSegment(-1, 1, "bad")], "ro", 1, 1, {}))
    with pytest.raises(TranscriptError):
        WhisperService(backend).transcribe(tmp_path / "audio.wav", destination)
    assert destination.read_text() == '{"known":"good"}'
    assert list(tmp_path.glob(".transcript.json.*.tmp")) == []


def test_faster_whisper_defaults_and_does_not_import_at_construction(tmp_path: Path) -> None:
    backend = FasterWhisperBackend(tmp_path / "large-v3")
    assert backend.model_name == "large-v3"
    assert backend.device == "cuda"
    assert backend.compute_type == "float16"
    assert backend.beam_size == 5
    assert backend.batch_size == 0
    assert backend.model_path == tmp_path / "large-v3"
    assert backend._model is None


def test_faster_whisper_loads_only_the_explicit_local_model(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def model(path, **kwargs):
        captured["path"] = path
        captured.update(kwargs)
        return object()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=model))
    local = tmp_path / "models" / "large-v3"
    backend = FasterWhisperBackend(local)
    backend._get_model()
    assert captured == {
        "path": str(local),
        "device": "cuda",
        "compute_type": "float16",
    }


def test_faster_whisper_wraps_batched_pipeline_when_enabled(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def model(path, **kwargs):
        return object()

    def batched(inner, *, batch_size):
        captured["inner"] = inner
        captured["batch_size"] = batch_size
        return object()

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=model, BatchedInferencePipeline=batched),
    )
    backend = FasterWhisperBackend(tmp_path / "large-v3", batch_size=8)
    backend._get_model()
    assert captured["batch_size"] == 8
    assert captured["inner"] is not None


def test_production_runtime_refuses_missing_local_model_before_opening_state(tmp_path: Path) -> None:
    config = WorkerConfig(
        api_base_url="https://example.test",
        api_token="fake-token",
        ffmpeg_path=tmp_path / "ffmpeg.exe",
        ffprobe_path=tmp_path / "ffprobe.exe",
        model_dir=tmp_path / "models",
        runtime_dir=tmp_path / "libs",
        work_dir=tmp_path / "work",
        state_db=tmp_path / "state.sqlite3",
    )
    with pytest.raises(RuntimeError, match="network model downloads are disabled"):
        build_orchestrator(config)
    assert not config.state_db.exists()
