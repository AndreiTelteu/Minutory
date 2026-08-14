from __future__ import annotations

import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from .atomic import atomic_json


class SpeakerDiarizationService:
    """CPU pyannote diarization; emits independent temporal speaker evidence."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._pipeline: Any = None

    def diarize(
        self,
        audio_path: Path,
        destination: Path,
        *,
        on_progress: Callable[[float], None] | None = None,
    ) -> dict[str, object]:
        if on_progress is not None:
            on_progress(0.0)
        started = time.monotonic()
        pipeline = self._get_pipeline()
        result = pipeline(str(audio_path))
        labels: dict[str, str] = {}
        turns: list[dict[str, object]] = []
        for segment, _, raw_label in result.itertracks(yield_label=True):
            start = float(segment.start)
            end = float(segment.end)
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
                continue
            speaker = labels.setdefault(str(raw_label), f"Speaker {len(labels) + 1}")
            turns.append({"start": start, "end": end, "speaker": speaker})
        turns.sort(
            key=lambda turn: (
                cast(float, turn["start"]),
                cast(float, turn["end"]),
                cast(str, turn["speaker"]),
            )
        )
        document: dict[str, object] = {
            "version": 1,
            "model": self.model_path.name,
            "runtime": {"device": "cpu", "elapsed_seconds": time.monotonic() - started},
            "turns": turns,
        }
        atomic_json(destination, document)
        if on_progress is not None:
            on_progress(1.0)
        return document

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            try:
                from pyannote.audio import Pipeline
            except ImportError as exception:
                raise RuntimeError(
                    "SpeakerID runtime is not installed; run the managed Windows bootstrap."
                ) from exception
            self._pipeline = Pipeline.from_pretrained(self.model_path)
        return self._pipeline
