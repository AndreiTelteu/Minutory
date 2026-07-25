# Minutory transcription runtime

The transcription CLI is installed inside Minutory's Lerd custom container and exposes three lazy-loaded drivers with one normalized JSON output format.

## Drivers

| Driver | Model | Runtime |
|---|---|---|
| `parakeet` | NVIDIA Parakeet TDT 0.6B v3 | ONNX-ASR / CPU |
| `whisper` | OpenAI Whisper large-v3 | faster-whisper / CTranslate2 |
| `qwen` | Qwen/Qwen3-ASR-1.7B | qwen-asr / PyTorch |

All Hugging Face/model artifacts are cached under `storage/app/model`. They survive Lerd image rebuilds because the project is bind-mounted into the container.

## CLI

```bash
/opt/minutory-venv/bin/python transcribe-microservice/transcribe.py \
  --audio-file storage/app/public/meetings/1/91/audio.wav \
  --output-file storage/app/public/meetings/1/91/transcript.json \
  --driver whisper \
  --model-dir storage/app/model \
  --language ro \
  --device cpu \
  --compute-type auto
```

Important options:

- `--driver parakeet|whisper|qwen`
- `--model-dir`: persistent model/cache directory
- `--language`: defaults to `ro`; Qwen maps it to its canonical `Romanian` name
- `--device cpu|cuda`
- `--compute-type`: faster-whisper compute type; `auto` selects `int8` on CPU and `float16` on CUDA
- `--threads`: CPU thread count
- `--qwen-chunk-seconds`: Qwen segment size, default 30 seconds

The output file is replaced atomically only after a valid, non-empty transcript has been generated.

## Laravel configuration

The default driver is configured in `config/services.php`:

```dotenv
TRANSCRIBING_DRIVER=parakeet
TRANSCRIBING_MODEL_PATH=/home/andrei/minutory/storage/app/model
TRANSCRIBING_LANGUAGE=ro
TRANSCRIBING_DEVICE=cpu
TRANSCRIBING_COMPUTE_TYPE=auto
```

Queue a specific meeting for regeneration with another driver:

```bash
php artisan meeting:transcribe 91 whisper
php artisan meeting:transcribe 91 parakeet
php artisan meeting:transcribe 91 qwen
```

The existing database transcript remains available while the replacement is generated. Database rows are replaced in a transaction only after the new JSON passes validation.

## Runtime build

```bash
lerd check
lerd rebuild
```

The image uses Debian/glibc because CTranslate2 and PyTorch do not provide compatible Alpine/musl wheels for the previous Python 3.14 Lerd FPM image.
