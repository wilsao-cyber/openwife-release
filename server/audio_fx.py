"""
Audio post-processing pipeline for TTS output.
Each emotion has a preset controlling reverb, warmth, compression, etc.
All effects use scipy.signal — no additional dependencies needed.
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FxPreset:
    reverb_room: float = 0.1        # 0-1, impulse response length
    reverb_wet: float = 0.05        # 0-1, wet/dry mix
    warmth_db: float = 1.0          # 0-6, low-shelf boost
    warmth_freq: float = 250.0      # Hz
    compression_threshold: float = -20.0  # dB
    compression_ratio: float = 2.0  # 1-8
    breathiness_db: float = 0.0     # 0-6, high-shelf boost
    breathiness_freq: float = 6000.0  # Hz
    deess_freq: float = 6500.0      # Hz center
    deess_db: float = 3.0           # 0-12, reduction
    noise_gate_db: float = -40.0    # threshold


EMOTION_PRESETS: dict[str, FxPreset] = {
    "neutral":   FxPreset(reverb_room=0.1, reverb_wet=0.05, warmth_db=1, compression_ratio=2, breathiness_db=0, deess_db=3),
    "happy":     FxPreset(reverb_room=0.1, reverb_wet=0.03, warmth_db=1.5, compression_ratio=2, breathiness_db=0.5, deess_db=3),
    "horny":     FxPreset(reverb_room=0.35, reverb_wet=0.18, warmth_db=3, compression_ratio=3, breathiness_db=4, deess_db=2, noise_gate_db=-50),
    "sad":       FxPreset(reverb_room=0.3, reverb_wet=0.15, warmth_db=2, compression_ratio=2, breathiness_db=1, deess_db=3),
    "relaxed":   FxPreset(reverb_room=0.2, reverb_wet=0.1, warmth_db=2, compression_ratio=2, breathiness_db=2, deess_db=3),
    "angry":     FxPreset(reverb_room=0.05, reverb_wet=0.02, warmth_db=0, compression_ratio=6, breathiness_db=0, deess_db=4, noise_gate_db=-35),
    "surprised": FxPreset(reverb_room=0.15, reverb_wet=0.08, warmth_db=1, compression_ratio=2, breathiness_db=0.5, deess_db=3),
}


def _noise_gate(samples: np.ndarray, threshold_db: float) -> np.ndarray:
    """Simple noise gate — zero out samples below threshold."""
    threshold = 10 ** (threshold_db / 20)
    envelope = np.abs(samples)
    # Smooth envelope with ~5ms window
    window = max(1, int(0.005 * 24000))
    if len(envelope) > window:
        kernel = np.ones(window) / window
        envelope = np.convolve(envelope, kernel, mode='same')
    gate = (envelope > threshold).astype(np.float32)
    # Smooth gate transitions (~2ms)
    smooth_w = max(1, int(0.002 * 24000))
    if len(gate) > smooth_w:
        kernel = np.ones(smooth_w) / smooth_w
        gate = np.convolve(gate, kernel, mode='same')
        gate = np.clip(gate, 0, 1)
    return samples * gate


def _low_shelf(samples: np.ndarray, sr: int, gain_db: float, freq: float) -> np.ndarray:
    """Low-shelf filter for warmth boost."""
    if abs(gain_db) < 0.1:
        return samples
    from scipy.signal import butter, sosfilt
    nyq = sr / 2
    cutoff = min(freq / nyq, 0.99)
    sos = butter(2, cutoff, btype='low', output='sos')
    boosted = sosfilt(sos, samples)
    gain = 10 ** (gain_db / 20) - 1
    return samples + boosted * gain


def _high_shelf(samples: np.ndarray, sr: int, gain_db: float, freq: float) -> np.ndarray:
    """High-shelf filter for breathiness boost."""
    if abs(gain_db) < 0.1:
        return samples
    from scipy.signal import butter, sosfilt
    nyq = sr / 2
    cutoff = min(freq / nyq, 0.99)
    sos = butter(2, cutoff, btype='high', output='sos')
    boosted = sosfilt(sos, samples)
    gain = 10 ** (gain_db / 20) - 1
    return samples + boosted * gain


def _deess(samples: np.ndarray, sr: int, center_freq: float, reduction_db: float) -> np.ndarray:
    """Simple de-esser — reduce sibilance around center_freq."""
    if reduction_db < 0.5:
        return samples
    from scipy.signal import butter, sosfilt
    nyq = sr / 2
    low = max(0.01, (center_freq - 1500) / nyq)
    high = min(0.99, (center_freq + 1500) / nyq)
    if low >= high:
        return samples
    sos = butter(2, [low, high], btype='band', output='sos')
    sibilance = sosfilt(sos, samples)
    # Detect sibilance energy
    energy = np.abs(sibilance)
    window = max(1, int(0.01 * sr))
    if len(energy) > window:
        kernel = np.ones(window) / window
        energy = np.convolve(energy, kernel, mode='same')
    threshold = np.percentile(energy, 80)
    mask = energy > threshold
    reduction = 10 ** (-reduction_db / 20)
    result = samples.copy()
    result[mask] = samples[mask] - sibilance[mask] * (1 - reduction)
    return result


def _compress(samples: np.ndarray, threshold_db: float, ratio: float) -> np.ndarray:
    """Simple compressor with envelope following."""
    if ratio <= 1.01:
        return samples
    threshold = 10 ** (threshold_db / 20)
    envelope = np.abs(samples)
    # Smooth envelope ~10ms
    window = max(1, int(0.01 * 24000))
    if len(envelope) > window:
        kernel = np.ones(window) / window
        envelope = np.convolve(envelope, kernel, mode='same')
    # Apply compression
    gain = np.ones_like(envelope)
    above = envelope > threshold
    if np.any(above):
        excess_db = 20 * np.log10(np.clip(envelope[above] / threshold, 1e-10, None))
        reduced_db = excess_db / ratio
        gain[above] = 10 ** ((reduced_db - excess_db) / 20)
    return samples * gain


def _reverb(samples: np.ndarray, sr: int, room_size: float, wet: float) -> np.ndarray:
    """Synthetic reverb using exponential decay impulse response."""
    if wet < 0.01 or room_size < 0.01:
        return samples
    from scipy.signal import fftconvolve
    # Generate impulse response
    ir_length = int(room_size * sr * 0.5)  # room_size controls decay time
    ir_length = min(ir_length, sr)  # cap at 1 second
    t = np.arange(ir_length, dtype=np.float32)
    ir = np.random.randn(ir_length).astype(np.float32) * np.exp(-t / (ir_length * 0.3))
    ir = ir / (np.max(np.abs(ir)) + 1e-10)
    # Convolve
    reverbed = fftconvolve(samples, ir, mode='full')[:len(samples)]
    return samples * (1 - wet) + reverbed * wet


def apply_fx(samples: np.ndarray, sr: int, preset: FxPreset) -> np.ndarray:
    """Apply full FX chain. Input/output: float32 array [-1, 1]."""
    s = samples.astype(np.float32)

    # 1. Noise gate
    s = _noise_gate(s, preset.noise_gate_db)

    # 2. Warmth (low-shelf boost)
    s = _low_shelf(s, sr, preset.warmth_db, preset.warmth_freq)

    # 3. De-ess
    s = _deess(s, sr, preset.deess_freq, preset.deess_db)

    # 4. Compression
    s = _compress(s, preset.compression_threshold, preset.compression_ratio)

    # 5. Breathiness (high-shelf boost)
    s = _high_shelf(s, sr, preset.breathiness_db, preset.breathiness_freq)

    # 6. Reverb (last, so it captures all processed audio)
    s = _reverb(s, sr, preset.reverb_room, preset.reverb_wet)

    # Normalize to prevent clipping
    peak = np.max(np.abs(s))
    if peak > 0.95:
        s = s * (0.95 / peak)

    return s


def process_wav(wav_path: Path, emotion: str = "neutral") -> Path:
    """Load WAV, apply emotion-based FX preset, write back in-place."""
    import wave
    import struct

    preset = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["neutral"])

    try:
        with wave.open(str(wav_path), 'rb') as wf:
            sr = wf.getframerate()
            n_frames = wf.getnframes()
            sw = wf.getsampwidth()
            n_channels = wf.getnchannels()
            raw = wf.readframes(n_frames)

        if sw != 2 or n_channels != 1:
            logger.debug(f"Skipping FX: unsupported format sw={sw} ch={n_channels}")
            return wav_path

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        processed = apply_fx(samples, sr, preset)
        out_int16 = np.clip(processed * 32768, -32768, 32767).astype(np.int16)

        with wave.open(str(wav_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(out_int16.tobytes())

        return wav_path

    except Exception as e:
        logger.warning(f"Audio FX failed for {wav_path}: {e}")
        return wav_path
