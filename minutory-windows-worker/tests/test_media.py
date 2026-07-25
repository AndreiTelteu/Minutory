from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from conftest import pcm_wave

from minutory_worker.atomic import atomic_output
from minutory_worker.domain import stream_sha256
from minutory_worker.media import (
    PRESETS,
    Cancelled,
    CommandResult,
    MediaError,
    MediaService,
    estimate_output_bytes,
    parse_probe_json,
    parse_rational,
    validate_pcm16_wave,
)


class FakeRunner:
    def __init__(self, result: CommandResult | None = None):
        self.result = result or CommandResult(0, "", "")
        self.commands: list[list[str]] = []

    def run(self, command, **kwargs):
        self.commands.append(command)
        return self.result


def probe_document(frame_rate: str = "30000/1001") -> str:
    return json.dumps(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": frame_rate,
                    "bit_rate": "7000000",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "60.5", "bit_rate": "7200000"},
        }
    )


def test_probe_parsing_rational_streams_and_bitrate() -> None:
    probe = parse_probe_json(probe_document())
    assert probe.duration == 60.5
    assert (probe.width, probe.height) == (1920, 1080)
    assert probe.fps == pytest.approx(29.97002997)
    assert probe.audio_codec == "aac"
    assert probe.bitrate == 7_000_000
    assert parse_rational("24000/1001") == pytest.approx(23.9760239)
    for invalid in ("broken", "1/0", "-1/1"):
        with pytest.raises(MediaError):
            parse_rational(invalid)


def test_estimate_is_documented_formula() -> None:
    preset = PRESETS["balanced"]
    assert preset is not None
    assert estimate_output_bytes(60, preset) == math.ceil(60 * (5_000_000 + 160_000) / 8 * 1.02)


def test_compression_command_preserves_resolution_and_fps(source: Path, tmp_path: Path) -> None:
    runner = FakeRunner()
    service = MediaService(Path("ffprobe"), Path("ffmpeg"), runner)
    preset = PRESETS["quality"]
    assert preset is not None
    command = service.compression_command(source, tmp_path / "out.mp4", preset, "h264_amf")
    assert "-vf" not in command
    assert "-filter:v" not in command
    assert "-r" not in command
    assert "-s" not in command
    assert command[command.index("-c:v") + 1] == "h264_amf"
    assert command[command.index("-b:v") + 1] == "8000000"


def test_probe_command_and_errors(source: Path) -> None:
    runner = FakeRunner(CommandResult(0, probe_document(), ""))
    probe = MediaService(Path("probe.exe"), Path("ffmpeg.exe"), runner).probe(source)
    assert probe.width == 1920
    assert runner.commands[0][0] == "probe.exe"
    runner.result = CommandResult(1, "", "corrupt")
    with pytest.raises(MediaError, match="corrupt"):
        MediaService(Path("probe"), Path("ffmpeg"), runner).probe(source)


def test_atomic_output_preserves_good_destination_and_cleans_temp(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.bin"
    destination.write_bytes(b"known-good")

    def fail(temporary: Path) -> None:
        temporary.write_bytes(b"partial")
        raise RuntimeError("failure")

    with pytest.raises(RuntimeError):
        atomic_output(destination, fail)
    assert destination.read_bytes() == b"known-good"
    assert list(tmp_path.glob(".artifact.bin.*.tmp")) == []


def test_atomic_output_requires_writer_to_create_file(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.bin"
    destination.write_bytes(b"known-good")
    with pytest.raises(RuntimeError, match="did not create"):
        atomic_output(destination, lambda _: None)
    assert destination.read_bytes() == b"known-good"


def test_wave_validation_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "audio.wav"
    path.write_bytes(pcm_wave())
    validate_pcm16_wave(path)
    assert stream_sha256(path) == "3e9bdf4cffd0b09b1ce550cf199542cd54fdaf69bf4f53d2e1b8be88c02f5aa3"
    path.write_bytes(pcm_wave()[:-1])
    with pytest.raises(MediaError):
        validate_pcm16_wave(path)


def test_extract_wav_command_and_atomic_cleanup(source: Path, tmp_path: Path) -> None:
    class WaveRunner(FakeRunner):
        def run(self, command, **kwargs):
            self.commands.append(command)
            Path(command[-1]).write_bytes(pcm_wave())
            return self.result

    runner = WaveRunner()
    destination = tmp_path / "audio.wav"
    MediaService(Path("probe"), Path("ffmpeg"), runner).extract_wav(source, destination)
    command = runner.commands[0]
    assert command[command.index("-acodec") + 1] == "pcm_s16le"
    assert command[command.index("-ar") + 1] == "16000"
    assert command[command.index("-ac") + 1] == "1"
    validate_pcm16_wave(destination)


def test_compression_falls_back_and_cancellation_cleans_partial(source: Path, tmp_path: Path) -> None:
    class FallbackRunner(FakeRunner):
        def run(self, command, **kwargs):
            self.commands.append(command)
            if command[command.index("-c:v") + 1] == "h264_amf":
                Path(command[-1]).write_bytes(b"partial")
                return CommandResult(1, "", "AMF unavailable")
            Path(command[-1]).write_bytes(b"fallback")
            return CommandResult(0, "", "")

    runner = FallbackRunner()
    destination = tmp_path / "video.mp4"
    service = MediaService(Path("probe"), Path("ffmpeg"), runner)
    service.select_video(
        source,
        destination,
        "balanced",
        codec="h264_amf",
        fallback_codec="libx264",
    )
    assert destination.read_bytes() == b"fallback"
    assert [command[command.index("-c:v") + 1] for command in runner.commands] == [
        "h264_amf",
        "libx264",
    ]

    class CancelRunner(FakeRunner):
        def run(self, command, **kwargs):
            Path(command[-1]).write_bytes(b"partial")
            raise Cancelled("cancelled")

    known_good = tmp_path / "known.mp4"
    known_good.write_bytes(b"known-good")
    with pytest.raises(Cancelled):
        MediaService(Path("probe"), Path("ffmpeg"), CancelRunner()).select_video(
            source,
            known_good,
            "balanced",
            codec="h264_amf",
            fallback_codec="libx264",
        )
    assert known_good.read_bytes() == b"known-good"
    assert list(tmp_path.glob(".known.mp4.*.tmp")) == []
