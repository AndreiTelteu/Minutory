# Stage 4 Windows GUI and bootstrap operations

## Release asset preparation

The repository cannot prove upstream Windows artifact hashes while offline, so
`manifests/runtime-assets.json` intentionally marks all five assets unresolved.
This is a release blocker, not a sample configuration: `bootstrap.ps1` exits
nonzero before downloading anything.

On a networked release workstation:

1. Select immutable, publisher-owned HTTPS artifacts for x86-64 Python 3.12.10,
   FFmpeg 7.1.1, the official CTranslate2 ROCm/HIP 4.8.1 CPython 3.12 Windows
   wheel, a complete Large v3 model snapshot, and an offline wheelhouse.
2. Independently verify every publisher checksum or hash the exact immutable
   object. Never copy a hash from an untrusted mirror.
3. Ensure the wheelhouse satisfies `requirements-runtime.txt` and contains no
   package named CTranslate2. The official ROCm wheel is the only allowed source.
4. Copy the tracked manifest to ignored
   `manifests/runtime-assets.local.json`, replace every null URL/hash, and change
   each status to `resolved`.
5. Run `bootstrap.ps1 -DryRun`, then bootstrap on a disposable clean Windows 11
   VM. Archive the approved local manifest in the private release system.

The Python and FFmpeg ZIPs must extract with their executable at
`libs/python/python.exe` and `libs/ffmpeg/bin/ffmpeg.exe`. The model archive must
place `model.bin`, `config.json`, and `tokenizer.json` directly under
`models/large-v3`.

## Operator workflow

Copy `.env.example` to `.env`; set only the application URL, bearer token, and
operator preferences. Launch with `start.bat`. Runtime/model/cache paths are
forced below the worker directory by `start.ps1`.

The queue supports MP4, MOV, AVI, WebM, MKV, and M4V. A recording can be added
only once by canonical path. Select a client and verify the parser-suggested title
and optional local meeting time. A DST-gap time is rejected visibly. Preset and
metadata edits are transactional and stop being available after meeting creation.

Use **Start / resume** for one item or **Start pending** for a batch. Batch items
are serialized; a second click cannot duplicate work. A failed stage shows a
stage-specific Retry label and continues through durable resume semantics. The
diagnostics panel is copyable and redacts API-token-derived transport messages.

**Cancel media command** applies only during compression and WAV extraction.
Transcription is intentionally not interrupted. Closing during transcription
keeps the application open with an explanation. During another active stage,
close asks before cancelling and waiting.

Items can be removed only before a server meeting exists and while no stage is
running. This refuses unsafe local deletion after remote history has been created.

## Verification and current limits

Linux/offline CI can test controller behavior, persistence, serialization,
cancellation, manifest planning, and launcher invariants. Qt smoke tests require
PySide6 and run with `QT_QPA_PLATFORM=offscreen`.

Still requiring Windows 11/RX 7900 XTX acceptance:

- exact asset URL/hash resolution and PowerShell `-DryRun`/`-Verify` execution;
- real PySide6 window construction and drag/drop on Windows;
- CTranslate2 ROCm 4.8.1 HIP DLL/device verification on gfx1100;
- AMF availability/fallback, Large v3 FP16 transcription, and teardown behavior;
- authenticated API artifact processing (reserved for Stage 5).

No PyInstaller bundle is configured yet. The managed runtime avoids embedding
multi-gigabyte models; packaging can be added after hardware acceptance.
