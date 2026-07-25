from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from minutory_worker.domain import SourceIdentity, WorkerItem
from minutory_worker.state import StateStore


def pcm_wave(samples: bytes = b"\0\0\0\0") -> bytes:
    size = len(samples)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + size)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 16_000, 32_000, 2, 16)
        + b"data"
        + struct.pack("<I", size)
        + samples
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "source.mp4"
    path.write_bytes(b"source-video")
    return path


@pytest.fixture
def item(source: Path) -> WorkerItem:
    return WorkerItem(
        source=SourceIdentity.from_path(source),
        title="Planning",
        meeting_at="2026-07-10T13:03:47+03:00",
        client_id=52,
    )


@pytest.fixture
def store(tmp_path: Path, item: WorkerItem) -> StateStore:
    state = StateStore(tmp_path / "state.sqlite3")
    state.add_item(item)
    yield state
    state.close()


def response(status: int, body: object, headers: dict[str, str] | None = None):
    from minutory_worker.api import TransportResponse

    return TransportResponse(status, headers or {}, json.dumps(body).encode())
