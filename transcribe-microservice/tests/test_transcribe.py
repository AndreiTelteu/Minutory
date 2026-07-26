import importlib.util
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).parents[1] / "transcribe.py"
SPEC = importlib.util.spec_from_file_location("minutory_transcribe", MODULE_PATH)
assert SPEC and SPEC.loader
transcribe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transcribe)


class NormalizationTest(unittest.TestCase):
    def test_normalized_segment_collapses_whitespace_and_clamps_end(self) -> None:
        segment = transcribe.normalized_segment(2.0, 1.0, "  Bună\n   ziua  ")

        self.assertEqual(
            segment,
            {
                "start": 2.0,
                "end": 2.0,
                "text": "Bună ziua",
                "speaker": "unknown",
            },
        )

    def test_normalized_segment_rejects_non_finite_timestamps(self) -> None:
        with self.assertRaises(ValueError):
            transcribe.normalized_segment(math.nan, 1.0, "invalid")

    def test_payload_sorts_segments_and_drops_empty_text(self) -> None:
        payload = transcribe.transcript_payload(
            driver=SimpleNamespace(name="whisper", model_name="large-v3"),
            language="ro",
            language_probability=None,
            duration=3.0,
            runtime={"device": "cpu"},
            segments=[
                transcribe.normalized_segment(2.0, 3.0, "al doilea"),
                transcribe.normalized_segment(0.0, 1.0, "primul"),
                transcribe.normalized_segment(1.0, 2.0, "   "),
            ],
        )

        self.assertEqual([segment["text"] for segment in payload["segments"]], ["primul", "al doilea"])
        self.assertIsNone(payload["language_probability"])

    def test_token_grouping_uses_punctuation_boundaries(self) -> None:
        segments = transcribe.group_tokens_into_segments(
            ["▁Prima", "▁propoziție.", "▁A", "▁doua", "▁propoziție!"],
            [0.0, 2.0, 3.0, 4.0, 6.0],
        )

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["start"], 0.0)
        self.assertEqual(segments[-1]["end"], 6.0)

    def test_parse_args_accepts_romanian_and_english_only(self) -> None:
        original_argv = sys.argv
        try:
            sys.argv = [
                "transcribe.py",
                "--audio-file",
                "input.wav",
                "--output-file",
                "output.json",
                "--language",
                "en",
            ]
            self.assertEqual(transcribe.parse_args().language, "en")

            sys.argv[-1] = "fr"
            with self.assertRaises(SystemExit):
                transcribe.parse_args()
        finally:
            sys.argv = original_argv


if __name__ == "__main__":
    unittest.main()
