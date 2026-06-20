"""Prepare uploaded audio for Basic Pitch transcription."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from app.core.config import Settings

logger = logging.getLogger(__name__)

BASIC_PITCH_SAMPLE_RATE = 22050


class AudioPreprocessError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class PreprocessResult:
    output_path: Path
    stem_separation: str  # "none", "light", "hpss", "demucs"
    stereo_mode: str


def resolve_preprocess_mode(settings: Settings) -> str:
    """Return effective mode: off | light | full | synthetic."""
    mode = settings.preprocess_mode.lower().strip()
    if mode in {"light", "full", "synthetic"}:
        return mode
    if settings.transcription_profile.lower() == "synthetic" and mode == "off":
        return "synthetic"
    if settings.enable_audio_preprocessing:
        return "full" if settings.enable_hpss or settings.enable_stem_separation else "light"
    return "off"


def _to_mono(y: np.ndarray, mode: str) -> np.ndarray:
    if y.ndim == 1:
        return y

    left, right = y[0], y[1]
    if mode == "left":
        return left
    if mode == "right":
        return right
    if mode == "mono":
        return librosa.to_mono(y)
    left_peak = float(np.max(np.abs(left)))
    right_peak = float(np.max(np.abs(right)))
    return left if left_peak >= right_peak else right


def _normalize_peak(audio: np.ndarray, target: float = 0.95) -> np.ndarray:
    peak = float(np.max(np.abs(audio)))
    if peak <= 0:
        return audio
    return (audio / peak) * target


def _highpass_guitar(audio: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    if cutoff_hz <= 0:
        return audio
    from scipy.signal import butter, sosfilt

    nyquist = sample_rate / 2.0
    normalized = min(cutoff_hz / nyquist, 0.99)
    sos = butter(2, normalized, btype="high", output="sos")
    return sosfilt(sos, audio).astype(np.float32)


def _hpss_harmonic(audio: np.ndarray) -> np.ndarray:
    # Low margin keeps pick transients; aggressive HPSS destroys onsets.
    harmonic, _percussive = librosa.effects.hpss(audio, margin=1.0)
    return harmonic


def _try_demucs_stem(wav: np.ndarray, sample_rate: int) -> np.ndarray | None:
    """Extract htdemucs 'other' stem from real stereo input."""
    try:
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model
    except ImportError:
        logger.info("demucs not installed; skipping stem separation")
        return None

    if wav.ndim != 2 or wav.shape[0] < 2 or wav.shape[1] == 0:
        logger.info("demucs requires stereo input; skipping stem separation")
        return None

    wav_t = torch.from_numpy(wav.astype(np.float32))
    ref = wav_t.mean(0)
    std = ref.std()
    if std > 0:
        wav_t = (wav_t - ref.mean()) / std

    model = get_model("htdemucs")
    model.eval()
    with torch.no_grad():
        sources = apply_model(model, wav_t.unsqueeze(0), device="cpu")[0]

    other = sources[2].mean(0).cpu().numpy()
    if std > 0:
        other = other * std + ref.mean().item()
    return other.astype(np.float32)


def _bandpass_guitar(
    audio: np.ndarray,
    sample_rate: int,
    low_hz: float,
    high_hz: float,
) -> np.ndarray:
    from scipy.signal import butter, sosfilt

    nyquist = sample_rate / 2.0
    low = max(low_hz / nyquist, 0.001)
    high = min(high_hz / nyquist, 0.99)
    if low >= high:
        return audio
    sos = butter(3, [low, high], btype="band", output="sos")
    return sosfilt(sos, audio).astype(np.float32)


def _spectral_soft_gate(audio: np.ndarray, sample_rate: int, floor_percentile: float = 12.0) -> np.ndarray:
    """Attenuate broadband noise floor without removing pick transients (unlike HPSS)."""
    hop_length = 512
    n_fft = 2048
    stft = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(stft)
    phase = np.angle(stft)
    floor = np.percentile(magnitude, floor_percentile, axis=1, keepdims=True)
    cleaned = np.maximum(magnitude - floor * 0.85, magnitude * 0.04)
    return librosa.istft(cleaned * np.exp(1j * phase), hop_length=hop_length).astype(np.float32)


def preprocess_synthetic(
    audio: np.ndarray,
    sample_rate: int,
    settings: Settings,
) -> np.ndarray:
    """Conditioning for AI/synthetic guitar: band-limit, enhance transients, gate noise."""
    audio = _bandpass_guitar(
        audio,
        sample_rate,
        settings.guitar_min_frequency_hz,
        min(settings.guitar_max_frequency_hz, 1400.0),
    )
    audio = librosa.effects.preemphasis(audio, coef=0.97)
    audio = _spectral_soft_gate(audio, sample_rate)
    return _normalize_peak(audio, settings.preprocess_normalize_peak)


def preprocess_full(
    audio: np.ndarray,
    stereo_wav: np.ndarray | None,
    sample_rate: int,
    settings: Settings,
) -> tuple[np.ndarray, str]:
    separation = "none"

    if settings.enable_stem_separation and stereo_wav is not None:
        demucs_stem = _try_demucs_stem(stereo_wav, sample_rate)
        if demucs_stem is not None:
            audio = demucs_stem
            separation = "demucs"
        elif settings.enable_hpss:
            audio = _hpss_harmonic(audio)
            separation = "hpss"
    elif settings.enable_hpss:
        audio = _hpss_harmonic(audio)
        separation = "hpss"

    audio = _highpass_guitar(audio, sample_rate, settings.preprocess_highpass_hz)
    audio = _normalize_peak(audio, settings.preprocess_normalize_peak)
    return audio, separation


def prepare_audio_for_transcription(
    audio_path: Path,
    settings: Settings,
) -> PreprocessResult:
    """Load and optionally preprocess audio. Default mode is off (use original file)."""
    mode = resolve_preprocess_mode(settings)
    stereo_mode = settings.stereo_mode

    if mode == "off":
        return PreprocessResult(
            output_path=audio_path,
            stem_separation="none",
            stereo_mode=stereo_mode,
        )

    settings.ensure_directories()
    try:
        y, _sr = librosa.load(
            str(audio_path),
            sr=BASIC_PITCH_SAMPLE_RATE,
            mono=False,
        )
    except Exception as exc:
        raise AudioPreprocessError(f"Failed to load audio: {exc}") from exc

    stereo_wav = y if y.ndim == 2 else None
    mono = _to_mono(y, stereo_mode)

    if mode == "light":
        processed = _normalize_peak(mono, settings.preprocess_normalize_peak)
        separation = "light"
    elif mode == "synthetic":
        processed = preprocess_synthetic(mono, BASIC_PITCH_SAMPLE_RATE, settings)
        separation = "synthetic"
    else:
        processed, separation = preprocess_full(
            mono, stereo_wav, BASIC_PITCH_SAMPLE_RATE, settings
        )

    output_path = settings.outputs_dir / f"{audio_path.stem}.preprocessed.wav"
    try:
        sf.write(str(output_path), processed, BASIC_PITCH_SAMPLE_RATE)
    except Exception as exc:
        raise AudioPreprocessError(f"Failed to write preprocessed audio: {exc}") from exc

    return PreprocessResult(
        output_path=output_path,
        stem_separation=separation,
        stereo_mode=stereo_mode,
    )
