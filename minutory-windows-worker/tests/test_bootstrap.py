from __future__ import annotations

import json
import re
import stat
import zipfile
from pathlib import Path

import pytest

from minutory_worker.bootstrap_plan import (
    BOOTSTRAP_SCHEMA,
    READY_MARKER,
    ManifestError,
    installed_tree_digest,
    load_asset_plan,
    readiness_fingerprint,
    ready_marker_matches,
    validate_wheelhouse,
    validate_zip_layout,
    verify_expected_files,
)

ROOT = Path(__file__).parents[1]


def test_tracked_manifest_is_explicitly_unresolved_and_fails_closed() -> None:
    path = ROOT / "manifests/runtime-assets.json"
    document = json.loads(path.read_text())
    assert document["schema_version"] == 2
    assert {asset["id"] for asset in document["assets"]} == {
        "python-runtime",
        "ffmpeg",
        "ctranslate2-rocm-wheel",
        "runtime-wheelhouse",
        "faster-whisper-large-v3",
    }
    assert all(asset["status"] == "unresolved" for asset in document["assets"])
    assert all(asset["sha256"] is None for asset in document["assets"])
    assert all(asset["installed_tree_sha256"] is None for asset in document["assets"])
    assert all(asset["expected_files"] for asset in document["assets"])
    rocm = next(asset for asset in document["assets"] if asset["id"] == "ctranslate2-rocm-wheel")
    assert rocm["archive"] == "zip"
    assert rocm["source_subdir"] == "temp-windows"
    assert rocm["destination"] == "libs/wheels/ctranslate2-rocm-4.8.1"
    assert rocm["expected_files"] == ["ctranslate2-4.8.1-cp312-cp312-win_amd64.whl"]
    assert "rocm-python-wheels-Windows.zip" in rocm["notes"]
    assert "3a4936a4e76f27b9c0e4f32b06baf6378fe778d784adcb53cd3e159bd4d218b3" in rocm["notes"]
    with pytest.raises(ManifestError, match="closed"):
        load_asset_plan(path)


def test_resolved_manifest_schema_hash_https_and_destinations(tmp_path: Path) -> None:
    original = json.loads((ROOT / "manifests/runtime-assets.json").read_text())
    for index, asset in enumerate(original["assets"]):
        asset["status"] = "resolved"
        asset["url"] = f"https://downloads.example.test/{asset['id']}-{asset['version']}.zip"
        asset["sha256"] = f"{index + 1:064x}"
        asset["installed_tree_sha256"] = f"{index + 11:064x}" if asset["archive"] == "zip" else None
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(original))
    plans = load_asset_plan(path)
    assert len(plans) == 5
    assert all(re.fullmatch(r"[0-9a-f]{64}", plan.sha256) for plan in plans)

    original["assets"][0]["destination"] = "../escape"
    path.write_text(json.dumps(original))
    with pytest.raises(ManifestError, match="exactly"):
        load_asset_plan(path)


def test_exact_archive_contract_and_python_distribution_are_enforced(tmp_path: Path) -> None:
    document = json.loads((ROOT / "manifests/runtime-assets.json").read_text())
    for index, asset in enumerate(document["assets"]):
        asset["status"] = "resolved"
        asset["url"] = f"https://example.test/{asset['id']}.bin"
        asset["sha256"] = f"{index + 1:064x}"
        asset["installed_tree_sha256"] = f"{index + 11:064x}" if asset["archive"] == "zip" else None
    path = tmp_path / "manifest.json"
    document["assets"][1]["archive"] = "file"
    path.write_text(json.dumps(document))
    with pytest.raises(ManifestError, match="archive must be zip"):
        load_asset_plan(path)
    document["assets"][1]["archive"] = "zip"
    document["assets"][0]["distribution_contract"] = "embeddable"
    path.write_text(json.dumps(document))
    with pytest.raises(ManifestError, match="embeddable ZIP"):
        load_asset_plan(path)


