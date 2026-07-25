# Stage 3 architecture

## Pipeline and retry boundary

Each item has a stable UUID v4 and these persisted stages:

1. `probe`
2. `source` — atomic copy or compression
3. `wav` — mono 16 kHz signed PCM16 extraction
4. `transcribe` — local faster-whisper and normalized JSON
5. `meeting` — idempotent metadata create/recovery
6. `video_upload`
7. `audio_upload`
8. `transcript_upload`

Dependencies are explicit in `domain.py`; success is stored after every stage.
A failed upload therefore does not discard or rerun compression, WAV extraction,
or ASR. Startup converts stale `running` stages to a retryable `failed` state
with separate concise and diagnostic errors.

Before a persisted server meeting is resumed, the orchestrator reconciles its
three durable server artifact hashes. Matching remote state advances the local
upload stage. A different remote hash raises a conflict. The core never silently
sets `replace=true`; a future GUI/operator action must opt into replacement.

## State and source identity

SQLite uses schema versioning through `PRAGMA user_version`, foreign keys, WAL,
`busy_timeout`, a process lock, and `BEGIN IMMEDIATE` transactions. The `items`
row owns editable metadata and artifact paths/hashes; `stages` owns status,
attempt count, user-facing error, and technical diagnostic.

Source identity contains resolved path, byte size, and nanosecond mtime, with an
optional streamed SHA-256 policy. A changed source invalidates `probe` and its
dependency closure, while retaining the stable UUID and server meeting ID so
reconciliation can surface any remote conflict instead of replacing data.

## Atomic artifacts

Every local output is written to a random temporary file in the destination
directory and installed with `os.replace`. Failures and cancellation delete the
temporary file and preserve any last known-good destination. Hashing is streamed.

Compression presets set video and audio bitrates but do not use scaling filters,
`-r`, or another forced frame-rate conversion. The size display is explicitly an
estimate:

`duration × (video bitrate + audio bitrate) / 8 × 1.02`

## API and secrets

The client matches `/api/v1/worker`, sends Bearer authentication, creates with
the item UUID, and uploads video/audio/transcript separately. Transport is
dependency-injected. Only transport errors, HTTP 429, and HTTP 5xx are retried;
validation, authentication, and conflict errors are permanent. Numeric
`Retry-After` is honored.

Configuration representations, diagnostics, and CLI output redact the token.
Tracked configuration uses `[REDACTED]` only.
