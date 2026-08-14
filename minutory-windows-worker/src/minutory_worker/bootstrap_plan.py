from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

SCHEMA_VERSION = 2
BOOTSTRAP_SCHEMA = "minutory-bootstrap-v2"
ASSET_MARKER = ".minutory-asset.json"
READY_MARKER = ".minutory-ready.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

ASSET_CONTRACTS: dict[str, tuple[str, str]] = {
    "python-runtime": ("libs/python", "zip"),
    "ffmpeg": ("libs/ffmpeg", "zip"),
    "ctranslate2-rocm-wheel": (
        "libs/wheels/ctranslate2-rocm-4.8.1",
        "zip",
    ),
    "runtime-wheelhouse": ("libs/wheelhouse", "zip"),
    "faster-whisper-large-v3": ("models/large-v3", "zip"),
    "pyannote-speaker-diarization-community-1": (
        "models/pyannote-speaker-diarization-community-1",
        "zip",
    ),
}
REQUIRED_EXPECTED_FILES: dict[str, frozenset[str]] = {
    "python-runtime": frozenset(
        {"python.exe", "pythonw.exe", "Lib/venv/__init__.py", "Lib/ensurepip/__init__.py"}
    ),
    "ffmpeg": frozenset(
        {
            "bin/ffmpeg.exe",
            "bin/ffprobe.exe",
            "bin/avcodec-61.dll",
            "bin/avformat-61.dll",
            "bin/avutil-59.dll",
            "bin/avfilter-10.dll",
            "bin/swscale-8.dll",
            "bin/swresample-5.dll",
        }
    ),
    "ctranslate2-rocm-wheel": frozenset({"ctranslate2-4.8.1-cp312-cp312-win_amd64.whl"}),
    "runtime-wheelhouse": frozenset(
        {
            "requirements-runtime.txt",
            "httpx-0.28.1-py3-none-any.whl",
            "python_dotenv-1.1.1-py3-none-any.whl",
            "tzdata-2025.2-py2.py3-none-any.whl",
            "PySide6-6.9.1-cp39-abi3-win_amd64.whl",
            "faster_whisper-1.2.0-py3-none-any.whl",
            "pyannote_audio-4.0.7-py3-none-any.whl",
        }
    ),
    "faster-whisper-large-v3": frozenset(
        {
            "model.bin",
            "config.json",
            "tokenizer.json",
            "vocabulary.json",
            "preprocessor_config.json",
        }
    ),
    "pyannote-speaker-diarization-community-1": frozenset({"config.yaml"}),
}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class AssetPlan:
    asset_id: str
    version: str
    url: str
    sha256: str
    destination: str
    archive: str
    source_subdir: str | None
    expected_files: tuple[str, ...]
    distribution_contract: str | None = None
    installed_tree_sha256: str | None = None


