from __future__ import annotations

from .api import HttpxTransport, WorkerApiClient
from .config import WorkerConfig
from .diarization import SpeakerDiarizationService
from .media import MediaService, SubprocessRunner
from .orchestrator import Orchestrator
from .state import StateStore
from .whisper import FasterWhisperBackend, WhisperService


def build_orchestrator(config: WorkerConfig) -> Orchestrator:
    """Assemble production services without starting work or loading the ASR model."""
    local_model = config.model_dir / config.whisper_model
    local_diarization_model = config.model_dir / "pyannote-speaker-diarization-community-1"
    required_model_files = (
        "model.bin",
        "config.json",
        "tokenizer.json",
        "vocabulary.json",
        "preprocessor_config.json",
    )
    missing = [name for name in required_model_files if not (local_model / name).is_file()]
    if missing:
        raise RuntimeError(
            f"Verified local model {local_model} is incomplete (missing {', '.join(missing)}). "
            "Run bootstrap verification; network model downloads are disabled."
        )
    if not (local_diarization_model / "config.yaml").is_file():
        raise RuntimeError(
            f"Verified local SpeakerID model {local_diarization_model} is incomplete (missing config.yaml). "
            "Run bootstrap verification; network model downloads are disabled."
        )
    store = StateStore(config.state_db)
    media = MediaService(config.ffprobe_path, config.ffmpeg_path, SubprocessRunner())
    whisper = WhisperService(
        FasterWhisperBackend(
            local_model,
            model_name=config.whisper_model,
            beam_size=config.beam_size,
            batch_size=config.batch_size,
        ),
        language=config.language,
        vad_filter=config.vad_filter,
        vad_min_silence_ms=config.vad_min_silence_ms,
    )
    api = WorkerApiClient(
        config.api_base_url,
        config.api_token,
        HttpxTransport(),
        basic_auth_username=config.api_basic_auth_username,
        basic_auth_password=config.api_basic_auth_password,
        custom_header_key=config.api_custom_header_key,
        custom_header_value=config.api_custom_header_value,
        connect_timeout=config.connect_timeout,
        read_timeout=config.read_timeout,
        upload_timeout=config.upload_timeout,
    )
    return Orchestrator(
        store,
        media,
        whisper,
        api,
        config.work_dir,
        diarization=SpeakerDiarizationService(local_diarization_model),
        video_codec=config.video_codec,
        fallback_video_codec=config.fallback_video_codec,
    )
