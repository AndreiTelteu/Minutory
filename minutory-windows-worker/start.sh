#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ -x .venv/bin/python ]] || { echo 'Run ./bootstrap.sh first.'; exit 1; }
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export LD_LIBRARY_PATH="$PWD/libs/ctranslate2-hip/lib:$PWD/libs/ctranslate2-hip/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
rocm="${ROCM_PATH:-/opt/rocm}"
if [[ -d "$rocm/lib" ]]; then export LD_LIBRARY_PATH="$rocm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; fi
.venv/bin/python -m minutory_worker.runtime_verify
exec .venv/bin/python -m minutory_worker.gui.app "$@"
