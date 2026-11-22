from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from openai import OpenAI


def audio_chunks(video_path: Path, chunk_seconds: int = 600) -> list[Path]:
    """Extract mono, low-bitrate audio chunks to keep uploads comfortably small."""
    temp_dir = Path(tempfile.mkdtemp(prefix="yap_audio_"))
    pattern = temp_dir / "chunk_%03d.mp3"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
        "-b:a", "48k", "-f", "segment", "-segment_time", str(chunk_seconds),
        "-reset_timestamps", "1", str(pattern),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    chunks = sorted(temp_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise RuntimeError("FFmpeg produced no audio chunks. Is the input video valid and does it contain audio?")
    return chunks


def transcribe_video(video_path: Path, output_path: Path, language: str | None = None) -> dict[str, Any]:
    client = OpenAI()
    chunks = audio_chunks(video_path)
    all_segments: list[dict[str, Any]] = []
    offset = 0.0
    for idx, chunk in enumerate(chunks, start=1):
        print(f"Transcribing audio chunk {idx}/{len(chunks)}...")
        with chunk.open("rb") as f:
            kwargs = {"model": "whisper-1", "file": f, "response_format": "verbose_json", "timestamp_granularities": ["segment"]}
            if language:
                kwargs["language"] = language
            response = client.audio.transcriptions.create(**kwargs)
        data = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        for seg in data.get("segments", []):
            all_segments.append({
                "start": round(float(seg["start"]) + offset, 3),
                "end": round(float(seg["end"]) + offset, 3),
                "text": seg["text"].strip(),
            })
        # Chunk durations are based on the actual extracted audio, not an assumed fixed duration.
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(chunk)], capture_output=True, text=True, check=True)
        offset += float(probe.stdout.strip())
    result = {"source": str(video_path), "model": "whisper-1", "segments": all_segments}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
