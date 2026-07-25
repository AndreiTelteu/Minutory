# Stage 3 operator and developer notes

## What can be exercised on Linux

- configuration parsing and token redaction;
- filename suggestions and manual ownership;
- SQLite migration, locking, crash recovery, invalidation, and resume;
- concurrent read-only diagnostics while a writer owns state;
- FFprobe parsing, FFmpeg command construction, and encoded-output validation;
- WAV format validation, streamed hashing, and atomic rollback;
- transcript normalization using an injected ASR backend;
- the full pipeline using fake media, API, and ASR services.

No test contacts Laravel or a package/model host.

## Windows-only work intentionally deferred

Stage 4 must install and verify the CTranslate2 ROCm 4.8.1 wheel/runtime, FFmpeg,
and Large v3 model; implement runtime manifests and checksums; add PySide6,
bootstrap and packaging; and supervise persistent-model shutdown. Stage 5 must
validate Windows 11 with the RX 7900 XTX (`gfx1100`), benchmark batch sizes, test
AMF availability/fallback, and run real artifact uploads against an explicitly
configured test instance.

Until those stages, the default AMF command is production-shaped but not claimed
as hardware-verified. A failed AMF command is retried once with the explicitly
configured `libx264` fallback. The diagnostic retains both encoder failures if
neither works.

## Safe operation

- Keep `.env`, state, work, logs, models, runtimes, binaries, wheels, and caches
  under ignored worker-local directories.
- Do not reuse a UUID for different canonical metadata.
- Use HTTPS for every non-loopback API URL. Plain HTTP deliberately fails closed.
- Treat artifact hash conflicts as an operator decision; do not automatically
  replace known-good server files.
- If the source or compression preset changes after meeting creation, create a
  new worker item. Existing server history is never repurposed.
- Completion means the final reconciliation stage confirmed video, audio, and
  transcript hashes and sizes remotely; local upload flags alone are insufficient.
- The Worker API token is mandatory at runtime. Documentation and screenshots
  must show `[REDACTED]`.
