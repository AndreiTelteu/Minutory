"""Offline pyannote 3.1 ONNX diarization, adapted from pyannote-onnx-extended.

The worker owns this reviewed adapter: no PyTorch/pyannote runtime is imported
at inference time. DirectML is selected explicitly; CPUExecutionProvider is a
graceful fallback when DirectML cannot initialize or fails during inference.
"""

from __future__ import annotations

import math
import os
import subprocess
import time
import wave
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .atomic import atomic_json

ENGINE = "pyannote-onnx-extended"
MODEL = "pyannote/speaker-diarization-3.1"


class DiarizationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderSelection:
    provider: str
    device: str
    providers: list[Any]
    fallback: bool = False


def select_provider(available: Sequence[str], *, device_id: int, device: str) -> ProviderSelection:
    if "DmlExecutionProvider" in available:
        return ProviderSelection(
            "DmlExecutionProvider", device, [("DmlExecutionProvider", {"device_id": device_id})]
        )
    return ProviderSelection("CPUExecutionProvider", "CPU fallback", ["CPUExecutionProvider"], True)


def windows_discrete_adapter() -> tuple[int, str]:
    """Discover the RX 7900 XTX and use its explicit DXGI DirectML ordinal."""
    try:
        device_id = int(os.environ.get("MINUTORY_DML_DEVICE_ID", "0"))
    except ValueError as exception:
        raise DiarizationError("MINUTORY_DML_DEVICE_ID must be a non-negative integer.") from exception
    if device_id < 0:
        raise DiarizationError("MINUTORY_DML_DEVICE_ID must be a non-negative integer.")
    if os.name != "nt":
        return device_id, f"DirectML adapter {device_id} (test host)"
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        adapters = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except OSError as exception:
        raise DiarizationError("Could not enumerate Windows graphics adapters.") from exception
    name = next((value for value in adapters if "7900 XTX" in value.upper()), None)
    if name is None:
        raise DiarizationError("RX 7900 XTX was not reported by Windows; refusing DirectML selection.")
    return device_id, f"{name} (DirectML device_id={device_id})"


