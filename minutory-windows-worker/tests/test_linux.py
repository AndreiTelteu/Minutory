from __future__ import annotations

import sys
from pathlib import Path

import pytest

from minutory_worker.config import ConfigError, load_config
from minutory_worker.diarization import SpeakerDiarizationService


def test_platform_defaults_and_explicit_gpu_configuration(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    config = load_config(environ={})
    assert (config.video_codec, config.asr_device, config.asr_compute_type) == ("libx264", "cpu", "int8")
    gpu = load_config(environ={"MINUTORY_ASR_DEVICE": "cuda"})
    assert gpu.asr_compute_type == "float16"
    monkeypatch.setattr(sys, "platform", "win32")
    windows = load_config(environ={})
    assert (windows.video_codec, windows.asr_device, windows.asr_compute_type) == (
        "h264_amf",
        "cuda",
        "float16",
    )


@pytest.mark.parametrize("env", [{"MINUTORY_ASR_DEVICE": "hip"}, {"MINUTORY_ASR_COMPUTE_TYPE": "bad"}])
def test_invalid_asr_configuration(env):
    with pytest.raises(ConfigError):
        load_config(environ=env)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux CPU provider test")
def test_linux_cpu_diarization_loads_local_models_without_directml(tmp_path: Path, monkeypatch):
    import onnxruntime as ort

    import minutory_worker.diarization as module

    monkeypatch.setattr(module.os, "name", "posix")
    for name in ("segmentation.onnx", "embedding.onnx"):
        (tmp_path / name).touch()
    calls = []
    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CPUExecutionProvider"])
    monkeypatch.setattr(ort, "InferenceSession", lambda path, providers: calls.append(providers) or object())
    service = SpeakerDiarizationService(tmp_path, device_id=2)
    service._get_sessions()
    assert calls == [["CPUExecutionProvider"], ["CPUExecutionProvider"]]
    assert service._selection.provider == "CPUExecutionProvider"
    assert not service._selection.fallback


@pytest.mark.skipif(sys.platform != "linux", reason="Linux runtime verification")
def test_runtime_rejects_unsupported_compute_and_missing_models(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from minutory_worker import runtime_verify

    ctranslate2 = SimpleNamespace(
        __version__="4.8.2", get_supported_compute_types=lambda device: {"int8", "float32"}
    )
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace())

    monkeypatch.setenv("MINUTORY_ENV_FILE", str(tmp_path / "absent.env"))
    monkeypatch.setenv("MINUTORY_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("MINUTORY_ASR_DEVICE", "cpu")
    monkeypatch.setenv("MINUTORY_ASR_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(ctranslate2, "get_supported_compute_types", lambda device: {"int8", "float32"})
    checks = runtime_verify.verify_runtime(Path("ffmpeg"), Path("ffprobe"))
    indexed = {check.name: check for check in checks}
    assert not indexed["CTranslate2"].ok
    assert not indexed["Speaker models"].ok
    assert not indexed["Whisper model"].ok
    assert all("Windows" not in check.name for check in checks)
