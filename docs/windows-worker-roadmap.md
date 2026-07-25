# Minutory Windows Worker Roadmap

## Goal

Keep the existing Linux/Lerd transcription runtime unchanged and add a native Windows ingestion worker optimized for AMD Radeon RX 7900 XTX. The worker creates meetings through an authenticated API, uploads video/audio/transcript artifacts independently, and imports the normalized transcript without starting server-side transcription.

## Non-negotiable constraints

- Do not change `transcribe-microservice/` behavior or the Linux driver contract.
- Windows sends `start_transcript_server=false`; other API clients may send `true`.
- Bearer secrets exist only in ignored `.env` files; tracked examples contain placeholders.
- Meeting creation is separate from video, WAV, and transcript uploads.
- Every local stage and remote artifact is independently retryable and persisted locally.
- Existing known-good transcript rows and `transcript.json` survive invalid replacement attempts.
- Uploaded filenames never determine server filesystem paths.
- Datetimes cross the API as offset-bearing ISO-8601 and are stored by Laravel as UTC.
- Runtime assets and generated data under `minutory-windows-worker/libs`, state, logs, and work directories are ignored.

## API v1 contract

All endpoints are under `/api/v1/worker` and protected by a constant-time Bearer-token middleware plus throttling.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/clients` | Ordered `{id,name}` client list |
| `POST` | `/meetings` | Idempotently create/recover a metadata-only meeting |
| `GET` | `/meetings/{meeting}` | Reconcile meeting and artifact state |
| `POST` | `/meetings/{meeting}/artifacts/video` | Upload/retry video independently |
| `POST` | `/meetings/{meeting}/artifacts/audio` | Upload/retry mono 16 kHz PCM WAV independently |
| `POST` | `/meetings/{meeting}/artifacts/transcript` | Validate/store normalized JSON, atomically replace DB rows, mark completed |

Multipart uploads use `POST`; PHP does not reliably populate files for multipart `PUT`.

### Create meeting

```json
{
  "worker_item_id": "uuid-v4",
  "client_id": 52,
  "title": "Synevo Prezentare Modificari Design Rezultate Web",
  "meeting_at": "2026-07-10T13:03:47+03:00",
  "duration_seconds": 3777,
  "start_transcript_server": false
}
```

- First create returns `201`; an identical UUID replay returns `200` and the same meeting.
- Conflicting metadata for the same UUID returns `409`.
- The start flag is persisted because metadata creation happens before video upload.
- `true` dispatches the existing Linux job exactly once only after video upload succeeds.
- `false` never dispatches Linux ASR; transcript upload completes the meeting.
- `true` is accepted only when Laravel uses the database queue on the application
  database connection with `after_commit=false`, so queue insertion and the
  durable dispatch marker commit in one transaction. External or deferred queue
  backends are rejected for this API path.

### Durable idempotency

Use a dedicated `worker_ingestions` table linked one-to-one to meetings:

- unique `worker_item_id` UUID;
- `start_transcript_server` boolean;
- SHA-256, byte size, and uploaded timestamp for video/audio/transcript;
- server-transcription dispatch timestamp.

Rules:

1. Same artifact hash returns `200 already_uploaded`.
2. Different hash returns `409` unless `replace=true` is explicitly supplied.
3. Server computes hashes; client hashes are hints only.
4. Artifact files are written to a temporary file and atomically renamed.
5. Transcript JSON is fully validated before filesystem or DB replacement.
6. Worker persists UUID, meeting ID, hashes, and completed stage after every transition.

## Shared transcript import contract

Extract DB import behavior from `TranscribeMeetingJob` into `App\Services\TranscriptImporter`. The Linux job delegates to it without changing the Python CLI or artifact paths.

Validation:

- JSON object with normalized top-level fields and `segments` array;
- configured maximum bytes and at most 100,000 segments;
- finite numeric `start`/`end`, `0 <= start <= end`;
- trimmed non-empty bounded text;
- nullable/bounded speaker and confidence;
- deterministic segment order;
- transactionally replace rows only after complete validation;
- preserve the old JSON and rows on any failure.

## Meeting date and filename parsing

Add nullable indexed `meetings.meeting_at`. Web create/update accepts it and UI displays `meeting_at ?? uploaded_at` while retaining upload time where useful.

Parser example:

```text
2026-07-10 13-03-47 Synevo Prezentare Modificari Design Rezultate Web Fast 1080p30.mp4
```

Produces:

- local datetime `2026-07-10 13:03:47`;
- title `Synevo Prezentare Modificari Design Rezultate Web`.

Only terminal recording profiles are stripped, case-insensitively, including forms such as `Fast 1080p30`, `Fast 1080p 30 FPS`, and equivalent 720p/1440p/2160p values. Date/title suggestions do not overwrite manually edited fields.

## Windows worker architecture

`minutory-windows-worker/` uses Python 3.12, PySide6/Qt 6, `httpx`, `python-dotenv`, and a persistent SQLite state store under `%LOCALAPPDATA%\Minutory Worker`.

Each dropped file is an independent row/card with:

- source metadata and probe status;
- compression selector;
- estimated final size;
- client selector;
- optional date/time;
- editable suggested title;
- per-stage progress/error;
- retry current stage and retry individual artifact actions.

Compression presets preserve source resolution and FPS by omitting scale/FPS filters:

- None: original video;
- Compact: 2.5 Mbps video + 128 kbps audio;
- Balanced: 5 Mbps + 160 kbps;
- Quality: 8 Mbps + 192 kbps.

Estimated size is `duration × (video bitrate + audio bitrate) / 8 × 1.02`. Prefer FFmpeg `h264_amf` when available, with explicit `libx264` fallback.

Pipeline:

1. probe;
2. compress or retain source;
3. extract PCM s16le mono 16 kHz WAV;
4. run local faster-whisper Large v3;
5. normalize existing JSON contract;
6. create/recover meeting;
7. upload video;
8. upload audio;
9. upload transcript/import DB;
10. reconcile and complete.

A failed API stage never reruns compression or ASR.

## AMD runtime and bootstrap

Primary backend: `faster-whisper` with the official CTranslate2 ROCm Windows wheel.

- RX 7900 XTX is RDNA3 `gfx1100`, included in official ROCm wheels.
- Pin CTranslate2 ROCm 4.8.1 initially and use `device="cuda"` (CTranslate2 API naming) with `compute_type="float16"`.
- Keep an `AsrBackend` interface and CPU fallback.
- Account for the open Windows/gfx1100 model-destruction deadlock by keeping the model loaded in a persistent worker process and supervising shutdown.
- Benchmark batch sizes 1/8/16 on the real machine before choosing the production default.

Tracked `manifests/runtime-assets.json` records URL, version, size, and SHA-256. Bootstrap downloads resumably over HTTPS and verifies checksums for:

- FFmpeg/FFprobe;
- managed Python/venv dependencies;
- CTranslate2 ROCm Windows wheel/runtime packages;
- Whisper Large v3 model.

`start.bat` invokes PowerShell bootstrap when required, then launches the GUI. Package as PyInstaller `onedir`; an installer can be added after clean-Windows acceptance.

## Staged delivery

### Stage 0 — Plan and baseline

- [x] Inspect repository and existing Linux contract.
- [x] Freeze API/idempotency/runtime architecture in this roadmap.
- [x] Commit and push the roadmap.

Acceptance: completed in `5381ab5`; clean baseline and an authoritative plan were pushed.

### Stage 1 — Laravel schema, transcript service, worker API

- [x] Add nullable `meeting_at` and metadata-first nullable `video_path`.
- [x] Add `worker_ingestions` durable idempotency table/model.
- [x] Extract and test `TranscriptImporter`; preserve Linux behavior.
- [x] Register `routes/api.php`, token middleware, throttles, requests/controllers.
- [x] Implement client list, meeting create/reconcile, three artifact endpoints.
- [x] Add configuration and `.env.example` placeholders.
- [x] Verify `start_transcript_server=false/true` dispatch semantics.

Acceptance: 48 Stage 1 tests / 253 assertions pass; migrations and rollback pass on isolated SQLite and MySQL databases; Pint, route inspection, and diff checks pass. The two unrelated pre-existing transcription test failures remain documented and unchanged.

### Stage 2 — Laravel/Vue meeting datetime UX

- [x] Add create/update datetime validation and persistence.
- [x] Add deterministic TypeScript filename parser and unit tests.
- [x] Add create form `datetime-local` and manual-edit preservation.
- [x] Display/filter/sort actual meeting time appropriately.
- [x] Build/typecheck and visually verify live UI.

Acceptance: 9 frontend parser/ownership tests and 63 focused Pest tests / 458 assertions pass; typecheck, ESLint, production build, and Pint pass. The live create form was verified at the public URL with the required filename, manual-edit preservation, clean console, and no visible layout defects.

### Stage 3 — Windows worker core

- [ ] Create package layout, configuration, filename parser, domain model, SQLite state.
- [ ] Implement API client and independent/reconcilable stage machine.
- [ ] Implement FFprobe, compression presets/estimate, WAV extraction, hashing.
- [ ] Implement faster-whisper ROCm backend abstraction and normalized JSON.
- [ ] Add unit/integration tests using fake binaries/API transport.

Acceptance: Linux-runnable non-GUI tests pass; no runtime binaries/models tracked.

### Stage 4 — Windows GUI and bootstrap

- [ ] Implement dark PySide6 multi-file drag/drop GUI.
- [ ] Add editable per-item controls, progress, errors, retry actions.
- [ ] Add runtime manifest, verified bootstrap, `start.bat`/PowerShell launchers.
- [ ] Add packaging configuration and operator documentation.

Acceptance: GUI modules import, headless Qt smoke test passes where possible, bootstrap dry-run/manifest tests pass, and Windows-only checks are explicitly documented.

### Stage 5 — Integration and Windows acceptance

- [ ] Apply migrations and set a generated local Bearer token without committing it.
- [ ] Exercise authenticated API create/upload/retry/import against the live container.
- [ ] Verify Linux web upload/transcription regression behavior.
- [ ] On Windows 11 + RX 7900 XTX, install runtime and benchmark Large v3 FP16.
- [ ] Process one real multi-file batch and verify server artifacts/DB/UI.
- [ ] Complete independent review and exactly one resumed implementation feedback pass per stage.

Acceptance: real artifacts and timings are recorded; anything requiring unavailable Windows hardware remains explicitly unverified, never claimed as passing.
