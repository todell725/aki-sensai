"""
STT pipeline: Silero-VAD end-of-speech detection → Faster-Whisper transcription.

Architecture:
  - VAD runs on each incoming 512-sample chunk (32ms at 16kHz)
  - When VAD score drops below threshold for VAD_SILENCE_MS ms, speech end is declared
  - Accumulated PCM is handed to Faster-Whisper for transcription
  - Returns (transcript, confidence) tuple
"""

import asyncio
import io
import time
import wave
import struct
from typing import Optional, Tuple

import numpy as np

from config import settings

# Lazy-loaded to avoid import overhead on startup
_whisper_model = None
_vad_model = None
_vad_utils = None


def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _whisper_model


def _load_vad():
    global _vad_model, _vad_utils
    if _vad_model is None:
        import torch
        _vad_model, _vad_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
    return _vad_model, _vad_utils


def warmup() -> None:
    """Pre-load both models at startup to avoid cold-start latency."""
    _load_whisper()
    _load_vad()


def transcribe(pcm_bytes: bytes, sample_rate: int = 16000) -> Tuple[str, float]:
    """
    Transcribe raw 16-bit mono PCM bytes to Japanese text.
    Returns (transcript, avg_log_prob as confidence proxy).
    """
    model = _load_whisper()

    # Convert bytes → float32 numpy array
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    segments, info = model.transcribe(
        samples,
        language="ja",
        beam_size=settings.whisper_beam_size,
        vad_filter=False,  # We use Silero-VAD externally
        without_timestamps=True,
    )

    text_parts = []
    confidence_sum = 0.0
    count = 0

    for seg in segments:
        text_parts.append(seg.text)
        if seg.avg_logprob:
            confidence_sum += seg.avg_logprob
            count += 1

    transcript = "".join(text_parts).strip()
    confidence = confidence_sum / count if count > 0 else 0.0

    return transcript, confidence


async def transcribe_async(pcm_bytes: bytes) -> Tuple[str, float]:
    return await asyncio.to_thread(transcribe, pcm_bytes)


class VADState:
    """State machine for a single WebSocket voice session."""

    CHUNK_SAMPLES = 512   # Silero-VAD requires 512 samples at 16kHz
    SAMPLE_RATE = 16000

    def __init__(self):
        self._vad_model, self._vad_utils = _load_vad()
        (
            self.get_speech_timestamps,
            self.save_audio,
            self.read_audio,
            self.VADIterator,
            self.collect_chunks,
        ) = self._vad_utils

        self._iterator = self.VADIterator(
            self._vad_model,
            threshold=settings.vad_threshold,
            sampling_rate=self.SAMPLE_RATE,
            min_silence_duration_ms=settings.vad_silence_ms,
            speech_pad_ms=30,
        )

        self._speech_buffer: list[bytes] = []
        self._in_speech: bool = False
        self._remainder: bytes = b""

    def reset(self) -> None:
        """Reset after a completed utterance."""
        self._iterator.reset_states()
        self._speech_buffer = []
        self._in_speech = False
        self._remainder = b""

    def feed(self, pcm_chunk: bytes) -> Optional[bytes]:
        """
        Feed a raw PCM bytes chunk (16-bit, 16kHz, mono).
        Returns accumulated speech bytes when end-of-speech is detected, else None.
        """
        import torch

        data = self._remainder + pcm_chunk
        self._remainder = b""

        chunk_bytes = self.CHUNK_SAMPLES * 2  # 16-bit = 2 bytes/sample
        speech_ended = False
        speech_output: Optional[bytes] = None

        while len(data) >= chunk_bytes:
            window = data[:chunk_bytes]
            data = data[chunk_bytes:]

            samples = np.frombuffer(window, dtype=np.int16).astype(np.float32) / 32768.0
            tensor = torch.from_numpy(samples)

            result = self._iterator(tensor, return_seconds=False)

            if result is not None:
                if "start" in result:
                    self._in_speech = True
                    self._speech_buffer = [window]
                elif "end" in result and self._in_speech:
                    self._in_speech = False
                    self._speech_buffer.append(window)
                    speech_output = b"".join(self._speech_buffer)
                    speech_ended = True
                    break
            elif self._in_speech:
                self._speech_buffer.append(window)

        self._remainder = data

        return speech_output if speech_ended else None
