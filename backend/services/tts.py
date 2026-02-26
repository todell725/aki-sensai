"""
Piper TTS service — synthesizes Japanese text to WAV bytes via subprocess.
Streams WAV header + PCM audio suitable for streaming playback.
"""

import asyncio
import subprocess
import io
import wave
import struct
from typing import Optional

from config import settings


def synthesize(text: str) -> bytes:
    """
    Run Piper binary synchronously and return WAV bytes.
    Piper reads text from stdin and writes raw PCM to stdout with --output_raw.
    We wrap the PCM in a WAV container for browser compatibility.
    """
    if not text.strip():
        return b""

    try:
        result = subprocess.run(
            [
                settings.piper_binary,
                "--model", settings.piper_model_path,
                "--output_raw",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Piper error: {result.stderr.decode()}")

        raw_pcm = result.stdout
        return _pcm_to_wav(raw_pcm)

    except FileNotFoundError:
        raise RuntimeError(
            "Piper binary not found. Install from https://github.com/rhasspy/piper"
        )


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 22050, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw PCM data in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


async def synthesize_async(text: str) -> bytes:
    """Async wrapper — runs synthesis in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(synthesize, text)


def is_available() -> bool:
    """Check if Piper binary and model are accessible."""
    try:
        result = subprocess.run(
            [settings.piper_binary, "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
