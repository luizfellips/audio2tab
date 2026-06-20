"""Transcription profiles — opt-in only via ?profile=synthetic on POST /transcribe."""

from __future__ import annotations

from app.core.config import Settings

# Profiles apply ONLY when explicitly requested. They do not run by default.
PROFILE_OVERRIDES: dict[str, dict[str, object]] = {
    "clean": {},
    "synthetic": {
        "preprocess_mode": "synthetic",
        "basic_pitch_onset_threshold": 0.45,
        "basic_pitch_frame_threshold": 0.30,
        "basic_pitch_min_note_length_ms": 90.0,
        "basic_pitch_melodia_trick": True,
        "harmonic_fold_enabled": True,
        "semitone_shimmer_collapse": True,
        "enforce_monophonic": True,
        "monophonic_mode": "melody",
    },
}


def resolve_transcription_settings(settings: Settings) -> Settings:
    profile = settings.transcription_profile.lower().strip()
    if profile == "clean":
        return settings
    overrides = PROFILE_OVERRIDES.get(profile, {})
    if not overrides:
        return settings
    return settings.model_copy(update=overrides)
