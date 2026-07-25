from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REDACTED = "[REDACTED]"


class ConfigError(ValueError):
    pass


def _boolean(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false.")


def _positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exception:
        raise ConfigError(f"{name} must be numeric.") from exception
    if parsed <= 0:
        raise ConfigError(f"{name} must be greater than zero.")
    return parsed


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exception:
        raise ConfigError(f"{name} must be an integer.") from exception
    if parsed <= 0:
        raise ConfigError(f"{name} must be greater than zero.")
    return parsed


@dataclass(frozen=True, repr=False)
class WorkerConfig:
    api_base_url: str
    api_token: str
    ffmpeg_path: Path
    ffprobe_path: Path
    model_dir: Path
    runtime_dir: Path
    work_dir: Path
    state_db: Path
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    upload_timeout: float = 3600.0
    compression_preset: str = "balanced"
    video_codec: str = "h264_amf"
    fallback_video_codec: str = "libx264"
    whisper_model: str = "large-v3"
    language: str = "ro"
    vad_filter: bool = True
    vad_min_silence_ms: int = 500
    timezone: str = "Europe/Bucharest"

    def __repr__(self) -> str:
        values = []
        for field in fields(self):
            value = REDACTED if field.name == "api_token" else getattr(self, field.name)
            values.append(f"{field.name}={value!r}")
        return f"WorkerConfig({', '.join(values)})"

    def safe_dict(self) -> dict[str, object]:
        return {
            field.name: REDACTED if field.name == "api_token" else getattr(self, field.name)
            for field in fields(self)
        }


def load_config(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    require_token: bool = True,
) -> WorkerConfig:
    values = dict(os.environ if environ is None else environ)
    if env_file is not None and env_file.exists():
        try:
            from dotenv import dotenv_values
        except ImportError as exception:  # pragma: no cover - dependency failure
            raise ConfigError("python-dotenv is required to load an environment file.") from exception
        file_values = {key: value for key, value in dotenv_values(env_file).items() if value is not None}
        file_values.update(values)
        values = file_values

    def get(name: str, default: str | None = None) -> str:
        value = values.get(name, default)
        if value is None:
            raise ConfigError(f"{name} is required.")
        return value.strip()

    base_url = get("MINUTORY_API_BASE_URL", "http://localhost:8000").rstrip("/")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigError("MINUTORY_API_BASE_URL must be an absolute HTTP(S) URL.")

    token = get("MINUTORY_API_TOKEN", "")
    if require_token and (not token or token == REDACTED):
        raise ConfigError("MINUTORY_API_TOKEN is required at runtime.")

    preset = get("MINUTORY_COMPRESSION_PRESET", "balanced").lower()
    if preset not in {"none", "compact", "balanced", "quality"}:
        raise ConfigError("MINUTORY_COMPRESSION_PRESET is invalid.")

    timezone = get("MINUTORY_TIMEZONE", "Europe/Bucharest")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exception:
        raise ConfigError("MINUTORY_TIMEZONE must be a valid IANA timezone.") from exception

    return WorkerConfig(
        api_base_url=base_url,
        api_token=token,
        ffmpeg_path=Path(get("MINUTORY_FFMPEG_PATH", "ffmpeg")),
        ffprobe_path=Path(get("MINUTORY_FFPROBE_PATH", "ffprobe")),
        model_dir=Path(get("MINUTORY_MODEL_DIR", "./models")),
        runtime_dir=Path(get("MINUTORY_RUNTIME_DIR", "./libs")),
        work_dir=Path(get("MINUTORY_WORK_DIR", "./work")),
        state_db=Path(get("MINUTORY_STATE_DB", "./state/worker.sqlite3")),
        connect_timeout=_positive_float(get("MINUTORY_CONNECT_TIMEOUT", "10"), "MINUTORY_CONNECT_TIMEOUT"),
        read_timeout=_positive_float(get("MINUTORY_READ_TIMEOUT", "120"), "MINUTORY_READ_TIMEOUT"),
        upload_timeout=_positive_float(get("MINUTORY_UPLOAD_TIMEOUT", "3600"), "MINUTORY_UPLOAD_TIMEOUT"),
        compression_preset=preset,
        video_codec=get("MINUTORY_VIDEO_CODEC", "h264_amf"),
        fallback_video_codec=get("MINUTORY_FALLBACK_VIDEO_CODEC", "libx264"),
        whisper_model=get("MINUTORY_WHISPER_MODEL", "large-v3"),
        language=get("MINUTORY_LANGUAGE", "ro"),
        vad_filter=_boolean(get("MINUTORY_VAD_FILTER", "true"), "MINUTORY_VAD_FILTER"),
        vad_min_silence_ms=_positive_int(
            get("MINUTORY_VAD_MIN_SILENCE_MS", "500"),
            "MINUTORY_VAD_MIN_SILENCE_MS",
        ),
        timezone=timezone,
    )


def redact_text(value: str, token: str) -> str:
    return value.replace(token, REDACTED) if token else value
