#!/usr/bin/env python3
"""Driver-based meeting transcription CLI for Parakeet, Whisper, and Qwen."""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import subprocess
import tempfile
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

SAMPLE_RATE = 16000
DRIVERS = ("parakeet", "whisper", "qwen")


class TranscriptionDriver(ABC):
    name: str
    model_name: str

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    @abstractmethod
    def transcribe(self, wav_path: Path) -> dict[str, Any]:
        """Return normalized transcript data."""


def normalized_segment(start: float, end: float, text: str) -> dict[str, Any]:
    start = float(start)
    end = float(end)
    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("Segment timestamps must be finite")
    start = max(0.0, start)
    end = max(start, end)
    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "text": " ".join(text.strip().split()),
        "speaker": "unknown",
    }


def read_wav(wav_path: Path) -> tuple[Any, float]:
    import numpy as np

    with wave.open(str(wav_path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getframerate() != SAMPLE_RATE or wav.getsampwidth() != 2:
            raise ValueError("Expected mono 16-bit PCM WAV at 16 kHz")
        frames = wav.readframes(wav.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, len(audio) / SAMPLE_RATE


def group_tokens_into_segments(
    tokens: Any,
    timestamps: Any,
    max_segment_duration: float = 30.0,
    min_segment_duration: float = 1.0,
) -> list[dict[str, Any]]:
    if tokens is None or timestamps is None or len(tokens) == 0 or len(timestamps) == 0:
        return []

    segments: list[dict[str, Any]] = []
    current_tokens: list[str] = []
    current_start: float | None = None
    current_end: float | None = None

    for index, (token, timestamp) in enumerate(zip(tokens, timestamps)):
        timestamp = float(timestamp)
        current_start = timestamp if current_start is None else current_start
        current_end = timestamp
        current_tokens.append(str(token))
        duration = current_end - current_start

        if (
            (str(token).strip().endswith((".", "!", "?", "。", "！", "？")) and duration >= min_segment_duration)
            or duration >= max_segment_duration
            or index == len(tokens) - 1
        ):
            text = " ".join("".join(current_tokens).replace("▁", " ").split())
            if text and duration >= 0.5:
                segments.append(normalized_segment(current_start, current_end, text))
            current_tokens = []
            current_start = None
            current_end = None

    return segments


class ParakeetDriver(TranscriptionDriver):
    name = "parakeet"
    model_name = "nemo-parakeet-tdt-0.6b-v3"

    def transcribe(self, wav_path: Path) -> dict[str, Any]:
        import onnxruntime as ort
        from onnx_asr import load_model, load_vad

        audio, total_duration = read_wav(wav_path)
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.args.threads
        options.inter_op_num_threads = self.args.threads
        options.execution_mode = ort.ExecutionMode.ORT_PARALLEL

        print(f"Loading {self.model_name} via ONNX-ASR...")
        vad = load_vad("silero", sess_options=options)
        model = (
            load_model(
                self.model_name,
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            .with_vad(vad)
            .with_timestamps()
        )

        segments: list[dict[str, Any]] = []
        for result in model.recognize(audio):
            text = (result.text or "").strip()
            local_segments = group_tokens_into_segments(result.tokens, result.timestamps)
            offset = float(getattr(result, "start", 0) or 0)
            for segment in local_segments:
                segment["start"] = round(segment["start"] + offset, 3)
                segment["end"] = round(segment["end"] + offset, 3)
                segments.append(segment)
            if text and not local_segments:
                start = offset
                end = float(getattr(result, "end", start + 5.0) or start + 5.0)
                segments.append(normalized_segment(start, end, text))

        return transcript_payload(self, segments, self.args.language, None, total_duration)


class WhisperDriver(TranscriptionDriver):
    name = "whisper"
    model_name = "large-v3"

    def transcribe(self, wav_path: Path) -> dict[str, Any]:
        from faster_whisper import WhisperModel

        compute_type = self.args.compute_type
        if compute_type == "auto":
            compute_type = "float16" if self.args.device == "cuda" else "int8"
        if self.args.device == "cpu" and compute_type in {"float16", "int8_float16"}:
            raise ValueError("Whisper float16 requires CUDA; use --compute-type int8 or float32 on CPU")

        download_root = self.args.model_dir / "whisper"
        download_root.mkdir(parents=True, exist_ok=True)
        print(
            f"Loading faster-whisper {self.model_name} on {self.args.device} "
            f"with {compute_type} (cache: {download_root})..."
        )
        model = WhisperModel(
            self.model_name,
            device=self.args.device,
            compute_type=compute_type,
            cpu_threads=self.args.threads,
            download_root=str(download_root),
        )
        raw_segments, info = model.transcribe(
            str(wav_path),
            language=self.args.language,
            beam_size=5,
            vad_filter=True,
        )
        segments = [
            normalized_segment(segment.start, segment.end, segment.text)
            for segment in raw_segments
            if segment.text and segment.text.strip()
        ]
        return transcript_payload(
            self,
            segments,
            info.language,
            info.language_probability,
            float(info.duration),
            {"compute_type": compute_type, "device": self.args.device},
        )


class QwenDriver(TranscriptionDriver):
    name = "qwen"
    model_name = "Qwen/Qwen3-ASR-1.7B"

    def transcribe(self, wav_path: Path) -> dict[str, Any]:
        import torch
        from qwen_asr import Qwen3ASRModel

        if self.args.device == "cuda":
            dtype = torch.float16
            device_map = "cuda:0"
        else:
            dtype = torch.float32
            device_map = "cpu"

        print(f"Loading {self.model_name} on {device_map} (cache: {self.args.model_dir})...")
        model = Qwen3ASRModel.from_pretrained(
            self.model_name,
            dtype=dtype,
            device_map=device_map,
            cache_dir=str(self.args.model_dir / "hub"),
            max_inference_batch_size=1,
            max_new_tokens=1024,
        )

        audio, total_duration = read_wav(wav_path)
        chunk_samples = self.args.qwen_chunk_seconds * SAMPLE_RATE
        segments: list[dict[str, Any]] = []
        language_name = "Romanian" if self.args.language == "ro" else self.args.language

        for index, start_sample in enumerate(range(0, len(audio), chunk_samples), start=1):
            chunk = audio[start_sample : start_sample + chunk_samples]
            if len(chunk) < SAMPLE_RATE // 2:
                continue
            start = start_sample / SAMPLE_RATE
            end = min(start + len(chunk) / SAMPLE_RATE, total_duration)
            print(f"Transcribing Qwen chunk {index}: {start:.1f}s-{end:.1f}s")
            result = model.transcribe(audio=(chunk, SAMPLE_RATE), language=language_name)[0]
            if result.text and result.text.strip():
                segments.append(normalized_segment(start, end, result.text))

        return transcript_payload(
            self,
            segments,
            self.args.language,
            None,
            total_duration,
            {"dtype": str(dtype), "device": self.args.device},
        )


def transcript_payload(
    driver: TranscriptionDriver,
    segments: list[dict[str, Any]],
    language: str,
    language_probability: float | None,
    duration: float,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    segments = sorted(
        (segment for segment in segments if segment["text"]),
        key=lambda segment: (segment["start"], segment["end"]),
    )
    return {
        "driver": driver.name,
        "model": driver.model_name,
        "language": language,
        "language_probability": (
            float(language_probability) if language_probability is not None else None
        ),
        "duration": round(float(duration), 3),
        "runtime": runtime or {},
        "segments": segments,
    }


def prepare_wav(audio_file: Path) -> tuple[Path, bool]:
    try:
        with wave.open(str(audio_file), "rb") as wav:
            compatible = (
                wav.getnchannels() == 1
                and wav.getframerate() == SAMPLE_RATE
                and wav.getsampwidth() == 2
            )
        if compatible:
            return audio_file, False
    except (wave.Error, EOFError):
        pass

    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.close()
    wav_path = Path(handle.name)
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio_file),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        wav_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to convert audio: {result.stderr}")
    return wav_path, True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minutory transcription driver CLI")
    parser.add_argument("--audio-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--driver", choices=DRIVERS, default="parakeet")
    parser.add_argument("--threads", type=int, default=multiprocessing.cpu_count())
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--language", default="ro")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(os.environ.get("HF_HOME", "storage/app/model")),
    )
    parser.add_argument("--qwen-chunk-seconds", type=int, default=30)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be at least 1")
    if args.qwen_chunk_seconds < 1:
        parser.error("--qwen-chunk-seconds must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    args.model_dir = args.model_dir.resolve()
    args.model_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(args.model_dir)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(args.model_dir / "hub")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["MKL_NUM_THREADS"] = str(args.threads)

    if not args.audio_file.is_file():
        raise FileNotFoundError(f"Audio file not found: {args.audio_file}")

    driver_class = {
        "parakeet": ParakeetDriver,
        "whisper": WhisperDriver,
        "qwen": QwenDriver,
    }[args.driver]
    driver = driver_class(args)
    wav_path, temporary = prepare_wav(args.audio_file)

    try:
        result = driver.transcribe(wav_path)
        if not result["segments"]:
            raise RuntimeError(f"{args.driver} returned no transcription segments")
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = args.output_file.with_suffix(args.output_file.suffix + ".tmp")
        try:
            with temporary_output.open("w", encoding="utf-8") as output:
                json.dump(result, output, indent=2, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_output, args.output_file)
        except BaseException:
            temporary_output.unlink(missing_ok=True)
            raise
        print(f"Transcription complete: {len(result['segments'])} segments")
        print(f"Transcript saved to {args.output_file}")
    finally:
        if temporary:
            wav_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
