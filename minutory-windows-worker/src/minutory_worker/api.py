from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import REDACTED, redact_text
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
    def __init__(self) -> None:
        import httpx

        self._httpx = httpx
        self._client = httpx.Client(follow_redirects=False)

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
        except Exception as exception:
            raise TransportFailure(str(exception)) from exception
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
        self._base_url = f"{base_url.rstrip('/')}/api/v1/worker"
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

    def create_meeting(self, item: WorkerItem) -> dict[str, object]:
        if item.client_id is None:
            raise ValueError("A client must be selected before meeting creation.")
        payload: dict[str, object] = {
            "worker_item_id": item.item_id,
            "client_id": item.client_id,
            "title": item.title,
            "meeting_at": item.meeting_at,
            "duration_seconds": item.duration_seconds,
            "start_transcript_server": False,
        }
        response = self._request("POST", "/meetings", json_body=payload)
        data = response.get("data")
        if not isinstance(data, dict):
            raise ApiError(
                "invalid_response", "Server returned invalid meeting metadata.", None, transient=False
            )
        if data.get("start_transcript_server") is not False:
            raise ApiError(
                "unsafe_server_state",
                "Server meeting is not configured for local transcription.",
                None,
                transient=False,
            )
        return data

    def reconcile(self, meeting_id: int) -> MeetingState:
        response = self._request("GET", f"/meetings/{meeting_id}")
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("artifacts"), dict):
            raise ApiError(
                "invalid_response", "Server returned invalid reconciliation state.", None, transient=False
            )
        artifacts: dict[str, ArtifactState] = {}
        for name in ("video", "audio", "transcript"):
            artifact = data["artifacts"].get(name)
            if not isinstance(artifact, dict):
                raise ApiError("invalid_response", f"Server omitted {name} state.", None, transient=False)
            artifacts[name] = ArtifactState(
                uploaded=artifact.get("uploaded") is True,
                sha256=artifact.get("sha256") if isinstance(artifact.get("sha256"), str) else None,
                bytes=artifact.get("bytes") if isinstance(artifact.get("bytes"), int) else None,
            )
        meeting_at = data.get("meeting_at")
        duration_seconds = data.get("duration_seconds")
        start_transcript_server = data.get("start_transcript_server")
        if meeting_at is not None and not isinstance(meeting_at, str):
            raise ApiError("invalid_response", "Server returned invalid meeting time.", None, transient=False)
        if duration_seconds is not None and not isinstance(duration_seconds, int):
            raise ApiError(
                "invalid_response", "Server returned invalid meeting duration.", None, transient=False
            )
        if not isinstance(start_transcript_server, bool):
            raise ApiError(
                "invalid_response", "Server omitted transcription ownership.", None, transient=False
            )
        return MeetingState(
            id=int(data["id"]),
            worker_item_id=str(data["worker_item_id"]),
            client_id=int(data["client_id"]),
            title=str(data["title"]),
            meeting_at=meeting_at,
            duration_seconds=duration_seconds,
            start_transcript_server=start_transcript_server,
            artifacts=artifacts,
        )

    def upload_artifact(
        self,
        meeting_id: int,
        artifact: str,
        path: Path,
        *,
        replace: bool = False,
    ) -> dict[str, object]:
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
            raise ApiError(
                "invalid_response", "Server returned invalid artifact state.", None, transient=False
            )
        return result

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
                raise last_error
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
        message = (
            error.get("message", "Worker API request failed.")
            if isinstance(error, dict)
            else "Worker API request failed."
        )
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


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
