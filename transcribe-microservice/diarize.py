#!/usr/bin/env python3
"""
Speaker diarization using pyannote.audio directly.
"""
import os
import torch

# Configure environment variables for HuggingFace
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "1"

# Use HuggingFace token from environment variable if available
hf_token = os.environ.get("HF_API_KEY", "")


def diarize_transcript(audio_file, transcript, device="cpu", model_name="pyannote/speaker-diarization-3.1"):
    """
    Performs speaker diarization on a transcript, splitting segments by speaker changes.
    Uses pyannote.audio directly instead of whisperx.
    """
    try:
        from pyannote.audio import Pipeline
        
        print(f"Loading diarization model: {model_name}")
        pipeline = Pipeline.from_pretrained(
            model_name,
            use_auth_token=hf_token if hf_token else None
        )
        
        if device == "cpu":
            pipeline.to(torch.device(device))
        
        print(f"Diarizing {audio_file}")
        diarization = pipeline(audio_file)
        
        # Build speaker map
        speaker_map = {}
        for segment, track, label in diarization.itertracks(yield_label=True):
            start = segment.start
            end = segment.end
            for seg in transcript.get("segments", []):
                if seg["start"] >= start and seg["end"] <= end:
                    seg["speaker"] = label
                    break
        
        print(f"Diarization complete")
        return transcript

    except Exception as e:
        print(f"Diarization failed: {str(e)}")
        # Fallback: Assign "unknown" to original segments
        for segment in transcript.get("segments", []):
            segment["speaker"] = "unknown"
        return transcript
