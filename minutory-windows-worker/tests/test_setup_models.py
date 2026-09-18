from __future__ import annotations

from pathlib import Path

import pytest

from minutory_worker.setup_models import WHISPER_FILES, complete, prepare_whisper, promote


def test_promotion_restores_existing_bundle_on_failure(tmp_path, monkeypatch):
    existing = tmp_path / "model"
    existing.mkdir()
    (existing / "weights").write_text("known good")
    staging = tmp_path / "staging"
    staging.mkdir()
    original = Path.rename

    def rename(path, target):
        if path == staging:
            raise OSError("cannot install")
        return original(path, target)

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(OSError):
        promote(staging, existing)
    assert (existing / "weights").read_text() == "known good"


def test_incomplete_download_preserves_existing_model(tmp_path, monkeypatch):
    import huggingface_hub

    existing = tmp_path / "large-v3"
    existing.mkdir()
    (existing / "model.bin").write_bytes(b"known good")

    def download(*args, local_dir, **kwargs):
        local_dir.mkdir()
        (local_dir / "model.bin").write_bytes(b"partial")

    monkeypatch.setattr(huggingface_hub, "snapshot_download", download)
    with pytest.raises(RuntimeError, match="incomplete"):
        prepare_whisper(tmp_path)
    assert (existing / "model.bin").read_bytes() == b"known good"


def test_complete_model_skips_network(tmp_path, monkeypatch):
    import huggingface_hub

    destination = tmp_path / "large-v3"
    destination.mkdir()
    for name in WHISPER_FILES:
        (destination / name).write_bytes(b"data")

    def unexpected(*args, **kwargs):
        pytest.fail("Already installed model should not use network")

    monkeypatch.setattr(huggingface_hub, "snapshot_download", unexpected)
    prepare_whisper(tmp_path)
    assert complete(destination, WHISPER_FILES)


def test_export_token_is_not_in_process_arguments_or_log(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from minutory_worker import setup_models

    token = "fake-test-token"
    repo = tmp_path / "cache" / "build" / "pyannote-export"
    (repo / ".git").mkdir(parents=True)
    python = tmp_path / "cache" / "export-venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=1, stdout=f"export failed: {token}")

    monkeypatch.setattr(setup_models.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="Speaker export failed"):
        setup_models.prepare_speakers(tmp_path, model_dir, token)
    assert all(token not in str(args) for args, _ in calls)
    assert calls[-1][1]["env"]["MINUTORY_DIARIZATION_TOKEN"] == token
    assert token not in (tmp_path / "logs" / "speaker-export.log").read_text()
    assert "[REDACTED]" in (tmp_path / "logs" / "speaker-export.log").read_text()
