# Linux worker

The same Python/Qt worker runs on Linux. Laravel Worker API, SQLite queue, artifact
hashes, reconciliation and retries are shared with Windows. Windows PowerShell
bootstrap and its verified runtime manifest remain Windows-specific.

## Install and start

Install `uv`, system FFmpeg, Git, CMake, Ninja and AMD ROCm development libraries
(including hipBLAS, hipRAND, rocPRIM, rocThrust and hipCUB). The tested target is
RX 7900 XTX (`gfx1100`) with ROCm 7.2 on CachyOS. Bootstrap uses Python 3.12,
while the isolated model exporter uses Python 3.11 and CPU PyTorch.

Accept both gated model agreements on Hugging Face:

- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

Copy `.env.linux.example` to `.env` if needed, then set
`MINUTORY_DIARIZATION_TOKEN` to a token with access to those models and configure
your Worker API URL/authentication. `MINUTORY_API_TOKEN` is sent in `X-Token`
and must match Laravel’s `WORKER_API_TOKEN`; Basic credentials use `Authorization`
independently for the proxy. Never put tokens in shell arguments.

```bash
./bootstrap.sh --hip
./start.sh
```

Bootstrap installs dependencies, builds pinned CTranslate2 4.8.2 for HIP, downloads
Whisper Large v3 (~3 GB), and exports the pinned speaker models to ONNX. The HIP
build updates only `MINUTORY_ASR_DEVICE=cuda` and
`MINUTORY_ASR_COMPUTE_TYPE=float16` in `.env`. Existing models are reused.
The `cuda` device name is also CTranslate2's name for HIP.

Model preparation is explicitly online. Normal startup remains offline and checks
the runtime and models before opening Qt. Model installation uses staging and
preserves previous bundles until the new files have passed validation. Speaker
export logs redact the token; the token is passed through the environment rather
than process command-line arguments. Gated downloads require accepted terms.

To retry just one setup step:

```bash
./build-hip.sh
./setup-models.sh --whisper-only
./setup-models.sh --speakers-only
```

Run `./bootstrap.sh --skip-models` for dependency-only developer setup. Without
`--hip`, bootstrap does not build CTranslate2 and the stock wheel supports CPU or
NVIDIA CUDA. Existing HIP installations are preserved. Windows installation and
its manifest verification remain separate.

Build artifacts stay in ignored `cache/`, `libs/`, and `.venv/`. No system-wide
CTranslate2 install or sudo is required. Set `ROCM_PATH` for a custom ROCm root,
`MINUTORY_HIP_ARCH` for a different AMD architecture (default `gfx1100`), or
`MINUTORY_BUILD_JOBS` to control build parallelism (default 6). Startup adds local
CTranslate2 and ROCm library paths. ONNX diarization runs on CPU concurrently with
ASR; DirectML remains available on Windows. For upstream build details, see
https://opennmt.net/CTranslate2/installation.html.

## Tests

```bash
uv pip install --python .venv/bin/python -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/mypy src/minutory_worker
```

For native desktop testing without model downloads or server writes:

```bash
.venv/bin/python tests/manual/linux_gui.py /tmp/minutory-linux-smoke
```

This fixture uses the production Qt interface, SQLite and real FFmpeg, with one
fake client. ASR and server writes are disabled explicitly. It is not a production
launcher or proof of GPU transcription. Add a real video through the file chooser,
edit its title, run **Preflight unprobed**, and restart to verify queue persistence.
