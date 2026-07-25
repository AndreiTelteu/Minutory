from __future__ import annotations

from .api import HttpxTransport, WorkerApiClient
from .config import WorkerConfig
from .media import MediaService, SubprocessRunner
from .orchestrator import Orchestrator
from .state import StateStore
from .whisper import FasterWhisperBackend, WhisperService


def build_orchestrator(config: WorkerConfig) -> Orchestrator:
    """Assemble production services without starting work or loading the ASR model."""
    store = StateStore(config.state_db)
    media = MediaService(config.ffprobe_path, config.ffmpeg_path, SubprocessRunner())
    local_model = config.model_dir / config.whisper_model
    whisper = WhisperService(
        FasterWhisperBackend(
            config.whisper_model,
            model_path=local_model if local_model.is_dir() else None,
            download_root=config.model_dir,
        ),
        language=config.language,
        vad_filter=config.vad_filter,
        vad_min_silence_ms=config.vad_min_silence_ms,
    )
    api = WorkerApiClient(
        config.api_base_url,
        config.api_token,
        HttpxTransport(),
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
        video_codec=config.video_codec,
        fallback_video_codec=config.fallback_video_codec,
    )
