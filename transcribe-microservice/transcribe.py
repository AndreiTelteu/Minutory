#!/usr/bin/env python3
"""
Transcription script using faster-whisper (instead of whisperx due to torch compatibility).
"""
import argparse
import json
import os
import faster_whisper
from diarize import diarize_transcript

# Configure environment variables for HuggingFace
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "1"

# Use HuggingFace token from environment variable if available
hf_token = os.environ.get("HF_API_KEY", "")


def main():
    parser = argparse.ArgumentParser(
        description="Faster Whisper Transcription Script with optional diarization."
    )
    parser.add_argument(
        "--audio-file",
        type=str,
        required=True,
        help="Path to the audio file to transcribe.",
    )
    parser.add_argument(
        "--model-size",
        type=str,
        default="small",
        help="Whisper model size (e.g., tiny, base, small, medium, large, large-v2).",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional language code to force Whisper to use (e.g., 'en').",
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        default=False,
        help="Enable speaker diarization.",
    )
    parser.add_argument(
        "--align",
        action="store_true",
        default=False,
        help="Perform alignment on the transcribed segments.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device to run Whisper on (e.g., 'cpu' or 'cuda').",
    )
    parser.add_argument(
        "--compute-type",
        type=str,
        default="int8",
        help="Compute type for Whisper inference (e.g., 'float16', 'int8').",
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
        default=1,
        help="Number of threads used for CPU inference",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default="/tmp/whisper_models",
        help="Directory where models are stored and cached",
    )
    parser.add_argument(
        "--diarization-model",
        type=str,
        default="pyannote/speaker-diarization-3.1",
        help="Speaker diarization model to use",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Batch size for inference",
    )
    args = parser.parse_args()

    # Configure CPU threading based on --threads for CPU runs
    if args.device == "cpu" and args.threads and args.threads > 0:
        os.environ["OMP_NUM_THREADS"] = str(args.threads)
        os.environ["MKL_NUM_THREADS"] = str(args.threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(args.threads)
        os.environ["NUMEXPR_NUM_THREADS"] = str(args.threads)
        try:
            import torch
            torch.set_num_threads(args.threads)
            interop = max(1, args.threads // 2)
            torch.set_num_interop_threads(interop)
            print(f"Configured CPU threads: torch={args.threads}, interop={interop}")
        except Exception as _e:
            print(f"Warning: could not fully configure torch thread settings: {_e}")

    # Load faster-whisper model
    print(f"Loading model: {args.model_size}")
    model = faster_whisper.WhisperModel(
        args.model_size,
        device=args.device,
        compute_type=args.compute_type,
        download_root=args.models_dir,
    )

    # Load audio - convert video to audio using faster-whisper's built-in loader
    import soundfile as sf
    print(f"Loading audio: {args.audio_file}")
    
    # For video files, use faster-whisper's audio loading which handles multiple formats
    # If it's a video file, we need to convert it first
    if args.audio_file.endswith(('.mp4', '.mov', '.avi', '.webm', '.m4a')):
        import subprocess
        import tempfile
        wav_path = tempfile.mktemp(suffix='.wav')
        # Convert to wav using ffmpeg
        subprocess.run([
            'ffmpeg', '-y', '-i', args.audio_file,
            '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wav_path
        ], capture_output=True)
        audio, samplerate = sf.read(wav_path)
    else:
        audio, samplerate = sf.read(args.audio_file)
    
    # If stereo, convert to mono
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
    
    # Ensure audio is float32 (required by faster-whisper)
    audio = audio.astype('float32')
    
    # Convert to 16kHz if needed
    if samplerate != 16000:
        from scipy import signal
        number_of_samples = round(len(audio) * 16000 / samplerate)
        audio = signal.resample(audio, number_of_samples)

    # Transcribe
    print(f"Transcribing with language: {args.language or 'auto-detect'}")
    segments, info = model.transcribe(
        audio, 
        language=args.language,
        beam_size=5,
        vad_filter=False,  # Disable VAD due to compatibility issues
    )

    print(f"Detected language: {info.language} with probability {info.language_probability:.2f}")

    # Build result
    result = {
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": []
    }

    for segment in segments:
        result["segments"].append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "avg_logprob": segment.avg_logprob,
            "no_speech_prob": segment.no_speech_prob,
        })

    # Optionally perform diarization
    if args.diarize:
        try:
            print("Performing speaker diarization...")
            diarized_result = diarize_transcript(args.audio_file, result, args.device, args.diarization_model)
            result["segments"] = diarized_result["segments"]
        except Exception as e:
            print(f"Diarization failed: {e}")
            # If diarization fails, we can still save the transcript without speaker labels
            for segment in result["segments"]:
                segment["speaker"] = "unknown"
    else:
        for segment in result["segments"]:
            segment["speaker"] = "unknown"

    # Save result
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Transcript saved to {args.output_file}")


if __name__ == "__main__":
    main()
