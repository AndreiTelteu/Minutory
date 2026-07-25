from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .atomic import atomic_copy, atomic_output
from .domain import stream_sha256


class MediaError(RuntimeError):
    pass


class Cancelled(MediaError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run(
        self, command: list[str], *, timeout: float | None = None, cancel: threading.Event | None = None
    ) -> CommandResult: ...


class SubprocessRunner:
    def run(
        self, command: list[str], *, timeout: float | None = None, cancel: threading.Event | None = None
    ) -> CommandResult:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )
        started = time.monotonic()
        try:
            while True:
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if cancel is not None and cancel.is_set():
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                    raise Cancelled("Media operation was cancelled.")
                if timeout is not None and time.monotonic() - started > timeout:
                    process.kill()
                    process.communicate()
                    raise MediaError("Media command timed out.")
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.communicate()
            raise
        return CommandResult(process.returncode, stdout, stderr)


@dataclass(frozen=True)
class Probe:
    duration: float
    width: int
    height: int
    fps: float
    fps_rational: str
    video_codec: str
    audio_codec: str | None
    bitrate: int | None


@dataclass(frozen=True)
class CompressionPreset:
    video_bitrate: int
    audio_bitrate: int


PRESETS: dict[str, CompressionPreset | None] = {
    "none": None,
    "compact": CompressionPreset(2_500_000, 128_000),
    "balanced": CompressionPreset(5_000_000, 160_000),
    "quality": CompressionPreset(8_000_000, 192_000),
}


def parse_rational(value: str) -> float:
    try:
        numerator_text, denominator_text = value.split("/", 1)
        numerator, denominator = int(numerator_text), int(denominator_text)
    except (ValueError, AttributeError) as exception:
        raise MediaError(f"Invalid rational frame rate: {value!r}.") from exception
    if denominator == 0 or numerator < 0:
        raise MediaError(f"Invalid rational frame rate: {value!r}.")
    return numerator / denominator


def parse_probe_json(content: str) -> Probe:
    try:
        data = json.loads(content)
        streams = data["streams"]
        format_data = data.get("format", {})
    except (json.JSONDecodeError, KeyError, TypeError) as exception:
        raise MediaError("FFprobe returned invalid JSON.") from exception
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not isinstance(video, dict):
        raise MediaError("Media has no video stream.")
    try:
        duration = float(format_data.get("duration", video.get("duration")))
        width, height = int(video["width"]), int(video["height"])
        rational = str(video.get("avg_frame_rate") or video["r_frame_rate"])
        fps = parse_rational(rational)
    except (TypeError, ValueError, KeyError) as exception:
        raise MediaError("FFprobe omitted required video metadata.") from exception
    if not math.isfinite(duration) or duration < 0 or width <= 0 or height <= 0 or fps <= 0:
        raise MediaError("FFprobe returned invalid video metadata.")
    bitrate_value = video.get("bit_rate", format_data.get("bit_rate"))
    try:
        bitrate = int(bitrate_value) if bitrate_value is not None else None
    except (TypeError, ValueError):
        bitrate = None
    return Probe(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        fps_rational=rational,
        video_codec=str(video.get("codec_name", "unknown")),
        audio_codec=str(audio.get("codec_name"))
        if isinstance(audio, dict) and audio.get("codec_name")
        else None,
        bitrate=bitrate,
    )


def estimate_output_bytes(duration: float, preset: CompressionPreset) -> int:
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("Duration must be finite and nonnegative.")
    return math.ceil(duration * (preset.video_bitrate + preset.audio_bitrate) / 8 * 1.02)


