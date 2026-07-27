from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .atomic import atomic_json

MAX_TIMESTAMP = 9_999_999.999


class TranscriptError(ValueError):
    pass


@dataclass(frozen=True)
class BackendSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class BackendResult:
    segments: Iterable[BackendSegment]
    language: str
    language_probability: float | None
    duration: float
    runtime: dict[str, object]


class AsrBackend(Protocol):
    model_name: str

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        vad_filter: bool,
        vad_parameters: Mapping[str, object],
    ) -> BackendResult: ...


class FasterWhisperBackend:
    """Lazy, persistent faster-whisper model wrapper for the CTranslate2 HIP wheel."""

    def __init__(
        self,
        model_path: Path,
        *,
        model_name: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        beam_size: int = 5,
        batch_size: int = 0,
    ) -> None:
        self.model_name = model_name
        self.model_path = model_path
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.batch_size = batch_size
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exception:
                raise RuntimeError(
                    "faster-whisper failed to import "
                    f"({exception}). "
                    "Stage 4 bootstrap must install the managed ROCm runtime."
                ) from exception
            model: Any = WhisperModel(
                str(self.model_path),
                device=self.device,
                compute_type=self.compute_type,
            )
            if self.batch_size > 0:
                try:
                    from faster_whisper import BatchedInferencePipeline
                except ImportError as exception:
                    raise RuntimeError(
                        f"faster-whisper BatchedInferencePipeline is unavailable ({exception})."
                    ) from exception
                model = BatchedInferencePipeline(model, batch_size=self.batch_size)
            self._model = model
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        vad_filter: bool,
        vad_parameters: Mapping[str, object],
    ) -> BackendResult:
        started = time.monotonic()
        model = self._get_model()
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=self.beam_size,
            condition_on_previous_text=False,
            vad_filter=vad_filter,
            vad_parameters=dict(vad_parameters),
        )

        def normalized_segments() -> Iterable[BackendSegment]:
            for segment in segments:
                yield BackendSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=str(segment.text),
                    speaker=getattr(segment, "speaker", None),
                )

        return BackendResult(
            segments=normalized_segments(),
            language=str(info.language or language),
            language_probability=(
                float(info.language_probability) if info.language_probability is not None else None
            ),
            duration=float(info.duration),
            runtime={
                "device": self.device,
                "compute_type": self.compute_type,
                "elapsed_seconds": time.monotonic() - started,
                "backend": "ctranslate2-rocm-4.8.1",
            },
        )


class WhisperService:
    def __init__(
        self,
        backend: AsrBackend,
        *,
        language: str = "ro",
        vad_filter: bool = True,
        vad_min_silence_ms: int = 500,
    ) -> None:
        if vad_min_silence_ms <= 0:
            raise ValueError("VAD minimum silence must be positive.")
        self.backend = backend
        self.language = language
        self.vad_filter = vad_filter
        self.vad_parameters = {"min_silence_duration_ms": vad_min_silence_ms}

    def transcribe(
        self,
        audio_path: Path,
        destination: Path,
        *,
        language: str | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> dict[str, object]:
        if on_progress is not None:
            on_progress(0.0)
        result = self.backend.transcribe(
            audio_path,
            language=language or self.language,
            vad_filter=self.vad_filter,
            vad_parameters=self.vad_parameters,
        )
        document = normalize_transcript(result, model=self.backend.model_name, on_progress=on_progress)
        atomic_json(destination, document)
        if on_progress is not None:
            on_progress(1.0)
        return document


def normalize_transcript(
    result: BackendResult,
    *,
    model: str,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, object]:
    if not model.strip() or len(model) > 255:
        raise TranscriptError("Transcript model is invalid.")
    language = result.language.strip()
    if not language or len(language) > 255:
        raise TranscriptError("Transcript language is invalid.")
    duration = _finite(result.duration, "duration")
    if duration < 0:
        raise TranscriptError("Transcript duration cannot be negative.")
    probability = result.language_probability
    if probability is not None and not 0 <= _finite(probability, "language probability") <= 1:
        raise TranscriptError("Language probability must be between zero and one.")
    if not isinstance(result.runtime, dict):
        raise TranscriptError("Transcript runtime must be an object.")

    segments: list[dict[str, object]] = []
    previous_start = -1.0
    for index, raw in enumerate(result.segments):
        start = _finite(raw.start, f"segment {index} start")
        end = _finite(raw.end, f"segment {index} end")
        text = raw.text.strip()
        speaker = raw.speaker.strip() if isinstance(raw.speaker, str) else None
        if start < 0 or end < start or start > MAX_TIMESTAMP or end > MAX_TIMESTAMP:
            raise TranscriptError(f"Segment {index} has invalid timestamps.")
        if start < previous_start:
            raise TranscriptError(f"Segment {index} is out of order.")
        if not text or len(text) > 10_000:
            raise TranscriptError(f"Segment {index} text is empty or too long.")
        if speaker is not None and len(speaker) > 255:
            raise TranscriptError(f"Segment {index} speaker is too long.")
        segments.append({"start": start, "end": end, "text": text, "speaker": speaker})
        previous_start = start
        if on_progress is not None and duration > 0:
            on_progress(min(max(end / duration, 0.0), 0.999))

    return {
        "driver": "faster-whisper-windows",
        "model": model,
        "language": language,
        "language_probability": probability,
        "duration": duration,
        "runtime": result.runtime,
        "segments": segments,
    }


def _finite(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise TranscriptError(f"Transcript {name} must be finite.")
    return number
