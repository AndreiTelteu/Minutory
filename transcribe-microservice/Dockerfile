# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TRUST_REMOTE_CODE=1 \
    PYTHONWARNINGS=ignore

# ffmpeg is required by whisper/whisperx
RUN apt-get update -y && apt-get install -y --no-install-recommends \
      ffmpeg git ca-certificates curl tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what we need first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt

# Optional CUDA support toggle: default is CPU
ARG WITH_CUDA=false
# Ensure NumPy < 2.0 is installed before any dependency that might pull NumPy 2.x
# Then install torch according to the toggle for a more deterministic env
RUN set -eux; \
    pip install --no-cache-dir "numpy<2.0"; \
    if [ "$WITH_CUDA" = "true" ]; then \
      pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu118 torch torchvision torchaudio; \
    else \
      pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio; \
    fi

# Then the rest of Python deps
RUN pip install --no-cache-dir -r /app/requirements.txt

# Models/cache directories (bind-mount friendly)
RUN mkdir -p /scriberr/models /scriberr/temp /scriberr/uploads \
 && chmod -R 755 /scriberr

# Copy application code
COPY transcribe.py /app/transcribe.py
COPY diarize.py /app/diarize.py

# CLI shim so `transcribe.py` is directly runnable as in the requested UX
COPY bin/transcribe.py /usr/local/bin/transcribe.py

# Default command prints help. Users override with their own args or call `transcribe.py ...`
CMD ["transcribe.py", "--help"]

# Use tini as a minimal init to handle signals properly
ENTRYPOINT ["/usr/bin/tini", "--"]