class SpeakerDiarizationService:
    def __init__(self, model_path: Path, *, device_id: int | None = None) -> None:
        self.model_path, self.device_id = model_path, device_id
        self._sessions: tuple[Any, Any] | None = None
        self._selection: ProviderSelection | None = None

    def diarize(
        self, audio_path: Path, destination: Path, *, on_progress: Callable[[float], None] | None = None
    ) -> dict[str, object]:
        if on_progress:
            on_progress(0.0)
        started = time.monotonic()
        try:
            turns = self._run(audio_path, on_progress)
            selection = self._selection_or_cpu()
            status = "fallback_cpu" if selection.fallback else "completed"
            document = self._document(status, selection, started, turns)
        except Exception as exception:
            try:
                if self._selection_or_cpu().provider != "DmlExecutionProvider":
                    raise exception
                self._activate_cpu_fallback()
                document = self._document(
                    "fallback_cpu", self._selection_or_cpu(), started, self._run(audio_path, on_progress)
                )
            except Exception as fallback_error:
                document = self._document(
                    "failed", self._selection_or_cpu(), started, [], error=_safe_error(fallback_error)
                )
        atomic_json(destination, document)
        if on_progress:
            on_progress(1.0)
        return document

    def _run(self, audio_path: Path, progress: Callable[[float], None] | None) -> list[dict[str, object]]:
        segmentation, embedding = self._get_sessions()
        waveform = _read_pcm16_mono(audio_path)
        segments = _segment(waveform, segmentation, progress)
        embeddings, valid = _embeddings(waveform, segments, embedding, progress)
        return _normalize_turns(
            [
                {"start": start, "end": end, "speaker": f"SPEAKER_{label:02d}"}
                for (start, end), label in zip(valid, _cluster(embeddings, valid), strict=True)
            ]
        )

    def _get_sessions(self) -> tuple[Any, Any]:
        if self._sessions is not None:
            return self._sessions
        segmentation, embedding = self.model_path / "segmentation.onnx", self.model_path / "embedding.onnx"
        if not segmentation.is_file() or not embedding.is_file():
            raise DiarizationError("Verified ONNX diarization bundle is incomplete; run managed bootstrap.")
        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
        except ImportError as exception:
            raise DiarizationError(
                "onnxruntime-directml is not installed; run managed bootstrap."
            ) from exception
        device_id, device = windows_discrete_adapter()
        if self.device_id is not None:
            device_id, device = self.device_id, f"RX 7900 XTX (DirectML device_id={self.device_id})"
        selection = select_provider(ort.get_available_providers(), device_id=device_id, device=device)
        try:
            self._sessions = (
                ort.InferenceSession(str(segmentation), providers=selection.providers),
                ort.InferenceSession(str(embedding), providers=selection.providers),
            )
            self._selection = selection
        except Exception as directml_error:
            if selection.provider != "DmlExecutionProvider":
                raise DiarizationError("CPU ONNX Runtime initialization failed.") from directml_error
            fallback = ProviderSelection(
                "CPUExecutionProvider",
                "CPU fallback after DirectML initialization failure",
                ["CPUExecutionProvider"],
                True,
            )
            try:
                self._sessions = (
                    ort.InferenceSession(str(segmentation), providers=fallback.providers),
                    ort.InferenceSession(str(embedding), providers=fallback.providers),
                )
                self._selection = fallback
            except Exception as cpu_error:
                raise DiarizationError("DirectML and CPU ONNX Runtime initialization failed.") from cpu_error
        return self._sessions

    def _activate_cpu_fallback(self) -> None:
        import onnxruntime as ort

        self._selection = ProviderSelection(
            "CPUExecutionProvider",
            "CPU fallback after DirectML runtime failure",
            ["CPUExecutionProvider"],
            True,
        )
        self._sessions = (
            ort.InferenceSession(
                str(self.model_path / "segmentation.onnx"), providers=self._selection.providers
            ),
            ort.InferenceSession(
                str(self.model_path / "embedding.onnx"), providers=self._selection.providers
            ),
        )

    def _selection_or_cpu(self) -> ProviderSelection:
        return self._selection or ProviderSelection(
            "CPUExecutionProvider", "CPU unavailable", ["CPUExecutionProvider"], True
        )

    def _document(
        self,
        status: str,
        selection: ProviderSelection,
        started: float,
        turns: list[dict[str, object]],
        *,
        error: str | None = None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "status": status,
            "engine": ENGINE,
            "model": MODEL,
            "provider": selection.provider,
            "device": selection.device,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "speaker_count": len({str(turn["speaker"]) for turn in turns}),
        }
        if error:
            metadata["error"] = error
        return {"version": 2, "diarization": metadata, "turns": turns}


def merge_transcript(transcript: dict[str, object], diarization: dict[str, object]) -> dict[str, object]:
    result = dict(transcript)
    metadata = cast(
        dict[str, object],
        diarization.get("diarization") if isinstance(diarization.get("diarization"), dict) else {},
    )
    turns = _normalize_turns(diarization.get("turns", [])) if metadata.get("status") != "failed" else []
    segments = transcript.get("segments")
    if not isinstance(segments, list):
        raise DiarizationError("ASR transcript has no segments.")
    result["segments"] = [
        {**segment, "speaker": _speaker_for(float(segment["start"]), float(segment["end"]), turns)}
        for segment in segments
        if isinstance(segment, dict)
    ]
    result["diarization"] = metadata
    return result


def _speaker_for(start: float, end: float, turns: list[dict[str, object]]) -> str:
    evidence: dict[str, float] = {}
    for turn in turns:
        overlap = max(0.0, min(end, float(turn["end"])) - max(start, float(turn["start"])))  # type: ignore[arg-type]
        if overlap:
            evidence[str(turn["speaker"])] = evidence.get(str(turn["speaker"]), 0.0) + overlap
    if not evidence or end <= start:
        return "Unknown"
    speaker, overlap = max(evidence.items(), key=lambda item: (item[1], item[0]))
    return speaker if overlap / (end - start) >= 0.2 else "Unknown"


def _normalize_turns(raw: object) -> list[dict[str, object]]:
    labels: dict[str, str] = {}
    turns: list[dict[str, object]] = []
    if not isinstance(raw, list):
        return turns
    for value in raw:
        if not isinstance(value, dict):
            continue
        try:
            start, end = float(value["start"]), float(value["end"])
        except (KeyError, TypeError, ValueError):
            continue
        label = str(value.get("speaker", ""))
        if math.isfinite(start) and math.isfinite(end) and start >= 0 and end > start and label:
            turns.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "speaker": labels.setdefault(label, f"Speaker {len(labels) + 1}"),
                }
            )
    return sorted(turns, key=lambda turn: (float(turn["start"]), float(turn["end"]), str(turn["speaker"])))  # type: ignore[arg-type]


