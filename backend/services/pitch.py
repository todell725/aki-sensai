"""
Pitch accent analysis service.

- get_pitch_contour(text): uses pyopenjtalk to extract mora-level pitch patterns
- compare_contours(reference, attempt_wav): uses librosa to extract F0 from user audio
  and aligns it against the reference pattern
"""

import asyncio
import io
from typing import Optional

import numpy as np

from models.schemas import PitchContour, PitchCompareResponse


def get_pitch_contour(text: str) -> PitchContour:
    """
    Generate pitch accent pattern for Japanese text.
    Returns mora sequence and integer pattern: 0=low, 1=high, 2=falling.
    """
    try:
        import pyopenjtalk
        # run_frontend returns a list of dicts with mora/accent info
        features = pyopenjtalk.run_frontend(text)
        morae: list[str] = []
        pattern: list[int] = []

        for word_info in features:
            word_morae = word_info.get("mora", [])
            accent = word_info.get("acc", 0)

            for i, mora in enumerate(word_morae):
                morae.append(mora)
                if accent == 0:
                    # Flat: first mora low, rest high
                    pattern.append(0 if i == 0 else 1)
                else:
                    # Rising then falling at accent position
                    if i == 0:
                        pattern.append(0)
                    elif i < accent:
                        pattern.append(1)
                    elif i == accent:
                        pattern.append(2)
                    else:
                        pattern.append(0)

        return PitchContour(text=text, morae=morae, pattern=pattern)

    except ImportError:
        # Graceful degradation: return empty contour
        return PitchContour(text=text, morae=[], pattern=[])
    except Exception:
        return PitchContour(text=text, morae=[], pattern=[])


def compare_contours(
    reference_pattern: list[int],
    attempt_wav_bytes: bytes,
) -> PitchCompareResponse:
    """
    Compare user's pitch attempt (WAV bytes) against the reference pattern.
    Uses librosa to extract F0 from the audio.

    Returns match_ratio and indices of mismatched morae.
    """
    try:
        import librosa
        import soundfile as sf

        # Load WAV from bytes
        audio_io = io.BytesIO(attempt_wav_bytes)
        y, sr = sf.read(audio_io, dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)

        # Extract fundamental frequency (F0)
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )

        # Remove unvoiced frames and normalize to pitch direction pattern
        voiced_f0 = f0[voiced_flag] if voiced_flag is not None else f0
        voiced_f0 = voiced_f0[~np.isnan(voiced_f0)]

        if len(voiced_f0) == 0 or len(reference_pattern) == 0:
            return PitchCompareResponse(
                match_ratio=0.0,
                mismatched_morae=[],
                reference_pattern=reference_pattern,
                attempt_pattern=[],
            )

        # Resample attempt contour to match reference length
        from scipy.interpolate import interp1d
        x_orig = np.linspace(0, 1, len(voiced_f0))
        x_new = np.linspace(0, 1, len(reference_pattern))
        interpolator = interp1d(x_orig, voiced_f0, kind="linear", fill_value="extrapolate")
        attempt_resampled = interpolator(x_new).tolist()

        # Convert F0 to direction pattern: 0=low, 1=high, 2=falling
        attempt_pattern = _f0_to_direction(attempt_resampled)

        # Compare patterns mora by mora
        mismatches = [
            i for i, (ref, att) in enumerate(zip(reference_pattern, attempt_pattern))
            if ref != att
        ]
        match_ratio = 1.0 - (len(mismatches) / len(reference_pattern))

        return PitchCompareResponse(
            match_ratio=round(match_ratio, 3),
            mismatched_morae=mismatches,
            reference_pattern=reference_pattern,
            attempt_pattern=attempt_resampled,
        )

    except ImportError:
        return PitchCompareResponse(
            match_ratio=0.0,
            mismatched_morae=[],
            reference_pattern=reference_pattern,
            attempt_pattern=[],
        )


def _f0_to_direction(f0_values: list[float]) -> list[int]:
    """Convert raw F0 values to pitch direction pattern [0=low, 1=high, 2=falling]."""
    if len(f0_values) == 0:
        return []

    median_f0 = float(np.median([v for v in f0_values if v > 0] or [0]))
    directions: list[int] = []

    for i, val in enumerate(f0_values):
        if i == 0:
            directions.append(0 if val < median_f0 else 1)
        else:
            prev = f0_values[i - 1]
            diff = val - prev
            if diff < -20:
                directions.append(2)  # falling
            elif val < median_f0 * 0.85:
                directions.append(0)  # low
            else:
                directions.append(1)  # high

    return directions


async def get_pitch_contour_async(text: str) -> PitchContour:
    return await asyncio.to_thread(get_pitch_contour, text)


async def compare_contours_async(
    reference_pattern: list[int],
    attempt_wav_bytes: bytes,
) -> PitchCompareResponse:
    return await asyncio.to_thread(compare_contours, reference_pattern, attempt_wav_bytes)
