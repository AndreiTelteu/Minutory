#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
build_hip=false
models=true
for arg in "$@"; do
    case "$arg" in
        --hip) build_hip=true ;;
        --skip-models) models=false ;;
        *) echo 'Usage: ./bootstrap.sh [--hip] [--skip-models]'; exit 2 ;;
    esac
done
command -v uv >/dev/null || { echo 'Install uv: https://docs.astral.sh/uv/getting-started/installation/'; exit 1; }
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo 'Install FFmpeg using your Linux package manager.'; exit 1; }
if [[ ! -x .venv/bin/python ]]; then uv venv --python 3.12 .venv; fi
# Preserve any locally installed HIP CTranslate2 wheel; stock CTranslate2 supports CPU/NVIDIA only.
uv pip install --python .venv/bin/python -r requirements-linux.txt -e .
if [[ ! -f .env ]]; then cp .env.linux.example .env; fi
if "$build_hip"; then ./build-hip.sh; fi
if "$models"; then ./setup-models.sh; fi
printf '%s\n' 'Setup complete. Configure API authentication in .env and run ./start.sh.'
