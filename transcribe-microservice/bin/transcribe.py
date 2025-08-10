#!/usr/bin/env bash
set -euo pipefail

inject_audio=""
for arg in "$@"; do
  if [[ "$arg" == "--audio-file" ]]; then
    inject_audio="no"
    break
  fi
done

if [[ -z "${inject_audio}" && -f "/input.mp4" ]]; then
  set -- --audio-file /input.mp4 "$@"
fi

# Respect HF_API_KEY if provided in the environment
exec python /app/transcribe.py "$@"
