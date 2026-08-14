from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Stage(StrEnum):
    PROBE = "probe"
    SOURCE = "source"
    WAV = "wav"
    TRANSCRIBE = "transcribe"
    DIARIZE = "diarize"
    MERGE = "merge"
    MEETING = "meeting"
    VIDEO_UPLOAD = "video_upload"
    AUDIO_UPLOAD = "audio_upload"
    TRANSCRIPT_UPLOAD = "transcript_upload"
    SPEAKERS_UPLOAD = "speakers_upload"
    FINAL_RECONCILE = "final_reconcile"


STAGE_ORDER = tuple(Stage)
STAGE_DEPENDENCIES: dict[Stage, tuple[Stage, ...]] = {
    Stage.PROBE: (),
    Stage.SOURCE: (Stage.PROBE,),
    Stage.WAV: (Stage.PROBE,),
    Stage.TRANSCRIBE: (Stage.WAV,),
    Stage.DIARIZE: (Stage.WAV,),
    Stage.MERGE: (Stage.TRANSCRIBE, Stage.DIARIZE),
    Stage.MEETING: (Stage.PROBE,),
    Stage.VIDEO_UPLOAD: (Stage.SOURCE, Stage.MEETING),
    Stage.AUDIO_UPLOAD: (Stage.WAV, Stage.MEETING),
    Stage.TRANSCRIPT_UPLOAD: (Stage.MERGE, Stage.MEETING),
    Stage.SPEAKERS_UPLOAD: (Stage.DIARIZE, Stage.MEETING),
    Stage.FINAL_RECONCILE: (
        Stage.VIDEO_UPLOAD,
        Stage.AUDIO_UPLOAD,
        Stage.TRANSCRIPT_UPLOAD,
        Stage.SPEAKERS_UPLOAD,
    ),
}

GPU_STAGES = (Stage.PROBE, Stage.SOURCE, Stage.WAV, Stage.TRANSCRIBE, Stage.DIARIZE)
CPU_STAGES: tuple[Stage, ...] = ()
IO_STAGES = (
    Stage.MEETING,
    Stage.VIDEO_UPLOAD,
    Stage.AUDIO_UPLOAD,
    Stage.TRANSCRIPT_UPLOAD,
    Stage.SPEAKERS_UPLOAD,
    Stage.FINAL_RECONCILE,
)

COMPRESSION_PRESETS = frozenset({"none", "nano", "micro", "compact", "balanced", "quality", "crf22", "crf26"})

SUPPORTED_LANGUAGES = frozenset({"ro", "en"})


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceIdentity:
    path: str
    size: int
    mtime_ns: int
    sha256: str | None = None

    @classmethod
    def from_path(cls, path: Path, *, hash_source: bool = False) -> SourceIdentity:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
        digest = stream_sha256(resolved) if hash_source else None
        return cls(str(resolved), stat.st_size, stat.st_mtime_ns, digest)


@dataclass
class WorkerItem:
    source: SourceIdentity
    title: str
    meeting_at: str | None = None
    client_id: int | None = None
    compression_preset: str = "crf22"
    language: str = "ro"
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title_manually_edited: bool = False
    meeting_at_manually_edited: bool = False
    duration_seconds: int | None = None
    probe_width: int | None = None
    probe_height: int | None = None
    probe_fps: float | None = None
    probe_bitrate: int | None = None
    selected_video_path: str | None = None
    wav_path: str | None = None
    transcript_path: str | None = None
    speakers_path: str | None = None
    selected_video_sha256: str | None = None
    audio_sha256: str | None = None
    transcript_sha256: str | None = None
    speakers_sha256: str | None = None
    selected_video_bytes: int | None = None
    audio_bytes: int | None = None
    transcript_bytes: int | None = None
    speakers_bytes: int | None = None
    server_meeting_id: int | None = None

    def __post_init__(self) -> None:
        parsed = uuid.UUID(self.item_id)
        if parsed.version != 4 or self.item_id != str(parsed):
            raise ValueError("item_id must be a canonical lowercase UUID v4.")
        if self.client_id is not None and self.client_id <= 0:
            raise ValueError("client_id must be positive.")
        if self.compression_preset not in COMPRESSION_PRESETS:
            raise ValueError(f"Unsupported compression preset {self.compression_preset!r}.")
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language {self.language!r}.")


def stream_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def dependent_stages(stage: Stage) -> set[Stage]:
    affected = {stage}
    changed = True
    while changed:
        changed = False
        for candidate, dependencies in STAGE_DEPENDENCIES.items():
            if candidate not in affected and any(dependency in affected for dependency in dependencies):
                affected.add(candidate)
                changed = True
    return affected
