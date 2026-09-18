#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ -x .venv/bin/python ]] || { echo 'Run bootstrap.sh first.'; exit 1; }
exec .venv/bin/python -m minutory_worker.setup_models "$@"
