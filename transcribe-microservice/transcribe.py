#!/usr/bin/env python3
"""
Transcription script using NVIDIA Parakeet TDT 0.6B v3 via ONNX-ASR.
Multilingual ASR model supporting 25 European languages.
Uses VAD for segmenting long audio into natural speech segments.
"""

import argparse
import json
import os
import subprocess
import tempfile
import multiprocessing
import wave
import numpy as np

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

SAMPLE_RATE = 16000


def group_tokens_into_segments(
    tokens, timestamps, max_segment_duration=30.0, min_segment_duration=1.0
):
    segments = []
    if not tokens or not timestamps:
        return segments

    current_segment_tokens = []
    current_segment_start = None
    current_segment_end = None

    for i, (token, ts) in enumerate(zip(tokens, timestamps)):
        if current_segment_start is None:
            current_segment_start = ts

        current_segment_tokens.append(token)
        current_segment_end = ts

        segment_duration = current_segment_end - current_segment_start

        is_sentence_end = token.strip().endswith((".", "!", "?", "。", "！", "？"))
        is_long_segment = segment_duration >= max_segment_duration
        is_last_token = i == len(tokens) - 1

        if (
            (is_sentence_end and segment_duration >= min_segment_duration)
            or is_long_segment
            or is_last_token
        ):
            text = "".join(current_segment_tokens).strip()
            text = text.replace("▁", " ").strip()
            text = " ".join(text.split())

            if text and segment_duration >= 0.5:
                segments.append(
                    {
                        "start": current_segment_start,
                        "end": current_segment_end,
                        "text": text,
                        "speaker": "unknown",
                    }
                )

            current_segment_tokens = []
            current_segment_start = None
            current_segment_end = None

    return segments


def main():
    parser = argparse.ArgumentParser(
        description="Parakeet TDT 0.6B v3 Transcription Script"
    )
    parser.add_argument(
        "--audio-file",
        type=str,
        required=True,
        help="Path to the audio file to transcribe.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="transcript.json",
        help="Path to the output JSON file.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Number of CPU threads (default: all available cores).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device to run on (e.g., 'cpu' or 'cuda').",
    )
    args = parser.parse_args()

    threads = args.threads if args.threads else multiprocessing.cpu_count()

    if args.device == "cpu" and threads > 0:
        os.environ["OMP_NUM_THREADS"] = str(threads)
        os.environ["MKL_NUM_THREADS"] = str(threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(threads)
        os.environ["NUMEXPR_NUM_THREADS"] = str(threads)
        os.environ["ONNX_NUM_THREADS"] = str(threads)
        os.environ["ORT_NUM_THREADS"] = str(threads)

    print(f"Loading audio: {args.audio_file}")
    wav_path = tempfile.mktemp(suffix=".wav")

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            args.audio_file,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            wav_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to convert audio: {result.stderr}")

    print(f"Audio converted to: {wav_path}")
    print(f"Using {threads} threads for transcription")

    import onnxruntime as ort

    print("Loading Parakeet TDT 0.6B v3 model via ONNX-ASR...")

    from onnx_asr import load_model, load_vad

    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = threads
    sess_options.inter_op_num_threads = threads
    sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL

    vad = load_vad("silero", sess_options=sess_options)

    model = (
        load_model(
            "nemo-parakeet-tdt-0.6b-v3",
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        .with_vad(vad)
        .with_timestamps()
    )

    print("Loading audio into memory...")
    with wave.open(wav_path, "rb") as wf:
        audio_data = wf.readframes(wf.getnframes())
        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        total_duration = len(audio) / SAMPLE_RATE

    print(f"Audio duration: {total_duration:.2f} seconds")
    print("Transcribing with VAD segmentation...")

    segments = []
    all_text = []

    try:
        results = model.recognize(audio)
        for result in results:
            text = result.text.strip() if result.text else ""
            if text:
                all_text.append(text)

            segment_tokens = result.tokens if result.tokens else []
            segment_timestamps = result.timestamps if result.timestamps else []

            if segment_tokens and segment_timestamps:
                local_segments = group_tokens_into_segments(
                    segment_tokens,
                    segment_timestamps,
                    max_segment_duration=30.0,
                    min_segment_duration=1.0,
                )

                segment_start = result.start if hasattr(result, "start") else 0
                for seg in local_segments:
                    seg["start"] += segment_start
                    seg["end"] += segment_start
                    segments.append(seg)
            elif text:
                start = result.start if hasattr(result, "start") else 0
                end = result.end if hasattr(result, "end") else start + 5.0
                segments.append(
                    {
                        "start": start,
                        "end": end,
                        "text": text,
                        "speaker": "unknown",
                    }
                )

    except Exception as e:
        print(f"VAD transcription failed, falling back to simple mode: {e}")
        print("Trying without VAD...")

        simple_model = load_model(
            "nemo-parakeet-tdt-0.6b-v3",
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        ).with_timestamps()

        chunk_duration = 30.0
        chunk_samples = int(chunk_duration * SAMPLE_RATE)
        num_chunks = int(np.ceil(len(audio) / chunk_samples))

        print(f"Processing in {num_chunks} chunks of {chunk_duration}s each...")

        for i in range(num_chunks):
            start_sample = i * chunk_samples
            end_sample = min((i + 1) * chunk_samples, len(audio))
            chunk_audio = audio[start_sample:end_sample]
            chunk_start_time = start_sample / SAMPLE_RATE

            print(
                f"Processing chunk {i + 1}/{num_chunks} ({chunk_start_time:.1f}s - {end_sample / SAMPLE_RATE:.1f}s)..."
            )

            try:
                result = simple_model.recognize(chunk_audio)
                text = result.text.strip() if result.text else ""

                if text:
                    all_text.append(text)

                tokens = result.tokens if result.tokens else []
                timestamps = result.timestamps if result.timestamps else []

                if tokens and timestamps:
                    local_segments = group_tokens_into_segments(
                        tokens,
                        timestamps,
                        max_segment_duration=30.0,
                        min_segment_duration=1.0,
                    )
                    for seg in local_segments:
                        seg["start"] += chunk_start_time
                        seg["end"] += chunk_start_time
                        segments.append(seg)
                elif text:
                    segments.append(
                        {
                            "start": chunk_start_time,
                            "end": min(
                                chunk_start_time + chunk_duration, total_duration
                            ),
                            "text": text,
                            "speaker": "unknown",
                        }
                    )
            except Exception as chunk_error:
                print(f"Warning: Chunk {i + 1} failed: {chunk_error}")
                continue

    text = " ".join(all_text)

    if not segments and text:
        segments.append(
            {
                "start": 0,
                "end": total_duration,
                "text": text,
                "speaker": "unknown",
            }
        )

    output_result = {
        "language": "auto",
        "language_probability": 1.0,
        "segments": segments,
    }

    print(f"Transcription complete: {len(segments)} segments")
    print(f"Text preview: {text[:200]}..." if len(text) > 200 else f"Text: {text}")

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(output_result, f, indent=2, ensure_ascii=False)
    print(f"Transcript saved to {args.output_file}")

    if os.path.exists(wav_path):
        os.remove(wav_path)


if __name__ == "__main__":
    main()
