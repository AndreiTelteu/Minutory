"""Explicit online model preparation; normal worker startup remains offline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from dotenv import dotenv_values

WHISPER_REVISION = "edaa852ec7e145841d8ffdb056a99866b5f0a478"
EXPORT_COMMIT = "edb7dbc1f6fa5c586064665c016947fc0057a32c"
WHISPER_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.json", "preprocessor_config.json")
SPEAKER_FILES = ("segmentation.onnx", "embedding.onnx", "metadata.json")
CONSTRAINTS = """torch==2.0.1+cpu
torchaudio==2.0.2+cpu
numpy==1.26.4
pytorch-lightning==2.0.9
torchmetrics==1.2.1
setuptools==68.2.2
huggingface-hub==0.25.2
"""


def complete(path: Path, files: tuple[str, ...]) -> bool:
    return all((path / name).is_file() and (path / name).stat().st_size > 0 for name in files)


def promote(staging: Path, destination: Path) -> None:
    """Keep the existing bundle until every new model has been validated."""
    backup = destination.with_name(f".{destination.name}-{uuid.uuid4().hex}.previous")
    had_old = destination.exists()
    if had_old:
        destination.rename(backup)
    try:
        staging.rename(destination)
    except OSError:
        if had_old:
            backup.rename(destination)
        raise
    if had_old:
        shutil.rmtree(backup)


def prepare_whisper(model_dir: Path) -> None:
    from huggingface_hub import snapshot_download

    destination = model_dir / "large-v3"
    if complete(destination, WHISPER_FILES):
        print("Whisper Large v3 is already installed.", flush=True)
        return
    print("Downloading Whisper Large v3 (about 3 GB)...", flush=True)
    with tempfile.TemporaryDirectory(prefix=".whisper-", dir=model_dir) as directory:
        staging = Path(directory) / "large-v3"
        snapshot_download(
            "Systran/faster-whisper-large-v3",
            revision=WHISPER_REVISION,
            allow_patterns=list(WHISPER_FILES),
            local_dir=staging,
            token=False,
        )
        if not complete(staging, WHISPER_FILES):
            raise RuntimeError("Whisper snapshot is incomplete.")
        promote(staging, destination)
    print("Whisper Large v3 installed.", flush=True)


def prepare_speakers(root: Path, model_dir: Path, token: str) -> None:
    destination = model_dir / "pyannote-diarization-3.1-onnx"
    if complete(destination, SPEAKER_FILES):
        print("Speaker ONNX bundle is already installed.", flush=True)
        return
    if not token or token == "[REDACTED]":
        raise RuntimeError(
            "Accept the pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0 "
            "terms on Hugging Face, then set MINUTORY_DIARIZATION_TOKEN in .env."
        )
    cache = root / "cache"
    cache.mkdir(exist_ok=True)
    repo = cache / "build" / "pyannote-export"
    if not (repo / ".git").is_dir():
        repo.parent.mkdir(exist_ok=True)
        subprocess.run(
            ["git", "clone", "https://github.com/samson6460/pyannote-onnx-extended.git", str(repo)],
            check=True,
        )
    subprocess.run(["git", "-C", str(repo), "checkout", "--detach", EXPORT_COMMIT], check=True)
    venv = cache / "export-venv"
    python = venv / "bin" / "python"
    if not python.exists():
        subprocess.run(["uv", "venv", "--python", "3.11", str(venv)], check=True)
    constraints = cache / "export-constraints.txt"
    constraints.write_text(CONSTRAINTS, encoding="utf-8")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--index-strategy",
            "unsafe-best-match",
            "--extra-index-url",
            "https://download.pytorch.org/whl/cpu",
            "-c",
            str(constraints),
            "pyannote.audio==3.1.1",
            "onnx",
            "setuptools",
        ],
        check=True,
    )
    environment = dict(os.environ)
    environment.update(
        MINUTORY_DIARIZATION_TOKEN=token,
        HF_HUB_OFFLINE="0",
        TRANSFORMERS_OFFLINE="0",
        HF_HOME=str(cache / "huggingface"),
    )
    # The token is read from the environment, never put in command-line arguments.
    code = (
        "import os; from export_onnx import export_onnx; "
        "export_onnx(os.environ['MINUTORY_DIARIZATION_TOKEN'])"
    )
    print("Downloading and exporting accepted pyannote models...", flush=True)
    output = repo / "models_onnx"
    if output.exists():
        shutil.rmtree(output)
    result = subprocess.run(
        [str(python), "-c", code],
        cwd=repo,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    log = logs / "speaker-export.log"
    log.write_text(result.stdout.replace(token, "[REDACTED]"), encoding="utf-8")
    if result.returncode or not complete(output, ("segmentation.onnx", "embedding.onnx")):
        raise RuntimeError(
            f"Speaker export failed. Check {log}; confirm access to both gated pyannote models."
        )
    import onnxruntime as ort  # type: ignore[import-untyped]

    for filename in ("segmentation.onnx", "embedding.onnx"):
        ort.InferenceSession(str(output / filename), providers=["CPUExecutionProvider"])
    with tempfile.TemporaryDirectory(prefix=".speakers-", dir=model_dir) as directory:
        staging = Path(directory) / "bundle"
        staging.mkdir()
        for filename in ("segmentation.onnx", "embedding.onnx"):
            shutil.copyfile(output / filename, staging / filename)
        (staging / "metadata.json").write_text(
            json.dumps(
                {
                    "engine": "pyannote-onnx-extended",
                    "model": "pyannote/speaker-diarization-3.1",
                    "upstream_commit": EXPORT_COMMIT,
                }
            ),
            encoding="utf-8",
        )
        promote(staging, destination)
    print("Speaker ONNX bundle installed.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--whisper-only", action="store_true")
    group.add_argument("--speakers-only", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    values = {**dotenv_values(root / ".env"), **os.environ}
    model_dir = Path(values.get("MINUTORY_MODEL_DIR") or "./models")
    if not model_dir.is_absolute():
        model_dir = root / model_dir
    model_dir.mkdir(parents=True, exist_ok=True)
    token = values.get("MINUTORY_DIARIZATION_TOKEN") or ""
    os.environ.update(HF_HUB_OFFLINE="0", TRANSFORMERS_OFFLINE="0")
    try:
        if not arguments.speakers_only:
            prepare_whisper(model_dir)
        if not arguments.whisper_only:
            prepare_speakers(root, model_dir, token)
    except Exception as exception:
        print(str(exception).replace(token, "[REDACTED]") if token else str(exception), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
