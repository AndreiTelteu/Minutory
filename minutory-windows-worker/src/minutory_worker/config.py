from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .domain import COMPRESSION_PRESETS

REDACTED = "[REDACTED]"
_SECRET_CONFIG_FIELDS = {"api_token", "api_basic_auth_password", "api_custom_header_value"}


class ConfigError(ValueError):
    pass


def _optional_value(value: str, name: str) -> str | None:
    normalized = value.strip()
    if not normalized or normalized == REDACTED:
        return None
    if "\r" in normalized or "\n" in normalized:
        raise ConfigError(f"{name} must not contain line breaks.")
    return normalized


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


def _non_negative_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exception:
        raise ConfigError(f"{name} must be an integer.") from exception
    if parsed < 0:
        raise ConfigError(f"{name} must be zero or greater.")
    return parsed


def validate_api_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    parsed = urlparse(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigError("MINUTORY_API_BASE_URL must be an absolute HTTP(S) URL without credentials.")
    if parsed.scheme == "http":
        hostname = (parsed.hostname or "").rstrip(".").lower()
        loopback = hostname == "localhost"
        if not loopback:
            try:
                loopback = ip_address(hostname).is_loopback
            except ValueError:
                loopback = False
        if not loopback:
            raise ConfigError("Plain HTTP is permitted only for loopback API hosts.")
    return base_url


@dataclass(frozen=True, repr=False)
class WorkerConfig:
    api_base_url: str
    api_token: str
    api_basic_auth_username: str | None
    api_basic_auth_password: str | None
    api_custom_header_key: str | None
    api_custom_header_value: str | None
    ffmpeg_path: Path
    ffprobe_path: Path
    model_dir: Path
    runtime_dir: Path
    work_dir: Path
    state_db: Path
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    upload_timeout: float = 3600.0
    compression_preset: str = "crf22"
    video_codec: str = "h264_amf"
    fallback_video_codec: str = "libx264"
    whisper_model: str = "large-v3"
    language: str = "ro"
    vad_filter: bool = True
    vad_min_silence_ms: int = 500
    beam_size: int = 5
    batch_size: int = 0
    timezone: str = "Europe/Bucharest"

    def __repr__(self) -> str:
        values = []
        for field in fields(self):
            value = REDACTED if field.name in _SECRET_CONFIG_FIELDS else getattr(self, field.name)
            values.append(f"{field.name}={value!r}")
        return f"WorkerConfig({', '.join(values)})"

    def safe_dict(self) -> dict[str, object]:
        return {
            field.name: REDACTED if field.name in _SECRET_CONFIG_FIELDS else getattr(self, field.name)
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

    base_url = validate_api_base_url(get("MINUTORY_API_BASE_URL", "http://localhost:8000"))

    token = _optional_value(get("MINUTORY_API_TOKEN", ""), "MINUTORY_API_TOKEN") or ""
    basic_auth_username = _optional_value(
        get("MINUTORY_API_BASIC_AUTH_USERNAME", ""), "MINUTORY_API_BASIC_AUTH_USERNAME"
    )
    basic_auth_password = _optional_value(
        get("MINUTORY_API_BASIC_AUTH_PASSWORD", ""), "MINUTORY_API_BASIC_AUTH_PASSWORD"
    )
    if (basic_auth_username is None) != (basic_auth_password is None):
        raise ConfigError(
            "MINUTORY_API_BASIC_AUTH_USERNAME and MINUTORY_API_BASIC_AUTH_PASSWORD must be set together."
        )
    custom_header_key = _optional_value(
        get("MINUTORY_API_CUSTOM_HEADER_KEY", ""), "MINUTORY_API_CUSTOM_HEADER_KEY"
    )
    custom_header_value = _optional_value(
        get("MINUTORY_API_CUSTOM_HEADER_VALUE", ""), "MINUTORY_API_CUSTOM_HEADER_VALUE"
    )
    if (custom_header_key is None) != (custom_header_value is None):
        raise ConfigError(
            "MINUTORY_API_CUSTOM_HEADER_KEY and MINUTORY_API_CUSTOM_HEADER_VALUE must be set together."
        )
    preset = get("MINUTORY_COMPRESSION_PRESET", "crf22").lower()
    if preset not in COMPRESSION_PRESETS:
        raise ConfigError("MINUTORY_COMPRESSION_PRESET is invalid.")

    timezone = get("MINUTORY_TIMEZONE", "Europe/Bucharest")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exception:
        raise ConfigError("MINUTORY_TIMEZONE must be a valid IANA timezone.") from exception

    return WorkerConfig(
        api_base_url=base_url,
        api_token=token,
        api_basic_auth_username=basic_auth_username,
        api_basic_auth_password=basic_auth_password,
        api_custom_header_key=custom_header_key,
        api_custom_header_value=custom_header_value,
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
        whisper_model=get("MINUTORY_MODEL_NAME", get("MINUTORY_WHISPER_MODEL", "large-v3")),
        language=get("MINUTORY_LANGUAGE", "ro"),
        vad_filter=_boolean(get("MINUTORY_VAD_FILTER", "true"), "MINUTORY_VAD_FILTER"),
        vad_min_silence_ms=_positive_int(
            get("MINUTORY_VAD_MIN_SILENCE_MS", "500"),
            "MINUTORY_VAD_MIN_SILENCE_MS",
        ),
        beam_size=_positive_int(get("MINUTORY_BEAM_SIZE", "5"), "MINUTORY_BEAM_SIZE"),
        batch_size=_non_negative_int(get("MINUTORY_BATCH_SIZE", "0"), "MINUTORY_BATCH_SIZE"),
        timezone=timezone,
    )


def redact_text(value: str, *secrets: str | None) -> str:
    for secret in secrets:
        if secret:
            value = value.replace(secret, REDACTED)
    return value
