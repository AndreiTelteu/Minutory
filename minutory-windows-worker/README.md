# Minutory Windows Worker

This directory contains the native Windows 11 ingestion application. Its PySide6
desktop queue prepares several videos, transcribes them locally on a Radeon RX
7900 XTX, persists every transition in SQLite, and uploads independently
retryable artifacts through the Laravel Worker API.

The worker always owns transcription. Every meeting request sends
`start_transcript_server=false`; there is no GUI setting or fallback that can
delegate ASR to Laravel.

## Windows operator setup

1. Copy `.env.example` to the ignored `.env` and set the Worker API URL and authentication.
   The existing Bearer token, optional HTTP Basic credentials
   (`MINUTORY_API_BASIC_AUTH_USERNAME` / `MINUTORY_API_BASIC_AUTH_PASSWORD`),
   and optional arbitrary header (`MINUTORY_API_CUSTOM_HEADER_KEY` /
   `MINUTORY_API_CUSTOM_HEADER_VALUE`) are supported. Basic Auth replaces the
   Bearer `Authorization` header; the custom header is additive. When no
   authentication variable is configured, requests are sent without auth. Never
   commit actual secret values.
2. Obtain a release-approved `manifests/runtime-assets.local.json` containing
   verified immutable HTTPS URLs, archive SHA-256 values, and normalized
   installed-tree SHA-256 values.
3. Double-click `start.bat`. Every launch runs non-mutating bootstrap verification.
   A missing, partial, stale, or modified runtime triggers a full staged bootstrap;
   only a completely verified venv receives the readiness marker and is launched.

The tracked manifest deliberately contains unresolved values instead of invented
hashes. Bootstrap fails closed until a release workstation verifies those assets.
`bootstrap.ps1 -DryRun` validates the exact schema/archive layout without
downloading or writing and reports unresolved assets as an error.
`bootstrap.ps1 -Verify` performs no downloads and checks expected files,
installed-tree digests, the manifest/requirements/schema readiness fingerprint,
venv dependencies, Python, FFmpeg, ROCm CTranslate2, visible HIP device, RX 7900
XTX, and the declared Large v3 model snapshot.

All downloaded/generated data remains below ignored `.venv/`, `libs/`, `models/`,
`cache/`, `work/`, `state/`, and `logs/`.

## Developer setup

```bash
cd minutory-windows-worker
uv sync --extra dev
QT_QPA_PLATFORM=offscreen uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy src/minutory_worker
```

Tests use fake subprocess, ASR, and HTTP transports. Qt tests use the offscreen
platform and skip explicitly when PySide6 is unavailable; no test requires a GPU,
FFmpeg, model, authenticated server, or network.

Copy `.env.example` to the ignored `.env` only on an operator machine and replace
the placeholder token there. Never paste a real credential into source, issues,
test output, or command history.

Useful diagnostics:

```bash
uv run minutory-worker validate-config
uv run minutory-worker list-state
uv run python -m minutory_worker.runtime_verify
```

`validate-config` always renders the token as `[REDACTED]`. `list-state` is a
read-only diagnostic: it does not require the API token, acquire writer ownership,
migrate the database, or recover running stages. Non-loopback API URLs must use
HTTPS; plain HTTP is accepted only for loopback development endpoints.

## Queue and shutdown behavior

Drop MP4, MOV, AVI, or WebM files, or use **Add files**. Canonical paths are
deduplicated and the queue is restored from SQLite after restart. New files run
probe-only preflight in the serialized background lane; restored unprobed files
can use **Preflight unprobed**. Review duration/resolution/FPS and the size
estimate, choose a client, edit the suggested title/date, and select a compression
preset before starting.
Metadata and presets become immutable as soon as meeting creation is attempted,
because a lost response may hide a committed server row. This preserves the API
idempotency contract.

One long-lived execution lane serializes the complete pipeline and holds one
lazy-loaded FasterWhisper model for the application process lifetime. FFmpeg
compression/audio extraction can be cancelled safely and leaves a retryable
failed stage. Active transcription cannot be cancelled and the application
refuses to close until it finishes, avoiding CTranslate2/HIP teardown during ASR.
Errors are concise; the diagnostics disclosure contains copyable redacted detail.
Failed or reconciliation-reset uploads expose separate video/audio/transcript
retry controls. They reconcile first, never request replacement, upload only the
requested artifact when needed, and finalize when all remote artifacts match.

## Runtime boundary

The production ASR backend is `faster-whisper` 1.2.0 Large v3 through the official
CTranslate2 ROCm/HIP Windows wheel pinned to 4.8.1. The CTranslate2 API uses
`device="cuda"` for HIP and `compute_type="float16"`. `faster-whisper` is imported
lazily, and one model object remains alive for the worker process lifetime.
`whisper.cpp` is neither the default nor a fallback.
Production always loads the verified local `models/large-v3` directory. Launchers
force `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; a missing model is an
actionable startup error, never a network download.

See [Architecture](docs/architecture.md), [Stage 3 notes](docs/stage3-operations.md),
and [Stage 4 Windows operations](docs/stage4-operations.md).
