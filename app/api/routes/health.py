from fastapi import APIRouter

from app.core.config import ENV_FILE, get_settings, reload_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/config")
def config_check() -> dict[str, float | int | str | bool]:
    """Show active transcription settings (reloads .env on each request)."""
    reload_settings()
    settings = get_settings()
    return {
        "env_file": str(ENV_FILE),
        "env_file_exists": ENV_FILE.exists(),
        "preprocess_mode": settings.preprocess_mode,
        "enable_audio_preprocessing": settings.enable_audio_preprocessing,
        "enable_hpss": settings.enable_hpss,
        "enable_stem_separation": settings.enable_stem_separation,
        "stereo_mode": settings.stereo_mode,
        "transcription_profile": settings.transcription_profile,
        "harmonic_fold_enabled": settings.harmonic_fold_enabled,
        "enforce_monophonic": settings.enforce_monophonic,
        "basic_pitch_onset_threshold": settings.basic_pitch_onset_threshold,
        "basic_pitch_frame_threshold": settings.basic_pitch_frame_threshold,
        "basic_pitch_min_note_length_ms": settings.basic_pitch_min_note_length_ms,
        "basic_pitch_melodia_trick": settings.basic_pitch_melodia_trick,
        "min_note_velocity": settings.min_note_velocity,
        "min_note_amplitude": settings.min_note_amplitude,
        "min_note_duration_sec": settings.min_note_duration_sec,
        "note_duration_mode": settings.note_duration_mode,
        "note_legato_gap_sec": settings.note_legato_gap_sec,
        "note_max_duration_sec": settings.note_max_duration_sec,
        "note_onset_spacing_sec": settings.note_onset_spacing_sec,
        "note_min_inter_onset_sec": settings.note_min_inter_onset_sec,
    }