def _zip(path: Path, members: list[tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w") as bundle:
        for name, payload in members:
            bundle.writestr(name, payload)


def test_zip_layout_rejects_traversal_absolute_and_collisions(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    _zip(archive, [("python/python.exe", b"ok"), ("python/../escape.exe", b"bad")])
    with pytest.raises(ManifestError, match="safe POSIX"):
        validate_zip_layout(archive, "python")

    _zip(archive, [("/python/python.exe", b"bad")])
    with pytest.raises(ManifestError, match="safe POSIX"):
        validate_zip_layout(archive, "python")

    _zip(archive, [("python/Bin/tool.exe", b"one"), ("python/bin/TOOL.exe", b"two")])
    with pytest.raises(ManifestError, match="colliding"):
        validate_zip_layout(archive, "python")

    _zip(archive, [("python/bin", b"file"), ("python/bin/tool.exe", b"child")])
    with pytest.raises(ManifestError, match="collision"):
        validate_zip_layout(archive, "python")

    with zipfile.ZipFile(archive, "w") as bundle:
        link = zipfile.ZipInfo("python/python.exe")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "target.exe")
    with pytest.raises(ManifestError, match="symlink"):
        validate_zip_layout(archive, "python")


def test_expected_files_tree_digest_and_ready_marker_detect_changes(tmp_path: Path) -> None:
    installed = tmp_path / "asset"
    installed.mkdir()
    (installed / "python.exe").write_bytes(b"python")
    assert verify_expected_files(installed, ("python.exe", "pythonw.exe")) == ("pythonw.exe",)
    first = installed_tree_digest(installed)
    (installed / "python.exe").write_bytes(b"modified")
    assert installed_tree_digest(installed) != first
    (installed / ".minutory-asset.json").write_text("mutable marker")
    unchanged = installed_tree_digest(installed)
    (installed / ".minutory-asset.json").write_text("different marker")
    assert installed_tree_digest(installed) == unchanged

    manifest = tmp_path / "manifest.json"
    requirements = tmp_path / "requirements.txt"
    manifest.write_text("{}")
    requirements.write_text("dependency==1")
    fingerprint = readiness_fingerprint(manifest, requirements)
    marker = tmp_path / READY_MARKER
    marker.write_text(json.dumps({"schema": BOOTSTRAP_SCHEMA, "fingerprint": fingerprint}))
    assert ready_marker_matches(marker, fingerprint)
    requirements.write_text("dependency==2")
    assert not ready_marker_matches(marker, readiness_fingerprint(manifest, requirements))
    marker.write_text("{partial")
    assert not ready_marker_matches(marker, fingerprint)


def test_wheelhouse_requires_pinned_wheels_and_forbids_ctranslate2(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("httpx==0.28.1\nPySide6==6.9.1\n")
    (wheelhouse / "httpx-0.28.1-py3-none-any.whl").touch()
    with pytest.raises(ManifestError, match="PySide6"):
        validate_wheelhouse(wheelhouse, requirements)
    (wheelhouse / "PySide6-6.9.1-cp39-abi3-win_amd64.whl").touch()
    validate_wheelhouse(wheelhouse, requirements)
    (wheelhouse / "ctranslate2-4.8.1-cp312-win_amd64.whl").touch()
    with pytest.raises(ManifestError, match="official ROCm"):
        validate_wheelhouse(wheelhouse, requirements)


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
    bootstrap = (ROOT / "bootstrap.ps1").read_text()
    assert "Expand-Archive" not in bootstrap
    assert ".venv.installing-" in bootstrap
    assert "installed_tree_sha256" in bootstrap
    assert "Get-AssetFileSnapshot" in bootstrap
    assert "Test-AssetFileSnapshot" in bootstrap
    assert "last_write_utc_ticks" in bootstrap
    assert "Write-AssetMarker" in bootstrap
    assert "Assert-NoReparsePoints" in bootstrap
    assert '$marker.PSObject.Properties["schema"]' in bootstrap
    assert "[IO.Path]::GetFullPath((Join-Path $Directory $AssetMarker))" in bootstrap
    assert "PYTHONDONTWRITEBYTECODE" in bootstrap
    assert "[[string]" not in bootstrap
    assert "$RequiredExpectedFiles = @{" in bootstrap
    assert "foreach ($requiredFile in $RequiredExpectedFiles[$assetId])" in bootstrap
    assert "$RequiredExpected = @{" not in bootstrap
    launcher = (ROOT / "start.ps1").read_text()
    assert 'bootstrap.ps1") -Verify' in launcher
    assert '$env:HF_HUB_OFFLINE = "1"' in launcher
    assert '$env:TRANSFORMERS_OFFLINE = "1"' in launcher


def test_runtime_requirements_pin_gui_and_do_not_name_ctranslate2() -> None:
    requirements = (ROOT / "requirements-runtime.txt").read_text()
    assert "PySide6==6.9.1" in requirements
    assert "faster-whisper==1.2.0" in requirements
    assert "ctranslate2" not in requirements.lower()
