from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LEADING_TIMESTAMP = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ ](\d{2})-(\d{2})-(\d{2})(?:\s+|$)")
RECORDER_FPS = r"(?:23\.976|24|25|29\.97|30|48|50|59\.94|60|90|120|144|240)"
TERMINAL_PROFILE = re.compile(
    rf"(?:^|\s+)Fast\s+(?:720|1080|1440|2160)p\s*{RECORDER_FPS}(?:\s+FPS)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FilenameSuggestion:
    title: str
    local_datetime: str | None = None


@dataclass
class EditableSuggestion:
    value: str
    manually_edited: bool = False

    def apply(self, suggestion: str | None) -> None:
        if not self.manually_edited:
            self.value = suggestion or ""


def _basename_without_extension(path: str) -> str:
    basename = re.split(r"[/\\]", path)[-1]
    extension_index = basename.rfind(".")
    return basename[:extension_index] if extension_index > 0 else basename


def _normalize(value: str) -> str:
    return " ".join(value.split())


def parse_meeting_filename(path: str) -> FilenameSuggestion:
    title = _normalize(_basename_without_extension(path))
    local_datetime: str | None = None
    timestamp = LEADING_TIMESTAMP.match(title)
    if timestamp:
        year, month, day, hour, minute, second = (int(value) for value in timestamp.groups())
        try:
            candidate = datetime(year, month, day, hour, minute, second)
            if 1000 <= year <= 9999:
                local_datetime = candidate.isoformat(timespec="seconds")
                title = title[timestamp.end() :]
        except ValueError:
            pass
    title = _normalize(TERMINAL_PROFILE.sub("", title))
    return FilenameSuggestion(title=title, local_datetime=local_datetime)


def local_datetime_to_offset_iso(value: str, timezone: str = "Europe/Bucharest") -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exception:
        raise ValueError("Expected a valid local datetime with seconds.") from exception
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exception:
        raise ValueError("Expected a valid IANA timezone.") from exception
    aware = parsed.replace(tzinfo=zone, fold=0)
    round_trip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if round_trip != parsed:
        raise ValueError("Local datetime does not exist because of a DST transition.")
    offset = aware.utcoffset()
    if offset is None:
        raise ValueError("Local datetime timezone has no UTC offset.")
    # JavaScript Date#getTimezoneOffset exposes whole minutes. Truncating the
    # historical Bucharest LMT seconds reproduces Stage 2's +01:44 output and
    # keeps every emitted value inside Laravel's ±HH:MM validation contract.
    offset_minutes = int(offset.total_seconds() / 60)
    sign = "+" if offset_minutes >= 0 else "-"
    absolute_minutes = abs(offset_minutes)
    offset_text = f"{sign}{absolute_minutes // 60:02d}:{absolute_minutes % 60:02d}"
    return f"{parsed.isoformat(timespec='seconds')}{offset_text}"