def load_asset_plan(path: Path) -> tuple[AssetPlan, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exception:
        raise ManifestError(f"Cannot read runtime asset manifest: {exception}") from exception
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"Runtime asset manifest schema_version must be {SCHEMA_VERSION}.")
    raw_assets = document.get("assets")
    if not isinstance(raw_assets, list):
        raise ManifestError("Runtime asset manifest assets must be an array.")
    plans: list[AssetPlan] = []
    seen: set[str] = set()
    unresolved: list[str] = []
    for index, raw in enumerate(raw_assets):
        if not isinstance(raw, dict):
            raise ManifestError(f"Asset {index} must be an object.")
        asset_id = raw.get("id")
        if not isinstance(asset_id, str) or asset_id not in ASSET_CONTRACTS or asset_id in seen:
            raise ManifestError(f"Asset {index} has an unknown or duplicate ID.")
        seen.add(asset_id)
        expected_destination, expected_archive = ASSET_CONTRACTS[asset_id]
        destination = raw.get("destination")
        archive = raw.get("archive")
        if destination != expected_destination:
            raise ManifestError(f"Asset {asset_id} destination must be exactly {expected_destination}.")
        if archive != expected_archive:
            raise ManifestError(f"Asset {asset_id} archive must be {expected_archive}.")
        source_subdir = raw.get("source_subdir")
        if archive == "zip":
            if not isinstance(source_subdir, str):
                raise ManifestError(f"Asset {asset_id} requires source_subdir.")
            _safe_relative(source_subdir, f"Asset {asset_id} source_subdir", allow_dot=True)
        elif source_subdir is not None:
            raise ManifestError(f"File asset {asset_id} source_subdir must be null.")
        expected_files = raw.get("expected_files")
        if not isinstance(expected_files, list) or not expected_files:
            raise ManifestError(f"Asset {asset_id} expected_files must be a non-empty array.")
        normalized_expected: list[str] = []
        for value in expected_files:
            if not isinstance(value, str):
                raise ManifestError(f"Asset {asset_id} has an invalid expected file.")
            normalized_expected.append(str(_safe_relative(value, f"Asset {asset_id} expected file")))
        if len({value.casefold() for value in normalized_expected}) != len(normalized_expected):
            raise ManifestError(f"Asset {asset_id} has duplicate expected files.")
        missing_expected = REQUIRED_EXPECTED_FILES[asset_id] - set(normalized_expected)
        if missing_expected:
            raise ManifestError(
                f"Asset {asset_id} omits required expected files: {', '.join(sorted(missing_expected))}."
            )
        version = raw.get("version")
        if not isinstance(version, str) or SAFE_VALUE.fullmatch(version) is None:
            raise ManifestError(f"Asset {asset_id} has no safe version.")
        contract = raw.get("distribution_contract")
        if asset_id == "python-runtime" and contract != "full-portable-venv":
            raise ManifestError(
                "Python runtime must declare distribution_contract full-portable-venv; "
                "the official embeddable ZIP is unsupported."
            )
        if contract is not None and not isinstance(contract, str):
            raise ManifestError(f"Asset {asset_id} has an invalid distribution contract.")
        status = raw.get("status")
        url = raw.get("url")
        digest = raw.get("sha256")
        tree_digest = raw.get("installed_tree_sha256")
        if status == "unresolved":
            if url is not None or digest is not None or tree_digest is not None:
                raise ManifestError(f"Unresolved asset {asset_id} must use null URL and hashes.")
            unresolved.append(asset_id)
            continue
        if status != "resolved":
            raise ManifestError(f"Asset {asset_id} has an invalid status.")
        parsed_url = urlparse(url) if isinstance(url, str) else None
        if (
            parsed_url is None
            or parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ManifestError(f"Asset {asset_id} must use an HTTPS URL.")
        assert isinstance(url, str)
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise ManifestError(f"Asset {asset_id} must have a lowercase SHA-256.")
        if archive == "zip":
            if not isinstance(tree_digest, str) or SHA256.fullmatch(tree_digest) is None:
                raise ManifestError(f"Asset {asset_id} must have a lowercase installed-tree SHA-256.")
        elif tree_digest is not None:
            raise ManifestError(f"File asset {asset_id} installed-tree SHA-256 must be null.")
        plans.append(
            AssetPlan(
                asset_id,
                version,
                url,
                digest,
                destination,
                archive,
                source_subdir,
                tuple(normalized_expected),
                contract,
                tree_digest,
            )
        )
    missing = set(ASSET_CONTRACTS) - seen
    if missing:
        raise ManifestError(f"Runtime asset manifest is missing: {', '.join(sorted(missing))}.")
    if unresolved:
        raise ManifestError(
            "Runtime assets are unresolved and bootstrap is closed: "
            f"{', '.join(unresolved)}. Verify upstream URLs and hashes, then use a local override manifest."
        )
    return tuple(plans)


def validate_zip_layout(archive: Path, source_subdir: str) -> tuple[str, ...]:
    """Return normalized install targets after rejecting unsafe/colliding ZIP entries."""
    root = PurePosixPath(source_subdir)
    targets: dict[str, bool] = {}
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            raw = info.filename.replace("\\", "/")
            member = _safe_relative(raw, "ZIP member", allow_dot=False)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ManifestError(f"ZIP member {raw!r} is a symlink/reparse-style entry.")
            try:
                relative = member.relative_to(root) if str(root) != "." else member
            except ValueError:
                continue
            if str(relative) == ".":
                continue
            target = str(relative)
            key = target.casefold()
            is_directory = info.is_dir() or raw.endswith("/")
            if key in targets:
                raise ManifestError(f"ZIP contains duplicate/colliding target {target!r}.")
            parts = PurePosixPath(target).parts
            for length in range(1, len(parts)):
                parent = "/".join(parts[:length]).casefold()
                if parent in targets and not targets[parent]:
                    raise ManifestError(f"ZIP file/directory collision at {target!r}.")
            if not is_directory and any(existing.startswith(f"{key}/") for existing in targets):
                raise ManifestError(f"ZIP file/directory collision at {target!r}.")
            targets[key] = is_directory
    files = tuple(sorted(key for key, is_directory in targets.items() if not is_directory))
    if not files:
        raise ManifestError("ZIP source_subdir contains no files.")
    return files


def verify_expected_files(root: Path, expected_files: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in expected_files if not (root / Path(name)).is_file())


def validate_wheelhouse(root: Path, requirements: Path) -> None:
    wheels = {path.name.casefold() for path in root.glob("*.whl")}
    if any(name.startswith("ctranslate2") for name in wheels):
        raise ManifestError("Wheelhouse must exclude CTranslate2; install only the official ROCm wheel.")
    missing: list[str] = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ManifestError(f"Runtime requirement must be exactly pinned: {line}.")
        name, version = line.split("==", 1)
        canonical = re.sub(r"[-_.]+", "-", name).casefold()
        prefixes = {
            f"{canonical}-{version.casefold()}-",
            f"{canonical.replace('-', '_')}-{version.casefold()}-",
        }
        if not any(any(wheel.startswith(prefix) for prefix in prefixes) for wheel in wheels):
            missing.append(line)
    if missing:
        raise ManifestError(f"Wheelhouse is missing pinned wheels: {', '.join(missing)}.")


def installed_tree_digest(root: Path) -> str:
    """Hash sorted path/size/file-hash records, excluding our marker."""
    if not root.is_dir():
        raise ManifestError(f"Installed asset directory is missing: {root}.")
    files = sorted(
        (
            path.relative_to(root).as_posix(),
            path,
        )
        for path in root.rglob("*")
        if path.is_file() and path.name != ASSET_MARKER
    )
    records = [f"{relative}|{path.stat().st_size}|{_file_sha256(path)}" for relative, path in files]
    return hashlib.sha256("\n".join(records).encode()).hexdigest()


def readiness_fingerprint(manifest: Path, requirements: Path) -> str:
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    requirements_hash = hashlib.sha256(requirements.read_bytes()).hexdigest()
    payload = f"{BOOTSTRAP_SCHEMA}|{manifest_hash}|{requirements_hash}"
    return hashlib.sha256(payload.encode()).hexdigest()


def ready_marker_matches(marker: Path, fingerprint: str) -> bool:
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(document, dict)
        and document.get("schema") == BOOTSTRAP_SCHEMA
        and document.get("fingerprint") == fingerprint
    )


def _safe_relative(value: str, label: str, *, allow_dot: bool = False) -> PurePosixPath:
    if not value or "\0" in value or "\\" in value:
        raise ManifestError(f"{label} must use a safe POSIX relative path.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or (str(path) == "." and not allow_dot):
        raise ManifestError(f"{label} must use a safe POSIX relative path.")
    if path.parts and ":" in path.parts[0]:
        raise ManifestError(f"{label} cannot be an absolute Windows path.")
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
