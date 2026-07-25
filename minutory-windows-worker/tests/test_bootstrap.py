from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from minutory_worker.bootstrap_plan import ManifestError, load_asset_plan

ROOT = Path(__file__).parents[1]


def test_tracked_manifest_is_explicitly_unresolved_and_fails_closed() -> None:
    path = ROOT / "manifests/runtime-assets.json"
    document = json.loads(path.read_text())
    assert document["schema_version"] == 1
    assert {asset["id"] for asset in document["assets"]} == {
        "python-runtime",
        "ffmpeg",
        "ctranslate2-rocm-wheel",
        "runtime-wheelhouse",
        "faster-whisper-large-v3",
    }
    assert all(asset["status"] == "unresolved" for asset in document["assets"])
    assert all(asset["sha256"] is None for asset in document["assets"])
    with pytest.raises(ManifestError, match="closed"):
        load_asset_plan(path)


def test_resolved_manifest_schema_hash_https_and_destinations(tmp_path: Path) -> None:
    original = json.loads((ROOT / "manifests/runtime-assets.json").read_text())
    for index, asset in enumerate(original["assets"]):
        asset["status"] = "resolved"
        asset["url"] = f"https://downloads.example.test/{asset['id']}-{asset['version']}.zip"
        asset["sha256"] = f"{index + 1:064x}"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(original))
    plans = load_asset_plan(path)
    assert len(plans) == 5
    assert all(re.fullmatch(r"[0-9a-f]{64}", plan.sha256) for plan in plans)

    original["assets"][0]["destination"] = "../escape"
    path.write_text(json.dumps(original))
    with pytest.raises(ManifestError, match="escapes"):
        load_asset_plan(path)


def test_bootstrap_and_launchers_are_credential_free_and_local_transcription_only() -> None:
    tracked = [
        ROOT / "bootstrap.ps1",
        ROOT / "start.ps1",
        ROOT / "start.bat",
        ROOT / ".env.example",
    ]
    combined = "\n".join(path.read_text() for path in tracked)
    assert "test-worker-token" not in combined
    assert "Bearer " not in combined
    assert "start_transcript_server=true" not in combined.lower()
    api_source = (ROOT / "src/minutory_worker/api.py").read_text()
    assert '"start_transcript_server": False' in api_source
    assert "Invoke-WebRequest" in (ROOT / "bootstrap.ps1").read_text()
    assert "Get-FileHash" in (ROOT / "bootstrap.ps1").read_text()


def test_runtime_requirements_pin_gui_and_do_not_name_ctranslate2() -> None:
    requirements = (ROOT / "requirements-runtime.txt").read_text()
    assert "PySide6==6.9.1" in requirements
    assert "faster-whisper==1.2.0" in requirements
    assert "ctranslate2" not in requirements.lower()
