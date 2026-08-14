#!/usr/bin/env python3
"""Emit pyannote temporal speaker turns as a standalone artifact."""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    parser.add_argument("--model", default="pyannote/speaker-diarization-community-1")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN", ""))
    args = parser.parse_args()

    from pyannote.audio import Pipeline

    started = time.monotonic()
    pipeline: Any = Pipeline.from_pretrained(args.model, token=args.token or None)
    diarization = pipeline(str(args.audio_file))
    labels: dict[str, str] = {}
    turns: list[dict[str, object]] = []
    for segment, _, label in diarization.itertracks(yield_label=True):
        start, end = float(segment.start), float(segment.end)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
            continue
        speaker = labels.setdefault(str(label), f"Speaker {len(labels) + 1}")
        turns.append({"start": start, "end": end, "speaker": speaker})
    turns.sort(key=lambda turn: (float(turn["start"]), float(turn["end"]), str(turn["speaker"])))
    document = {
        "version": 1,
        "model": args.model,
        "runtime": {"device": "cpu", "elapsed_seconds": time.monotonic() - started},
        "turns": turns,
    }
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output_file.parent, delete=False) as staged:
        json.dump(document, staged, ensure_ascii=False)
        staged.write("\n")
        staged_path = Path(staged.name)
    staged_path.replace(args.output_file)


if __name__ == "__main__":
    main()
