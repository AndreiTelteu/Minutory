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
   object. Compute each ZIP's deterministic installed-tree SHA-256 using the
   normalized layout validator. Never copy a hash from an untrusted mirror.
   For CTranslate2 4.8.1, upstream publishes
   `rocm-python-wheels-Windows.zip`, not a standalone wheel. GitHub reports and
   the downloaded release asset independently matched SHA-256
   `3a4936a4e76f27b9c0e4f32b06baf6378fe778d784adcb53cd3e159bd4d218b3`;
   its CPython 3.12 member is
   `temp-windows/ctranslate2-4.8.1-cp312-cp312-win_amd64.whl`. The tracked asset
   remains unresolved until its deterministic installed-tree digest is approved.
3. Ensure the wheelhouse satisfies `requirements-runtime.txt` and contains no
   package named CTranslate2. The official ROCm wheel is the only allowed source.
4. Confirm the Python archive is a full redistributable distribution with
   functional `python -m venv` and `python -m ensurepip`. The official embeddable
   ZIP is unsupported. Every ZIP must declare its safe top-level
   `source_subdir`; every asset must retain its required destination and expected
   files.
5. Copy the tracked manifest to ignored
   `manifests/runtime-assets.local.json`, replace every null URL, archive hash,
   and ZIP installed-tree hash, then change each status to `resolved`.
6. Run `bootstrap.ps1 -DryRun`, then bootstrap on a disposable clean Windows 11
   VM. Archive the approved local manifest in the private release system.

Archive roots are normalized by `source_subdir`. Required contents cover Python
launchers plus `venv`/`ensurepip`, FFmpeg/FFprobe, the exact ROCm wheel filename,
pinned wheelhouse inputs with no CTranslate2, and model/tokenizer/preprocessor
files. Safe extraction rejects traversal, absolute paths, symlink/reparse
entries, and duplicate/colliding targets.

## Operator workflow

Copy `.env.example` to `.env`; set only the application URL, bearer token, and
operator preferences. Launch with `start.bat`. Runtime/model/cache paths are
forced below the worker directory by `start.ps1`.

The queue supports MP4, MOV/QuickTime, AVI, and WebM, matching the Laravel Worker
API MIME contract. MKV and M4V are rejected before persistence. A recording can
be added only once by canonical path. Adding it schedules probe-only preflight;
**Preflight unprobed** handles restored items. Review duration, resolution, FPS,
the estimate, parser-suggested title, optional local meeting time, client, and
preset before starting. DST gaps are rejected visibly. Metadata and preset edits
are unavailable while scheduled/running and permanently after a meeting attempt.

Use **Start / resume** for one item or **Start pending** for a batch. Batch items
are serialized; a second click cannot duplicate work. A failed stage shows a
stage-specific Retry label and continues through durable resume semantics. The
diagnostics panel is copyable and redacts API-token-derived transport messages.
When an individual remote upload failed or reconciliation reset it, separate
**Retry video**, **Retry audio**, and **Retry transcript** actions appear. They
validate the local prerequisite, reconcile first, never replace a differing
server artifact, upload only the requested artifact, and finalize automatically
once all three artifacts match.

**Cancel media command** applies only during compression and WAV extraction.
Transcription is intentionally not interrupted. Closing during transcription
keeps the application open with an explanation. During another active stage,
close asks before cancelling and waiting.

Items can be removed only before a server meeting attempt and while neither
scheduled nor running. This refuses unsafe local deletion after remote history
may have been created.

Every launch first runs `bootstrap.ps1 -Verify`. The first
verification after installation, a legacy marker, or a detected file change
computes the complete installed-tree SHA-256. A successful verification stores a
per-file path, byte-count, and UTC last-write-tick snapshot in the asset marker.
Unchanged later launches compare that metadata instead of rereading the entire
Large v3 model; any difference forces a complete SHA-256 verification and marker
refresh. The expensive runtime check (`pip check`, CTranslate2/ROCm initialization,
GPU enumeration, and Windows video-controller lookup) runs after a bootstrap and
then at most once per local Windows calendar day, provided the venv runtime
fingerprint still matches. Full bootstrap builds dependencies in a fresh staging
venv, runs runtime verification, writes the manifest/requirements/schema
readiness marker only on success, and atomically promotes it. Failed staging is
removed while an earlier ready venv remains intact. The launcher forces offline
model resolution, so missing or modified model content cannot fall back to the
network.

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
