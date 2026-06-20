from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Audio2Tab"
    samples_dir: Path = Path("samples")
    outputs_dir: Path = Path("outputs")
    frontend_dir: Path = Path("frontend")
    max_upload_mb: int = 50
    max_fret: int = 24
    basic_pitch_model_path: Path | None = None
    guitar_min_frequency_hz: float = 80.0
    guitar_max_frequency_hz: float = 1400.0
    guitar_min_midi: int = 40   # E2
    guitar_max_midi: int = 88   # E6
    basic_pitch_onset_threshold: float = 0.65
    basic_pitch_frame_threshold: float = 0.45
    basic_pitch_min_note_length_ms: float = 150.0
    basic_pitch_melodia_trick: bool = True
    basic_pitch_multiple_pitch_bends: bool = False
    apply_guitar_range_filter: bool = True
    merge_same_pitch_max_gap_sec: float = 0.05
    enforce_monophonic: bool = False
    min_note_velocity: int = 1
    min_note_amplitude: float = 0.0
    min_note_duration_sec: float = 0.0
    audio_rms_threshold: float = 0.0
    max_melodic_jump_semitones: int = 24
    short_note_max_duration_sec: float = 0.0
    tight_gap_sec: float = 0.25
    isolated_note_max_duration_sec: float = 0.0
    isolated_note_min_gap_sec: float = 0.70
    tab_columns_per_second: float = 8.0
    tab_min_column_gap: int = 2
    tab_max_column_gap: int = 24
    # Preprocessing: off (default) | light (normalize only) | full (hpss/demucs — Suno mixes only)
    preprocess_mode: str = "off"
    enable_audio_preprocessing: bool = False
    enable_hpss: bool = False
    enable_stem_separation: bool = False
    stereo_mode: str = "mono"
    preprocess_highpass_hz: float = 70.0
    preprocess_normalize_peak: float = 0.95
    monophonic_mode: str = "melody"
    preferred_max_fret_string1: int = 12
    # clean = DI guitar; synthetic = Suno / AI-generated mixes
    transcription_profile: str = "clean"
    harmonic_fold_enabled: bool = False
    harmonic_fold_unpaired_octaves: bool = False
    semitone_shimmer_collapse: bool = False
    semitone_shimmer_window_sec: float = 0.20
    # Drop weak notes (amp below cap) when a much stronger note overlaps in time
    weak_note_amplitude_cap: float = 0.0
    # onset = one note per attack cluster (best for riffs); overlap = legacy monophonic; none = skip
    melody_extraction_mode: str = "onset"
    onset_cluster_sec: float = 0.10
    # Split onset cluster when a new pitch class appears above this amplitude (phone riffs)
    onset_cluster_split_min_amplitude: float = 0.0
    # Correct Basic Pitch sharp bias on compressed audio (F#→F, G#→D context)
    semitone_flat_bias: bool = False
    # Collapse rapid same-pitch re-attacks after onset extraction (Suno shimmer)
    same_pitch_repeat_gap_sec: float = 0.22
    # Merge consecutive same pitch-class notes when starts are within this gap (phone dedup)
    merge_consecutive_same_pitch_max_gap_sec: float = 0.0
    # off = keep Basic Pitch note lengths; legato = extend each note toward the next attack
    note_duration_mode: str = "legato"
    note_legato_gap_sec: float = 0.02
    note_max_duration_sec: float = 0.55
    # Silence between note end and next start in cleaned JSON (trim first, shift only if needed)
    note_onset_spacing_sec: float = 0.02
    # Minimum seconds between consecutive note starts (0 = keep Basic Pitch onsets)
    note_min_inter_onset_sec: float = 0.0
    # Shift all notes so the first attack starts at 0 (phone voice notes with long intro)
    trim_leading_silence: bool = False
    # Keep only the strongest note when multiple onsets fall within this window (seconds)
    simultaneous_onset_window_sec: float = 0.0

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=ENV_FILE)


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return Settings(_env_file=ENV_FILE)


# Backward-compatible module singleton (reload via reload_settings()).
settings = get_settings()
