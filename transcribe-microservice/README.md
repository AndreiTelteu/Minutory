
# Copyright. The entire code in this repository belogs to the contribuitors of [rishikanthc/Scriberr](https://github.com/rishikanthc/Scriberr)

# Transcribe Microservice (WhisperX + optional diarization/alignment)

This Dockerized CLI lets you run the existing transcribe.py as a standalone tool.

## Image build

- CPU build:
  docker build -t scriberr-local:latest transcribe-microservice

- CUDA build (requires a CUDA-capable host + nvidia-container-toolkit):
  docker build --build-arg WITH_CUDA=true -t scriberr-local:latest transcribe-microservice

## Basic usage

Mount an input video/audio as /input.mp4 and call the CLI:

- Explicit audio file:
  docker run --rm -v "$(pwd)/videoinput.mp4:/input.mp4:ro" scriberr-local:latest transcribe.py --audio-file /input.mp4

- Convenience: if you map to /input.mp4 and do NOT pass --audio-file, the wrapper injects it automatically:
  docker run --rm -v "$(pwd)/videoinput.mp4:/input.mp4:ro" scriberr-local:latest transcribe.py --model-size small --device cpu

Output is written inside the container unless you bind-mount a location. For example, to get transcript.json on the host:

  docker run --rm \
    -v "$(pwd)/videoinput.mp4:/input.mp4:ro" \
    -v "$(pwd):/out" \
    scriberr-local:latest \
    transcribe.py --audio-file /input.mp4 --output-file /out/transcript.json

## Environment

- HF_API_KEY: optional HuggingFace token that enables private models (needed for some pyannote diarization pipelines).

The container sets:
- HF_HUB_DISABLE_TELEMETRY=1
- TRUST_REMOTE_CODE=1

Models cache at /scriberr/models (bind mount it to reuse across runs):
  -v "$(pwd)/.models:/scriberr/models"

## CLI parameters

Taken directly from transcribe.py:

- --audio-file (str, required): Path to the audio/video file to transcribe. If omitted and /input.mp4 exists, the wrapper injects --audio-file /input.mp4 automatically.
- --model-size (str, default: small): Whisper model size (tiny, base, small, medium, large, large-v2).
- --language (str, optional): Force Whisper language (e.g., "en"). If omitted, Whisper attempts detection.
- --diarize (flag, default: false): Enable speaker diarization via pyannote.
- --align (flag, default: false): Run alignment of Whisper segments.
- --device (str, default: cpu): Device for inference ("cpu" or "cuda").
- --compute-type (str, default: int8): Compute type for WhisperX (e.g., "float16", "float32", "int8"). Fallback to float32 if float16 not supported is implemented.
- --output-file (str, default: transcript.json): Output JSON file path.
- --threads (int, default: 1): Number of threads used by torch for CPU inference.
- --models-dir (str, default: /scriberr/models): Directory used to download/cache models.
- --diarization-model (str, default: pyannote/speaker-diarization-3.1): Model used when --diarize is enabled.
- --batch_size (int, default: 16): Batch size during transcription.

## Notes on diarization

- For pyannote diarization pipelines, some models require an HF token. Export HF_API_KEY and pass it with -e:
  docker run --rm -e HF_API_KEY=xxxxx \
    -v "$(pwd)/videoinput.mp4:/input.mp4:ro" \
    scriberr-local:latest transcribe.py --diarize --audio-file /input.mp4

## GPU usage

Build with --build-arg WITH_CUDA=true and run with NVIDIA runtime:
  docker run --rm --gpus all \
    -v "$(pwd)/videoinput.mp4:/input.mp4:ro" \
    scriberr-local:latest \
    transcribe.py --device cuda --audio-file /input.mp4

