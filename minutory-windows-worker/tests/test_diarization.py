from __future__ import annotations

from minutory_worker.diarization import _normalize_turns, merge_transcript, select_provider


def test_provider_prefers_explicit_directml_device_and_cpu_fallback() -> None:
    selected = select_provider(["DmlExecutionProvider", "CPUExecutionProvider"], device_id=3, device="RX")
    assert selected.provider == "DmlExecutionProvider"
    assert selected.providers == [("DmlExecutionProvider", {"device_id": 3})]
    fallback = select_provider(["CPUExecutionProvider"], device_id=0, device="RX")
    assert fallback.provider == "CPUExecutionProvider"
    assert fallback.fallback


def test_turns_are_sorted_and_receive_stable_friendly_labels() -> None:
    assert _normalize_turns(
        [
            {"start": 4, "end": 5, "speaker": "B"},
            {"start": 1, "end": 2, "speaker": "A"},
            {"start": 3, "end": 4, "speaker": "B"},
            {"start": -1, "end": 1, "speaker": "bad"},
        ]
    ) == [
        {"start": 1.0, "end": 2.0, "speaker": "Speaker 2"},
        {"start": 3.0, "end": 4.0, "speaker": "Speaker 1"},
        {"start": 4.0, "end": 5.0, "speaker": "Speaker 1"},
    ]


def test_merge_uses_largest_overlap_and_unknown_for_gaps_or_failed_diarization() -> None:
    transcript = {
        "segments": [
            {"start": 0, "end": 4, "text": "one"},
            {"start": 4, "end": 8, "text": "two"},
            {"start": 8, "end": 10, "text": "three"},
        ]
    }
    diarization = {
        "diarization": {"status": "completed"},
        "turns": [
            {"start": 0, "end": 3, "speaker": "first"},
            {"start": 3, "end": 7, "speaker": "second"},
        ],
    }
    merged = merge_transcript(transcript, diarization)
    assert [segment["speaker"] for segment in merged["segments"]] == ["Speaker 1", "Speaker 2", "Unknown"]
    failed = merge_transcript(
        transcript, {"diarization": {"status": "failed"}, "turns": diarization["turns"]}
    )
    assert {segment["speaker"] for segment in failed["segments"]} == {"Unknown"}
