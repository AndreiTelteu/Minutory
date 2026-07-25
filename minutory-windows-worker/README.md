# Minutory Windows Worker — headless core

This directory contains Stage 3 of the native Windows worker: a Python 3.12+
pipeline that probes and prepares media, transcribes locally, persists every
transition in SQLite, and uploads independently retryable artifacts through the
Laravel Worker API.

Stage 3 deliberately has no GUI, installer, runtime bootstrap, bundled FFmpeg,
GPU packages, or model downloads. Stage 4 owns those concerns.

## Developer setup

```bash
cd minutory-windows-worker
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy
```

The tests use fake subprocess, ASR, and HTTP transports. They do not require a
GPU, FFmpeg, Windows, a model, or network access.

Copy `.env.example` to the ignored `.env` only on an operator machine and replace
the placeholder token there. Never paste a real credential into source, issues,
test output, or command history.

Useful headless diagnostics:

```bash
uv run minutory-worker validate-config
uv run minutory-worker list-state
```

`validate-config` always renders the token as `[REDACTED]`. `list-state` is a
read-only diagnostic: it does not require the API token, acquire writer
ownership, migrate the database, or recover running stages.

Non-loopback API URLs must use HTTPS. Plain HTTP is accepted only for
`localhost`, `127.0.0.0/8`, and `::1` development endpoints.

## Runtime boundary

The production ASR backend is `faster-whisper` Large v3 through the official
CTranslate2 ROCm/HIP Windows wheel pinned by Stage 4 to 4.8.1. The CTranslate2
API uses `device="cuda"` for the HIP runtime and `compute_type="float16"`.
`faster-whisper` is imported lazily, and one model object remains alive for the
worker process lifetime. Ordinary tests never import it.

The worker always creates API meetings with
`start_transcript_server=false`. It never asks Laravel to start Linux ASR.

See [Architecture](docs/architecture.md) and
[Stage 3 operator/developer notes](docs/stage3-operations.md).