def _read_pcm16_mono(path: Path) -> Any:
    import numpy as np

    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getframerate() != 16000 or source.getsampwidth() != 2:
            raise DiarizationError("Diarization requires the worker mono PCM16 16 kHz WAV.")
        return np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype("float32") / 32768.0


def _segment(
    waveform: Any, session: Any, progress: Callable[[float], None] | None
) -> list[tuple[float, float]]:
    import numpy as np

    sample_rate, window, step = 16000, 160000, 80000
    padded = np.pad(waveform, (0, (-len(waveform)) % window))
    scores: dict[int, tuple[Any, int]] = {}
    for _index, offset in enumerate(range(0, max(1, len(padded) - window + 1), step)):
        model_output = session.run(
            None, {session.get_inputs()[0].name: padded[offset : offset + window][None, None, :]}
        )[0][0]
        probabilities = np.exp(model_output)[:, 1:4]
        for frame, score in enumerate(probabilities):
            key = int(offset / step * (len(probabilities) / 2) + frame)
            old, count = scores.get(key, (np.zeros(3), 0))
            scores[key] = (old + score, count + 1)
        if progress:
            progress(min(0.55, 0.55 * (offset + step) / max(len(waveform), 1)))
    if not scores:
        return []
    frame_seconds = 10 / len(probabilities)
    turns: list[tuple[float, float]] = []
    for channel in range(3):
        active: float | None = None
        for frame in range(max(scores) + 1):
            score, count = scores.get(frame, (np.zeros(3), 1))
            timestamp = frame * frame_seconds
            speech = score[channel] / count > 0.5
            if speech and active is None:
                active = timestamp
            elif not speech and active is not None:
                if timestamp - active >= 0.5:
                    turns.append((active, timestamp))
                active = None
        if active is not None and len(waveform) / sample_rate - active >= 0.5:
            turns.append((active, float(len(waveform) / sample_rate)))
    return turns


def _embeddings(
    waveform: Any, segments: list[tuple[float, float]], session: Any, progress: Callable[[float], None] | None
) -> tuple[Any, list[tuple[float, float]]]:
    import librosa  # type: ignore[import-not-found]
    import numpy as np

    embeddings, valid = [], []
    for index, (start, end) in enumerate(segments):
        chunk = waveform[int(start * 16000) : int(end * 16000)]
        if len(chunk) < 400:
            continue
        features = np.log(
            librosa.feature.melspectrogram(
                y=chunk, sr=16000, n_fft=400, hop_length=160, n_mels=80, window="hamming", center=False
            )
            + 1e-6
        ).T
        features -= features.mean(axis=0)
        vector = session.run(None, {session.get_inputs()[0].name: features[None, :, :]})[0][0]
        norm = np.linalg.norm(vector)
        if norm > 1e-6:
            embeddings.append(vector / norm)
            valid.append((start, end))
        if progress:
            progress(0.55 + 0.45 * (index + 1) / max(len(segments), 1))
    return np.asarray(embeddings), valid


def _cluster(embeddings: Any, segments: list[tuple[float, float]]) -> list[int]:
    import numpy as np
    from scipy.spatial.distance import cdist  # type: ignore[import-untyped]
    from sklearn.cluster import AgglomerativeClustering  # type: ignore[import-not-found]

    if len(embeddings) < 2:
        return [0] * len(embeddings)
    duration = sum(end - start for start, end in segments)
    long = [
        index for index, (start, end) in enumerate(segments) if end - start >= min(5, max(2, duration / 60))
    ]
    if len(long) < 2:
        return [0] * len(embeddings)
    labels = np.zeros(len(embeddings), dtype=int)
    clustered = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=max((350 - duration) / 350, 0.73),
        metric="euclidean",
        linkage="single",
    ).fit_predict(embeddings[long])
    labels[long] = clustered
    centers = np.asarray(
        [embeddings[long][clustered == label].mean(axis=0) for label in sorted(set(clustered))]
    )
    short = [index for index in range(len(embeddings)) if index not in long]
    if short:
        labels[short] = np.argmin(cdist(embeddings[short], centers, metric="euclidean"), axis=1)
    return [int(value) for value in labels]


def _safe_error(exception: Exception) -> str:
    return str(exception).replace("\r", " ").replace("\n", " ")[:500] or exception.__class__.__name__
