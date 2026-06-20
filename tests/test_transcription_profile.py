from app.core.config import Settings
from app.services.transcription_profile import resolve_transcription_settings


def test_synthetic_profile_enables_harmonic_correction():
    settings = Settings(transcription_profile="synthetic")
    effective = resolve_transcription_settings(settings)

    assert effective.harmonic_fold_enabled is True
    assert effective.basic_pitch_melodia_trick is True
    assert effective.preprocess_mode == "synthetic"


def test_clean_profile_leaves_settings_unchanged():
    settings = Settings(
        transcription_profile="clean",
        harmonic_fold_enabled=False,
        basic_pitch_onset_threshold=0.35,
    )
    effective = resolve_transcription_settings(settings)

    assert effective.harmonic_fold_enabled is False
    assert effective.basic_pitch_onset_threshold == 0.35
