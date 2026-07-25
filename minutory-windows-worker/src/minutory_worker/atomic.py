from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def atomic_output(destination: Path, writer: Callable[[Path], None]) -> None:
    """Write beside destination and replace it only after writer succeeds."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        writer(temporary)
        if not temporary.is_file():
            raise RuntimeError(f"Writer did not create output for {destination.name}.")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_copy(source: Path, destination: Path) -> None:
    atomic_output(destination, lambda temporary: shutil.copyfile(source, temporary))


def atomic_json(destination: Path, value: Any) -> None:
    def write(temporary: Path) -> None:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    atomic_output(destination, write)
