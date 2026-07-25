from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ASSET_IDS = {
    "python-runtime",
    "ffmpeg",
    "ctranslate2-rocm-wheel",
    "runtime-wheelhouse",
    "faster-whisper-large-v3",
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


def load_asset_plan(path: Path) -> tuple[AssetPlan, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exception:
        raise ManifestError(f"Cannot read runtime asset manifest: {exception}") from exception
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ManifestError("Runtime asset manifest schema_version must be 1.")
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
        if not isinstance(asset_id, str) or SAFE_VALUE.fullmatch(asset_id) is None or asset_id in seen:
            raise ManifestError(f"Asset {index} has a missing or duplicate ID.")
        seen.add(asset_id)
        status = raw.get("status")
        url = raw.get("url")
        digest = raw.get("sha256")
        if status == "unresolved" or url is None or digest is None:
            unresolved.append(asset_id)
            continue
        if status != "resolved":
            raise ManifestError(f"Asset {asset_id} has an invalid status.")
        if not isinstance(url, str) or urlparse(url).scheme != "https":
            raise ManifestError(f"Asset {asset_id} must use an HTTPS URL.")
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise ManifestError(f"Asset {asset_id} must have a lowercase SHA-256.")
        destination = raw.get("destination")
        if not isinstance(destination, str):
            raise ManifestError(f"Asset {asset_id} has no destination.")
        target = PurePosixPath(destination)
        if (
            target.is_absolute()
            or ".." in target.parts
            or target.parts[0]
            not in {
                "libs",
                "models",
                "cache",
            }
        ):
            raise ManifestError(f"Asset {asset_id} destination escapes managed directories.")
        archive = raw.get("archive")
        if archive not in {"zip", "file"}:
            raise ManifestError(f"Asset {asset_id} archive must be zip or file.")
        version = raw.get("version")
        if not isinstance(version, str) or SAFE_VALUE.fullmatch(version) is None:
            raise ManifestError(f"Asset {asset_id} has no version.")
        plans.append(AssetPlan(asset_id, version, url, digest, destination, archive))
    missing = ASSET_IDS - seen
    if missing:
        raise ManifestError(f"Runtime asset manifest is missing: {', '.join(sorted(missing))}.")
    if unresolved:
        raise ManifestError(
            "Runtime assets are unresolved and bootstrap is closed: "
            f"{', '.join(unresolved)}. Verify upstream URLs and hashes, then use a local override manifest."
        )
    return tuple(plans)
