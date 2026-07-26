# Pipeline Optimization Plan

Status: proposed · Last updated: 2026-07-26

## Current Architecture

`ProcessingCoordinator` runs a single execution lane (`ThreadPoolExecutor(max_workers=1)`).
Every queue item passes through the stages strictly sequentially:

```
probe → source (ffmpeg compress) → wav (ffmpeg extract) → transcribe (GPU)
      → meeting (API) → video_upload → audio_upload → transcript_upload → final_reconcile
```

Resource profile per stage:

| Stage | Bound by | Typical duration (43 min 1080p meeting) |
|---|---|---|
| probe | disk | ~1 s |
| source | CPU / GPU AMF encode | 1–5 min (0 if preset `none`) |
| wav | CPU / disk | ~30–60 s |
| transcribe | **GPU (ROCm/HIP)** | ~3–4 min (large-v3, ~15x realtime) |
| meeting + uploads + reconcile | **network** | 1–3 min (300 MB video + 84 MB wav) |

Key observation: the three big stages use **disjoint resources** (GPU, CPU, network),
so the GPU sits idle during uploads and the network sits idle during transcription.
Serial per-item time ≈ 8–12 min; overlapped throughput could approach `max(GPU, IO)` ≈ 4–5 min.

## Proposals (ordered by value / effort)

### P1 — Dual-lane pipeline (GPU lane + IO lane)

Split the coordinator into two independent lanes:

- **GPU lane (sequential):** `source → wav → transcribe` per item.
- **IO lane (background, 1–2 workers):** `meeting → video/audio/transcript upload → final_reconcile`.

As soon as item N finishes `transcribe`, the GPU lane starts item N+1 while item N's
uploads proceed in the background.

- Expected gain: ~2x throughput on multi-item batches.
- Files: `presentation.py` (`ProcessingCoordinator`), `orchestrator.py` (stage ordering
  already per-item in SQLite, so the state machine needs no change).
- The coordinator currently tracks a single `_current_item` / `_current_stage`; must
  become per-lane. `transcription_active`, `cancel_current_media`, and the closeEvent
  guard (CTranslate2/HIP teardown deadlock) need rework for two lanes.
- GUI events are already keyed by `item_id`; per-card progress keeps working.

### P2 — Eager WAV extraction at drag & drop

Extract `audio.wav` directly from the source file as soon as the item is added
(alongside the existing preflight probe). The compression preset only affects the
video artifact, so the WAV is valid regardless of later preset changes.

- Expected gain: saves 30–60 s per item; transcription can start immediately.
- Implementation: extend preflight (`orchestrator.preflight` / coordinator `preflight`)
  to also run the WAV stage; mark `Stage.WAV` succeeded before the main pipeline.
- Cleanup: when an item is removed, its `work/{item_id}/` folder should be deleted
  (currently orphaned files remain — same fix covers eager WAV leftovers).

### P3 — Switch model to `large-v3-turbo`

`large-v3-turbo` is ~6–8x faster than `large-v3` with a minor quality drop and is
multilingual (works for Romanian).

- Expected gain: possibly the largest single one; transcription drops from ~3–4 min
  to ~30–60 s per 43 min meeting.
- Cost: one new model download (~1.6 GB), plus bootstrap/resolve-assets manifest
  entries for the new snapshot (`models/turbo`).
- Must validate transcript quality on a real Romanian meeting before switching
  permanently. Keep `large-v3` available via config.

### P4 — `beam_size=1` (greedy decoding)

faster-whisper defaults to `beam_size=5`. Greedy decoding is ~2x faster; for meeting
dictation with large-v3/turbo the quality loss is small.

- Make it a config/env knob (`MINUTORY_BEAM_SIZE`, default 5 → try 1).
- File: `whisper.py` (`FasterWhisperBackend.transcribe` call).

### P5 — Batched inference (`BatchedInferencePipeline`)

faster-whisper's batched pipeline (`batch_size=8/16`) can give 2–4x on GPU.

- Risk: higher VRAM use and unknown stability on the ROCm stack (already fragile —
  see the cuBLAS/ROCm 6 vs 7 incident). Test in isolation before adopting.
- Incompatible with some VAD edge cases historically; verify.

### P6 — Smaller/faster uploads (optional, server-side)

- Upload FLAC/Opus instead of raw WAV (~50–60% smaller; lossless FLAC preferred).
  Requires server MIME/validation changes (`config/services.php` worker artifacts).
- Preset `none` skips re-encode entirely (fastest local path, largest upload) —
  already supported.

## Risks and Constraints

- **Single model instance in VRAM.** Parallelism is between items, never two
  transcriptions at once — two large-v3 instances would contend for VRAM and run
  slower, plus CTranslate2/HIP stability concerns.
- **GPU contention.** AMF encode (`source`) and HIP transcribe share the GPU; expect
  a small slowdown when overlapped. Measure; if significant, serialize `source`
  before `transcribe` starts on the next item (still overlaps uploads).
- **Coordinator refactor risk.** Cancel/close semantics (`transcription_active`,
  the CT2 teardown deadlock workaround in `closeEvent`) must remain correct with
  two lanes. `close()` must wait for the GPU lane while allowing IO lane to finish.
- **Failure isolation.** Per-item stage state lives in SQLite and is already
  independent; a failure on item N+1's GPU lane must not cancel item N's uploads.
- **API rate limits.** `worker.throttle` default 60/min — fine for 1–2 concurrent
  upload lanes.
- **Disk space.** Eager WAV adds ~2 MB/min per queued item before processing starts;
  negligible, but removal cleanup (P2) becomes mandatory.
- **turbo quality.** Unvalidated on Romanian speech; needs an A/B check on a real
  recording before default.

## Phased Rollout

1. **Phase 1 (low risk, quick):** P2 eager WAV + work-folder cleanup on remove;
   P4 beam_size knob. No architecture change.
2. **Phase 2 (measure):** P3 turbo model download + quality check; optionally P5
   batched inference experiment on the bench clip.
3. **Phase 3 (architecture):** P1 dual-lane coordinator with per-lane state,
   updated close/cancel logic, and GUI status per lane.

## Benchmarks to Capture

Before/after each phase, record on a fixed 43 min 1080p clip:

- wall time per stage (already in `transcript.json` runtime for transcribe),
- end-to-end per-item time,
- batch throughput (3 items),
- GPU utilization / VRAM during overlap.
