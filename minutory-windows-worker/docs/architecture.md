# Windows worker architecture

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
9. `final_reconcile` — confirm all server hashes and sizes before completion

Dependencies are explicit in `domain.py`; success is stored after every stage.
A failed upload therefore does not discard or rerun compression, WAV extraction,
or ASR. Startup converts stale `running` stages to a retryable `failed` state
with separate concise and diagnostic errors.

Before a persisted server meeting is resumed, and again before first-run
completion, the orchestrator reconciles all three durable server artifact hashes
and sizes. Matching state advances the local upload stage. A remotely missing
file transactionally resets its upload and final reconciliation stages. A
different remote hash or size raises a conflict. The core never silently sets
`replace=true`; a future GUI/operator action must opt into replacement.

Immediately before every upload, the worker streams the file hash and reads its
size again, comparing both with the durable generation result. Upload responses
must echo that exact hash and size before the stage can succeed.

## State and source identity

SQLite uses schema versioning through `PRAGMA user_version`, foreign keys, WAL,
`busy_timeout`, and `BEGIN IMMEDIATE` transactions. A lifetime single-writer
lock uses `msvcrt` on Windows and `fcntl` on POSIX. Stale `running` recovery only
begins after that lock proves the old writer is gone. `list-state` opens SQLite
in read-only mode and never migrates or recovers state.

The `items` row owns editable metadata and artifact paths/hashes/sizes; `stages`
owns status, attempt count, user-facing error, and technical diagnostic.
Stage 4 also persists probe width, height, FPS, and source bitrate. It stores only
canonical source path identity—not a Qt file object—so the queue can be restored.

The GUI and processing lane share exactly one `StateStore` connection.
`check_same_thread=false` is paired with the store's reentrant lock; public reads,
writes, metadata mutation, preset invalidation, and pre-server deletion all pass
through that serialization boundary.

Source identity contains resolved path, byte size, and nanosecond mtime, with an
optional streamed SHA-256 policy. A changed source invalidates `probe` and its
dependency closure before meeting creation. Source changes after server meeting
creation are refused. Metadata, removal, and compression-preset changes are
conservatively refused after the first meeting attempt because a lost response
may hide a committed server row; the operator must create a new item.
A preset change preserves probe metadata while transactionally invalidating
`source` and its true dependency closure.

## Atomic artifacts

Every local output is written to a random temporary file in the destination
directory and installed with `os.replace`. Failures and cancellation delete the
temporary file and preserve any last known-good destination. Hashing is streamed.

Compression presets set video and audio bitrates but do not use scaling filters,
`-r`, or another forced frame-rate conversion. The size display is explicitly an
estimate:

`duration × (video bitrate + audio bitrate) / 8 × 1.02`

Encoded output is post-probed before atomic replacement. It must be readable MP4
with positive duration and the source resolution and rational frame rate.

## API and secrets

The client matches `/api/v1/worker`, sends Bearer authentication, creates with
the item UUID, and uploads video/audio/transcript separately. Transport is
dependency-injected. Only transport errors, HTTP 429, and HTTP 5xx are retried;
validation, authentication, and conflict errors are permanent. Delta-seconds and
IMF-fixdate `Retry-After` values are honored.

Configuration representations, diagnostics, and CLI output redact the token.
Tracked configuration uses `[REDACTED]` only. HTTPS is required except for
loopback development hosts (`localhost`, `127.0.0.0/8`, and `::1`).

Europe/Bucharest filename datetimes reject DST gaps, select `fold=0`
deterministically, and emit only `Z` or minute-resolution `±HH:MM` offsets.
Historical LMT seconds are truncated to match Stage 2 browser semantics.

## Stage 4 presentation and execution

`presentation.py` owns the testable queue controller, immutable view snapshots,
client validation, size estimates, and single-lane `ProcessingCoordinator`. The
PySide6 classes only bind widgets, dialogs, drag/drop, and signals to that
controller. Worker results cross into the Qt main thread through a signal; worker
threads never mutate widgets.

The coordinator has one persistent executor thread. It coalesces duplicate item
starts and serializes all queued pipelines, which serializes FasterWhisper GPU use
through one lazily loaded model instance. `Orchestrator.process_next_stage` also
exposes a safe stage-sized integration seam, while normal GUI runs retain the
Stage 3 resume loop.

Compression and WAV extraction receive a cancellation event that terminates and,
after a grace period, kills only the active child process. Atomic outputs preserve
known-good artifacts and the running stage becomes failed/retryable. Transcription
is deliberately non-cancellable. Closing is refused while it is active so the
model is never torn down mid-call.

## Bootstrap trust boundary

The tracked runtime manifest is schema-validated and closed by default because
its upstream URLs/hashes have not been proven in this offline environment. A
release-approved ignored override unlocks installation. PowerShell accepts HTTPS
only, verifies SHA-256 before use, extracts into a sibling temporary directory,
atomically renames it, records a digest marker, and refuses an unexpected existing
destination.

The offline wheelhouse must exclude CTranslate2. Bootstrap explicitly installs
the official ROCm 4.8.1 wheel first and resolves pinned runtime requirements only
from the wheelhouse. Verification checks 64-bit Python 3.12, FFmpeg/FFprobe,
CTranslate2 version and HIP DLL/device visibility, Windows GPU name, and required
Large v3 files.
