from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from .config import REDACTED, redact_text, validate_api_base_url
from .domain import WorkerItem


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def json(self) -> Any:
        return json.loads(self.content)


@dataclass(frozen=True)
class RequestTimeout:
    connect: float
    read: float


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object] | None,
        files: Mapping[str, tuple[str, Any, str]] | None,
        data: Mapping[str, str] | None,
        timeout: RequestTimeout,
    ) -> TransportResponse: ...


class TransportFailure(RuntimeError):
    pass


class HttpxTransport:
    def __init__(self, client: Any | None = None) -> None:
        import httpx

        self._httpx = httpx
        self._client = client or httpx.Client(follow_redirects=False)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object] | None,
        files: Mapping[str, tuple[str, Any, str]] | None,
        data: Mapping[str, str] | None,
        timeout: RequestTimeout,
    ) -> TransportResponse:
        try:
            response = self._client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                files=files,
                data=data,
                timeout=self._httpx.Timeout(timeout.read, connect=timeout.connect),
            )
        except Exception:
            # Transport exception messages and causes may echo request headers. Discard
            # both at the first boundary so no bearer token can enter diagnostics.
            raise TransportFailure("The HTTP transport failed.") from None
        return TransportResponse(response.status_code, response.headers, response.content)


class ApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        status: int | None,
        *,
        transient: bool,
        retry_after: float | None = None,
        details: object = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.transient = transient
        self.retry_after = retry_after
        self.details = details

    def __repr__(self) -> str:
        return (
            f"ApiError(code={self.code!r}, status={self.status!r}, transient={self.transient!r}, "
            f"message={str(self)!r})"
        )


@dataclass(frozen=True)
class ArtifactState:
    uploaded: bool
    sha256: str | None
    bytes: int | None


@dataclass(frozen=True)
class MeetingState:
    id: int
    worker_item_id: str
    client_id: int
    title: str
    meeting_at: str | None
    duration_seconds: int | None
    start_transcript_server: bool
    artifacts: Mapping[str, ArtifactState]


@dataclass(frozen=True)
class ArtifactUploadResult:
    state: str
    sha256: str
    bytes: int


SHA256 = re.compile(r"^[0-9a-f]{64}$")
OFFSET_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")


class WorkerApiClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        transport: Transport,
        *,
        connect_timeout: float = 10,
        read_timeout: float = 120,
        upload_timeout: float = 3600,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not token:
            raise ValueError("Bearer token is required.")
        self._base_url = f"{validate_api_base_url(base_url)}/api/v1/worker"
        self._token = token
        self._transport = transport
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._upload_timeout = upload_timeout
        self._max_attempts = max_attempts
        self._sleeper = sleeper

    def __repr__(self) -> str:
        return f"WorkerApiClient(base_url={self._base_url!r}, token={REDACTED!r})"

    def list_clients(self) -> list[dict[str, object]]:
        data = self._request("GET", "/clients")
        result = data.get("data")
        if not isinstance(result, list):
            raise ApiError(
                "invalid_response", "Server returned an invalid client list.", None, transient=False
            )
        return result

    def create_meeting(self, item: WorkerItem) -> MeetingState:
        if item.client_id is None:
            raise ValueError("A client must be selected before meeting creation.")
        payload: dict[str, object] = {
            "worker_item_id": item.item_id,
            "client_id": item.client_id,
            "title": item.title,
            "meeting_at": item.meeting_at,
            "duration_seconds": item.duration_seconds,
            "language": item.language,
            "start_transcript_server": False,
        }
        response = self._request("POST", "/meetings", json_body=payload)
        meeting = self._parse_meeting(response, require_artifacts=False)
        self._validate_created_meeting(meeting, item)
        return meeting

    def reconcile(self, meeting_id: int) -> MeetingState:
        response = self._request("GET", f"/meetings/{meeting_id}")
        meeting = self._parse_meeting(response, require_artifacts=True)
        if meeting.id != meeting_id:
            raise self._invalid_response("Server returned a different meeting ID.")
        return meeting

    def _parse_meeting(
        self,
        response: Mapping[str, object],
        *,
        require_artifacts: bool,
    ) -> MeetingState:
        data = response.get("data")
        if not isinstance(data, dict):
            raise self._invalid_response("Server returned invalid meeting metadata.")
        meeting_id = _positive_int(data.get("id"))
        worker_item_id = _canonical_uuid4(data.get("worker_item_id"))
        client_id = _positive_int(data.get("client_id"))
        title = data.get("title")
        if not isinstance(title, str) or not title or len(title) > 255:
            raise self._invalid_response("Server returned invalid meeting title.")
        meeting_at = data.get("meeting_at")
        if meeting_at is not None:
            if not isinstance(meeting_at, str):
                raise self._invalid_response("Server returned invalid meeting time.")
            _parse_offset_datetime(meeting_at)
        duration_seconds = data.get("duration_seconds")
        if duration_seconds is not None and (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, int)
            or duration_seconds < 0
        ):
            raise self._invalid_response("Server returned invalid meeting duration.")
        start_transcript_server = data.get("start_transcript_server")
        if not isinstance(start_transcript_server, bool):
            raise self._invalid_response("Server omitted transcription ownership.")

        artifacts: dict[str, ArtifactState] = {}
        raw_artifacts = data.get("artifacts")
        if require_artifacts and not isinstance(raw_artifacts, dict):
            raise self._invalid_response("Server returned invalid reconciliation state.")
        if isinstance(raw_artifacts, dict):
            for name in ("video", "audio", "transcript"):
                artifact = raw_artifacts.get(name)
                if not isinstance(artifact, dict):
                    raise self._invalid_response(f"Server omitted {name} state.")
                uploaded = artifact.get("uploaded")
                digest = artifact.get("sha256")
                byte_count = artifact.get("bytes")
                if not isinstance(uploaded, bool):
                    raise self._invalid_response(f"Server returned invalid {name} upload state.")
                if digest is not None and (not isinstance(digest, str) or SHA256.fullmatch(digest) is None):
                    raise self._invalid_response(f"Server returned invalid {name} hash.")
                if byte_count is not None and (
                    isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0
                ):
                    raise self._invalid_response(f"Server returned invalid {name} size.")
                if uploaded and (digest is None or byte_count is None):
                    raise self._invalid_response(f"Server returned incomplete {name} state.")
                artifacts[name] = ArtifactState(uploaded, digest, byte_count)
        return MeetingState(
            id=meeting_id,
            worker_item_id=worker_item_id,
            client_id=client_id,
            title=title,
            meeting_at=meeting_at,
            duration_seconds=duration_seconds,
            start_transcript_server=start_transcript_server,
            artifacts=MappingProxyType(artifacts),
        )

    def _validate_created_meeting(self, meeting: MeetingState, item: WorkerItem) -> None:
        mismatched = (
            meeting.worker_item_id != item.item_id
            or meeting.client_id != item.client_id
            or meeting.title != item.title
            or meeting.duration_seconds != item.duration_seconds
            or not _same_instant(meeting.meeting_at, item.meeting_at)
        )
        if mismatched:
            raise self._invalid_response("Server meeting metadata does not match the requested item.")
        if meeting.start_transcript_server:
            raise self._invalid_response("Server meeting is not configured for local transcription.")

    def upload_artifact(
        self,
        meeting_id: int,
        artifact: str,
        path: Path,
        *,
        replace: bool = False,
    ) -> ArtifactUploadResult:
        if artifact not in {"video", "audio", "transcript"}:
            raise ValueError(f"Unsupported artifact {artifact}.")
        media_types = {
            "audio": "audio/wav",
            "transcript": "application/json",
        }
        video_media_types = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".webm": "video/webm",
        }
        media_type = (
            video_media_types.get(path.suffix.lower(), "application/octet-stream")
            if artifact == "video"
            else media_types[artifact]
        )
        with path.open("rb") as stream:
            response = self._request(
                "POST",
                f"/meetings/{meeting_id}/artifacts/{artifact}",
                files={"file": (path.name, stream, media_type)},
                data={"replace": "true"} if replace else None,
                timeout=self._upload_timeout,
                retryable=True,
            )
        result = response.get("data")
        if not isinstance(result, dict) or result.get("state") not in {"uploaded", "already_uploaded"}:
            raise self._invalid_response("Server returned invalid artifact state.")
        digest = result.get("sha256")
        byte_count = result.get("bytes")
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise self._invalid_response("Server returned an invalid artifact hash.")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
            raise self._invalid_response("Server returned an invalid artifact size.")
        return ArtifactUploadResult(str(result["state"]), digest, byte_count)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, object] | None = None,
        files: Mapping[str, tuple[str, Any, str]] | None = None,
        data: Mapping[str, str] | None = None,
        timeout: float | None = None,
        retryable: bool = True,
    ) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        last_error: ApiError | None = None
        for attempt in range(1, self._max_attempts + 1):
            if files:
                for _, stream, _ in files.values():
                    stream.seek(0)
            try:
                response = self._transport.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    json_body=json_body,
                    files=files,
                    data=data,
                    timeout=RequestTimeout(
                        connect=self._connect_timeout,
                        read=timeout or self._read_timeout,
                    ),
                )
                if 200 <= response.status_code < 300:
                    parsed = response.json()
                    if not isinstance(parsed, dict):
                        raise ApiError(
                            "invalid_response",
                            "Server returned non-object JSON.",
                            response.status_code,
                            transient=False,
                        )
                    return parsed
                last_error = self._response_error(response)
            except TransportFailure as exception:
                last_error = ApiError(
                    "transport_error",
                    redact_text(str(exception), self._token),
                    None,
                    transient=True,
                )
            except (json.JSONDecodeError, UnicodeDecodeError) as exception:
                last_error = ApiError(
                    "invalid_response",
                    redact_text(f"Server returned invalid JSON: {exception}", self._token),
                    None,
                    transient=False,
                )
            if not retryable or not last_error.transient or attempt >= self._max_attempts:
                raise last_error from None
            self._sleeper(
                last_error.retry_after if last_error.retry_after is not None else min(2 ** (attempt - 1), 8)
            )
        raise AssertionError("unreachable")

    def _response_error(self, response: TransportResponse) -> ApiError:
        try:
            body = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        code = (
            error.get("code", f"http_{response.status_code}")
            if isinstance(error, dict)
            else f"http_{response.status_code}"
        )
        if isinstance(error, dict) and error.get("message"):
            message = str(error["message"])
        else:
            message = f"Worker API request failed (HTTP {response.status_code})."
            snippet = re.sub(r"<[^>]+>", " ", response.content[:1000].decode("utf-8", "replace"))
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if snippet:
                message += f" Server response: {snippet[:300]}"
        retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
        transient = response.status_code == 429 or 500 <= response.status_code <= 599
        return ApiError(
            str(code),
            redact_text(str(message), self._token),
            response.status_code,
            transient=transient,
            retry_after=retry_after,
            details=error.get("details") if isinstance(error, dict) else None,
        )

    @staticmethod
    def _invalid_response(message: str) -> ApiError:
        return ApiError("invalid_response", message, None, transient=False)


