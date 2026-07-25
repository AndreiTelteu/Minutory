from __future__ import annotations

from pathlib import Path

import pytest
from conftest import response

from minutory_worker.api import ApiError, RequestTimeout, TransportFailure, WorkerApiClient


class RecordingTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method, url, **kwargs):
        file_bytes = None
        if kwargs["files"]:
            file_bytes = next(iter(kwargs["files"].values()))[1].read()
        self.calls.append({"method": method, "url": url, "file_bytes": file_bytes, **kwargs})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def meeting_response(item, *, artifacts=None):
    return {
        "data": {
            "id": 91,
            "worker_item_id": item.item_id,
            "client_id": item.client_id,
            "title": item.title,
            "meeting_at": "2026-07-10T10:03:47+00:00",
            "duration_seconds": 10,
            "status": "pending",
            "start_transcript_server": False,
            "artifacts": artifacts
            or {
                name: {"uploaded": False, "sha256": None, "bytes": None, "uploaded_at": None}
                for name in ("video", "audio", "transcript")
            },
        }
    }


def test_exact_paths_payload_auth_and_forced_false(item) -> None:
    transport = RecordingTransport(
        [
            response(200, {"data": [{"id": 1, "name": "Client"}]}),
            response(201, meeting_response(item)),
            response(200, meeting_response(item)),
        ]
    )
    client = WorkerApiClient("https://example.test/", "secret-test-token", transport)
    assert client.list_clients()[0]["name"] == "Client"
    created = client.create_meeting(item)
    assert created["id"] == 91
    reconciled = client.reconcile(91)
    assert reconciled.id == 91
    assert [call["url"] for call in transport.calls] == [
        "https://example.test/api/v1/worker/clients",
        "https://example.test/api/v1/worker/meetings",
        "https://example.test/api/v1/worker/meetings/91",
    ]
    assert transport.calls[1]["json_body"]["start_transcript_server"] is False
    timeout = transport.calls[0]["timeout"]
    assert isinstance(timeout, RequestTimeout)
    assert timeout.connect == 10
    assert timeout.read == 120
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer secret-test-token"
    assert "secret-test-token" not in repr(client)


def test_artifact_upload_retries_stream_from_start(tmp_path: Path) -> None:
    path = tmp_path / "audio.wav"
    path.write_bytes(b"artifact")
    transport = RecordingTransport(
        [
            response(503, {"error": {"code": "busy", "message": "Retry"}}, {"Retry-After": "0"}),
            response(200, {"data": {"state": "uploaded", "sha256": "a" * 64, "bytes": 8}}),
        ]
    )
    client = WorkerApiClient("https://example.test", "token", transport, sleeper=lambda _: None)
    result = client.upload_artifact(12, "audio", path)
    assert result["state"] == "uploaded"
    assert [call["file_bytes"] for call in transport.calls] == [b"artifact", b"artifact"]
    assert transport.calls[0]["url"].endswith("/meetings/12/artifacts/audio")
    assert transport.calls[0]["data"] is None


@pytest.mark.parametrize("status", [401, 409, 422])
def test_permanent_errors_are_not_retried(status: int) -> None:
    transport = RecordingTransport(
        [response(status, {"error": {"code": "permanent", "message": "No retry"}})]
    )
    client = WorkerApiClient("https://example.test", "token", transport)
    with pytest.raises(ApiError) as caught:
        client.list_clients()
    assert not caught.value.transient
    assert len(transport.calls) == 1


def test_transient_transport_and_server_errors_retry_and_redact() -> None:
    token = "token-never-log"
    transport = RecordingTransport(
        [
            TransportFailure(f"failed with {token}"),
            response(500, {"error": {"code": "server_error", "message": f"bad {token}"}}),
            response(200, {"data": []}),
        ]
    )
    client = WorkerApiClient("https://example.test", token, transport, sleeper=lambda _: None)
    assert client.list_clients() == []
    failing = RecordingTransport([TransportFailure(f"failed {token}")] * 3)
    client = WorkerApiClient("https://example.test", token, failing, sleeper=lambda _: None)
    with pytest.raises(ApiError) as caught:
        client.list_clients()
    assert token not in str(caught.value)
    assert token not in repr(caught.value)


def test_reconcile_rejects_malformed_response(item) -> None:
    client = WorkerApiClient(
        "https://example.test", "token", RecordingTransport([response(200, {"data": {"id": 1}})])
    )
    with pytest.raises(ApiError, match="reconciliation"):
        client.reconcile(1)


def test_reconcile_requires_explicit_local_transcription_ownership(item) -> None:
    payload = meeting_response(item)
    payload["data"]["start_transcript_server"] = None
    client = WorkerApiClient("https://example.test", "token", RecordingTransport([response(200, payload)]))
    with pytest.raises(ApiError, match="ownership"):
        client.reconcile(91)