class MediaService:
    def __init__(self, ffprobe: Path, ffmpeg: Path, runner: Runner) -> None:
        self.ffprobe = ffprobe
        self.ffmpeg = ffmpeg
        self.runner = runner

    def probe(self, source: Path) -> Probe:
        command = [
            str(self.ffprobe),
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
        ]
        result = self.runner.run(command, timeout=120)
        if result.returncode:
            raise MediaError(f"FFprobe failed: {result.stderr.strip()[:2000]}")
        return parse_probe_json(result.stdout)

    def select_video(
        self,
        source: Path,
        destination: Path,
        preset_name: str,
        *,
        codec: str,
        fallback_codec: str | None = None,
        cancel: threading.Event | None = None,
    ) -> Path:
        preset = PRESETS.get(preset_name)
        if preset_name not in PRESETS:
            raise ValueError(f"Unknown compression preset {preset_name}.")
        if preset is None:
            if source.resolve() != destination.resolve():
                atomic_copy(source, destination)
            return destination

        def run(temporary: Path) -> None:
            command = self.compression_command(source, temporary, preset, codec)
            result = self.runner.run(command, cancel=cancel)
            if result.returncode and fallback_codec and fallback_codec != codec:
                command = self.compression_command(source, temporary, preset, fallback_codec)
                fallback_result = self.runner.run(command, cancel=cancel)
                if not fallback_result.returncode:
                    return
                raise MediaError(
                    "FFmpeg compression failed with both configured codecs: "
                    f"{result.stderr.strip()[:1000]} / {fallback_result.stderr.strip()[:1000]}"
                )
            if result.returncode:
                raise MediaError(f"FFmpeg compression failed: {result.stderr.strip()[:2000]}")

        atomic_output(destination, run)
        return destination

    def compression_command(
        self, source: Path, destination: Path, preset: CompressionPreset, codec: str
    ) -> list[str]:
        return [
            str(self.ffmpeg),
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            codec,
            "-b:v",
            str(preset.video_bitrate),
            "-maxrate",
            str(preset.video_bitrate),
            "-bufsize",
            str(preset.video_bitrate * 2),
            "-c:a",
            "aac",
            "-b:a",
            str(preset.audio_bitrate),
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(destination),
        ]

    def extract_wav(self, source: Path, destination: Path, *, cancel: threading.Event | None = None) -> Path:
        def run(temporary: Path) -> None:
            command = [
                str(self.ffmpeg),
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "wav",
                str(temporary),
            ]
            result = self.runner.run(command, cancel=cancel)
            if result.returncode:
                raise MediaError(f"FFmpeg WAV extraction failed: {result.stderr.strip()[:2000]}")
            validate_pcm16_wave(temporary)

        atomic_output(destination, run)
        return destination


def validate_pcm16_wave(path: Path) -> None:
    size = path.stat().st_size
    if size < 44:
        raise MediaError("Audio is not a complete PCM WAV file.")
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise MediaError("Audio is not a RIFF/WAVE file.")
        if struct.unpack("<I", header[4:8])[0] + 8 != size:
            raise MediaError("WAV RIFF size is inconsistent.")
        offset = 12
        format_data: tuple[int, int, int, int, int, int] | None = None
        data_size: int | None = None
        while offset + 8 <= size:
            stream.seek(offset)
            chunk_id, chunk_size = struct.unpack("<4sI", stream.read(8))
            data_start = offset + 8
            data_end = data_start + chunk_size
            padded_end = data_end + chunk_size % 2
            if data_end > size or padded_end > size:
                raise MediaError("WAV chunk exceeds file size.")
            if chunk_id == b"fmt ":
                if chunk_size < 16:
                    raise MediaError("WAV format chunk is truncated.")
                stream.seek(data_start)
                format_data = struct.unpack("<HHIIHH", stream.read(16))
            elif chunk_id == b"data":
                data_size = chunk_size
            offset = padded_end
    expected = (1, 1, 16_000, 32_000, 2, 16)
    if offset != size or format_data != expected or data_size is None or data_size <= 0 or data_size % 2:
        raise MediaError("Audio must be complete mono 16 kHz signed PCM16 WAV.")


__all__ = ["PRESETS", "MediaService", "Probe", "estimate_output_bytes", "stream_sha256"]
