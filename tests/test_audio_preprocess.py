import numpy as np
import pytest

from app.core.config import Settings
from app.services.audio_preprocess import (
    _to_mono,
    prepare_audio_for_transcription,
    resolve_preprocess_mode,
)


def test_to_mono_louder_channel():
    left = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    right = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    stereo = np.stack([left, right])

    assert np.array_equal(_to_mono(stereo, "louder_channel"), right)
    assert np.array_equal(_to_mono(stereo, "left"), left)


def test_resolve_preprocess_mode_off_by_default():
    settings = Settings()
    assert resolve_preprocess_mode(settings) == "off"


def test_resolve_preprocess_mode_legacy_light():
    settings = Settings(
        enable_audio_preprocessing=True,
        enable_hpss=False,
        preprocess_mode="off",
    )
    assert resolve_preprocess_mode(settings) == "light"


def test_prepare_audio_off_returns_original(tmp_path):
    audio_path = tmp_path / "song.mp3"
    audio_path.write_bytes(b"ID3" + b"\x00" * 128)
    settings = Settings(outputs_dir=tmp_path / "outputs", preprocess_mode="off")

    result = prepare_audio_for_transcription(audio_path, settings)

    assert result.output_path == audio_path
    assert result.stem_separation == "none"
