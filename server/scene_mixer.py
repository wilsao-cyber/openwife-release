"""
Scene Mixer — parses structured scripts, generates TTS segments,
looks up SFX from catalog, and mixes everything into a single WAV file.

Script format:
[
  {"type": "speech", "text": "台詞"},
  {"type": "sfx", "query": "雨の音", "volume": 0.5, "fade_in": 1.0},
  {"type": "pause", "duration": 5},
  {"type": "sfx_stop"},
  {"type": "sfx", "query": "射精音", "volume": 0.7},
]

The mixer builds a numpy timeline and layers speech + SFX onto it.
"""

import asyncio
import logging
import uuid
import wave
import struct
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000  # Match Voicebox output


def _load_wav_as_float(path: str) -> Optional[np.ndarray]:
    """Load a WAV/MP3 file and return float32 mono samples at SAMPLE_RATE."""
    try:
        import soundfile as sf
        audio, sr = sf.read(path, dtype='float32', always_2d=True)
        # Convert to mono
        if audio.shape[1] > 1:
            audio = audio.mean(axis=1)
        else:
            audio = audio[:, 0]
        # Resample if needed
        if sr != SAMPLE_RATE:
            from scipy.signal import resample
            new_len = int(len(audio) * SAMPLE_RATE / sr)
            audio = resample(audio, new_len).astype(np.float32)
        return audio
    except Exception as e:
        logger.warning(f"Failed to load audio {path}: {e}")
        return None


def _fade_in(samples: np.ndarray, duration_s: float) -> np.ndarray:
    """Apply fade-in to audio samples."""
    n = min(int(duration_s * SAMPLE_RATE), len(samples))
    if n <= 0:
        return samples
    result = samples.copy()
    result[:n] *= np.linspace(0, 1, n, dtype=np.float32)
    return result


def _fade_out(samples: np.ndarray, duration_s: float) -> np.ndarray:
    """Apply fade-out to audio samples."""
    n = min(int(duration_s * SAMPLE_RATE), len(samples))
    if n <= 0:
        return samples
    result = samples.copy()
    result[-n:] *= np.linspace(1, 0, n, dtype=np.float32)
    return result


def _mix_into(timeline: np.ndarray, samples: np.ndarray, offset: int, volume: float = 1.0):
    """Mix samples into timeline at given offset. Extends timeline if needed."""
    end = offset + len(samples)
    if end > len(timeline):
        timeline = np.pad(timeline, (0, end - len(timeline)))
    timeline[offset:offset + len(samples)] += samples * volume
    return timeline


async def mix_scene(
    script: list[dict],
    tts_engine,
    sfx_catalog,
    language: str = "zh-TW",
    emotion: str = "neutral",
) -> Optional[Path]:
    """
    Parse scene script, generate TTS + lookup SFX, mix into single WAV.
    Returns path to the mixed audio file.
    """
    import httpx
    from audio_fx import process_wav

    output_dir = Path("./output/audio")
    output_dir.mkdir(parents=True, exist_ok=True)

    timeline = np.zeros(SAMPLE_RATE * 5, dtype=np.float32)  # start with 5s, will grow
    cursor = 0  # current position in samples
    active_sfx = None  # currently looping SFX
    active_sfx_volume = 0.5

    for step in script:
        step_type = step.get("type", "")

        if step_type == "speech":
            text = step.get("text", "")
            if not text:
                continue

            # Generate TTS for this line
            ja_text, sentences, instruct, profile_id = await tts_engine._prepare_tts(
                text, language, emotion
            )
            if not sentences:
                continue

            async with httpx.AsyncClient(timeout=120.0) as client:
                for sent in sentences:
                    path = await tts_engine._voicebox_generate_one(
                        client, sent, profile_id, instruct, emotion=emotion
                    )
                    if not path:
                        continue
                    speech_audio = _load_wav_as_float(str(path))
                    if speech_audio is None:
                        continue
                    # Mix speech into timeline
                    timeline = _mix_into(timeline, speech_audio, cursor)
                    cursor += len(speech_audio)
                    # Small gap between sentences
                    cursor += int(0.15 * SAMPLE_RATE)

            # If SFX is active, layer it under the speech we just added
            if active_sfx is not None:
                sfx_samples = active_sfx
                sfx_start = cursor - len(speech_audio) - int(0.15 * SAMPLE_RATE) if speech_audio is not None else cursor
                # Loop SFX to cover speech duration
                speech_len = cursor - sfx_start
                if speech_len > 0 and len(sfx_samples) > 0:
                    repeats = (speech_len // len(sfx_samples)) + 1
                    looped = np.tile(sfx_samples, repeats)[:speech_len]
                    timeline = _mix_into(timeline, looped, sfx_start, active_sfx_volume)

        elif step_type == "sfx":
            tag = step.get("tag", "")
            query = step.get("query", "")
            volume = step.get("volume", 0.5)
            fade_in_s = step.get("fade_in", 0.5)

            results = sfx_catalog.search(tag=tag, query=query, limit=1)
            if not results:
                logger.warning(f"SFX not found: {query}")
                continue

            sfx_audio = _load_wav_as_float(results[0].path)
            if sfx_audio is None:
                continue

            if fade_in_s > 0:
                sfx_audio = _fade_in(sfx_audio, fade_in_s)

            active_sfx = sfx_audio
            active_sfx_volume = volume

            # Also place this SFX at current cursor position
            timeline = _mix_into(timeline, sfx_audio, cursor, volume)

        elif step_type == "pause":
            duration = step.get("duration", 5)
            pause_samples = int(duration * SAMPLE_RATE)

            # If SFX is active, loop it during the pause
            if active_sfx is not None and len(active_sfx) > 0:
                repeats = (pause_samples // len(active_sfx)) + 1
                looped = np.tile(active_sfx, repeats)[:pause_samples]
                timeline = _mix_into(timeline, looped, cursor, active_sfx_volume)

            cursor += pause_samples

        elif step_type == "sfx_stop":
            if active_sfx is not None:
                # Fade out over 0.5s at current position
                fade_len = min(int(0.5 * SAMPLE_RATE), len(active_sfx))
                fade = np.linspace(active_sfx_volume, 0, fade_len, dtype=np.float32)
                if cursor + fade_len <= len(timeline):
                    timeline[cursor:cursor + fade_len] *= np.linspace(1, 0.5, fade_len, dtype=np.float32)
                active_sfx = None
                active_sfx_volume = 0.5

    # Trim trailing silence
    end = len(timeline)
    while end > 0 and abs(timeline[end - 1]) < 0.001:
        end -= 1
    end = min(len(timeline), end + int(0.3 * SAMPLE_RATE))  # keep 0.3s tail
    timeline = timeline[:end]

    # Normalize
    peak = np.max(np.abs(timeline))
    if peak > 0.95:
        timeline = timeline * (0.95 / peak)

    # Write WAV
    out_name = f"scene_{uuid.uuid4().hex[:8]}.wav"
    out_path = output_dir / out_name
    out_int16 = np.clip(timeline * 32768, -32768, 32767).astype(np.int16)
    with wave.open(str(out_path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(out_int16.tobytes())

    duration_s = len(timeline) / SAMPLE_RATE
    logger.info(f"Scene mixed: {out_name} ({duration_s:.1f}s)")
    return out_path
