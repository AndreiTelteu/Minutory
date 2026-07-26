from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from minutory_worker.config import REDACTED, ConfigError, load_config, redact_text
from minutory_worker.filename_parser import (
    EditableSuggestion,
    local_datetime_to_offset_iso,
    parse_meeting_filename,
)


def test_filename_contract_fixtures() -> None:
    fixtures = json.loads((Path(__file__).parent / "fixtures/meeting_filename_cases.json").read_text())
    for fixture in fixtures:
        result = parse_meeting_filename(fixture["path"])
        assert result.title == fixture["title"]
        assert result.local_datetime == fixture["local_datetime"]


@pytest.mark.parametrize("suffix", ["0", "2026", "999", "30FPS", "29.970", "23.98", "-30", "30.0", "30 FP"])
def test_parser_does_not_strip_unsupported_terminal_suffix(suffix: str) -> None:
    title = f"Planning Fast 1080p{suffix}"
    assert parse_meeting_filename(f"{title}.mp4").title == title


def test_manual_metadata_ownership_is_separate() -> None:
    field = EditableSuggestion("automatic")
    field.apply("second")
    assert field.value == "second"
    field.manually_edited = True
    field.value = ""
    field.apply("third")
    assert field.value == ""


def test_parser_matches_final_extension_edge_cases() -> None:
    assert parse_meeting_filename("meeting.").title == "meeting"
    assert parse_meeting_filename(".hidden").title == ".hidden"


def test_local_datetime_becomes_offset_bearing() -> None:
    cases = {
        "1000-01-02T03:04:05": "1000-01-02T03:04:05+01:44",
        "1800-01-01T12:00:00": "1800-01-01T12:00:00+01:44",
        "1891-01-01T12:00:00": "1891-01-01T12:00:00+01:44",
        "2026-01-10T13:03:47": "2026-01-10T13:03:47+02:00",
        "2026-07-10T13:03:47": "2026-07-10T13:03:47+03:00",
        "2026-10-25T03:30:00": "2026-10-25T03:30:00+03:00",
    }
    laravel_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")
    for value, expected in cases.items():
        emitted = local_datetime_to_offset_iso(value)
        assert emitted == expected
        assert laravel_pattern.fullmatch(emitted)
    with pytest.raises(ValueError):
        local_datetime_to_offset_iso("2026-02-30T13:03:47")
    with pytest.raises(ValueError, match="DST"):
        local_datetime_to_offset_iso("2026-03-29T03:30:00")
    with pytest.raises(ValueError, match="timezone"):
        local_datetime_to_offset_iso("2026-07-10T13:03:47", "Not/AZone")


def test_config_requires_and_redacts_token(tmp_path: Path) -> None:
    token = "sensitive-test-value"
    config = load_config(
        environ={
            "MINUTORY_API_BASE_URL": "https://minutory.example.test/",
            "MINUTORY_API_TOKEN": token,
            "MINUTORY_STATE_DB": str(tmp_path / "state.sqlite3"),
        }
    )
    assert token not in repr(config)
    assert config.safe_dict()["api_token"] == REDACTED
    assert redact_text(f"Bearer {token}", token) == f"Bearer {REDACTED}"
    with pytest.raises(ConfigError, match="required"):
        load_config(environ={"MINUTORY_API_TOKEN": REDACTED})


def test_config_validates_url_timeouts_boolean_and_preset() -> None:
    base = {"MINUTORY_API_TOKEN": "not-a-real-token"}
    for override in (
        {"MINUTORY_API_BASE_URL": "relative"},
        {"MINUTORY_CONNECT_TIMEOUT": "0"},
        {"MINUTORY_VAD_FILTER": "maybe"},
        {"MINUTORY_COMPRESSION_PRESET": "tiny"},
        {"MINUTORY_TIMEZONE": "Not/AZone"},
        {"MINUTORY_API_BASE_URL": "http://minutory.example.test"},
    ):
        with pytest.raises(ConfigError):
            load_config(environ={**base, **override})


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.99.4.2:8000",
        "http://[::1]:8000",
        "https://minutory.example.test",
    ],
)
def test_config_accepts_https_and_http_loopback_only(url: str) -> None:
    config = load_config(environ={"MINUTORY_API_TOKEN": "fake-test-token", "MINUTORY_API_BASE_URL": url})
    assert config.api_base_url == url


def test_config_parses_model_beam_and_batch_knobs() -> None:
    config = load_config(
        environ={
            "MINUTORY_API_TOKEN": "fake-test-token",
            "MINUTORY_MODEL_NAME": "large-v3-turbo",
            "MINUTORY_BEAM_SIZE": "1",
            "MINUTORY_BATCH_SIZE": "8",
        }
    )
    assert config.whisper_model == "large-v3-turbo"
    assert config.beam_size == 1
    assert config.batch_size == 8


def test_config_model_name_falls_back_to_whisper_model() -> None:
    config = load_config(
        environ={
            "MINUTORY_API_TOKEN": "fake-test-token",
            "MINUTORY_WHISPER_MODEL": "large-v3",
        }
    )
    assert config.whisper_model == "large-v3"


def test_config_rejects_invalid_beam_and_batch() -> None:
    base = {"MINUTORY_API_TOKEN": "fake-test-token"}
    for override in (
        {"MINUTORY_BEAM_SIZE": "0"},
        {"MINUTORY_BATCH_SIZE": "-1"},
        {"MINUTORY_BEAM_SIZE": "wide"},
    ):
        with pytest.raises(ConfigError):
            load_config(environ={**base, **override})