def _retry_after_seconds(value: str | None, *, now: datetime | None = None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped.isdigit():
        return float(stripped)
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return max(0.0, (parsed.astimezone(UTC) - current.astimezone(UTC)).total_seconds())


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ApiError(
            "invalid_response", "Server returned an invalid positive integer.", None, transient=False
        )
    return value


def _canonical_uuid4(value: object) -> str:
    if not isinstance(value, str):
        raise ApiError(
            "invalid_response", "Server returned an invalid worker item UUID.", None, transient=False
        )
    try:
        parsed = uuid.UUID(value)
    except ValueError as exception:
        raise ApiError(
            "invalid_response",
            "Server returned an invalid worker item UUID.",
            None,
            transient=False,
        ) from exception
    if parsed.version != 4 or value != str(parsed):
        raise ApiError(
            "invalid_response",
            "Server returned a non-canonical worker item UUID.",
            None,
            transient=False,
        )
    return value


def _parse_offset_datetime(value: str) -> datetime:
    if OFFSET_ISO.fullmatch(value) is None:
        raise ApiError(
            "invalid_response",
            "Server returned an invalid meeting time.",
            None,
            transient=False,
        )
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exception:
        raise ApiError(
            "invalid_response", "Server returned an invalid meeting time.", None, transient=False
        ) from exception
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ApiError("invalid_response", "Server meeting time lacks an offset.", None, transient=False)
    return parsed


def _same_instant(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right
    return _parse_offset_datetime(left).astimezone(UTC) == _parse_offset_datetime(right).astimezone(UTC)
