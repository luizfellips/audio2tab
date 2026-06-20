import pytest

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.services.harmonic_correction import (
    apply_harmonic_corrections,
    collapse_semitone_shimmer,
    fold_harmonic_ghosts,
    fold_unpaired_octave_errors,
)


@pytest.fixture
def synthetic_settings():
    return Settings(
        harmonic_fold_enabled=True,
        semitone_shimmer_collapse=True,
        semitone_shimmer_window_sec=0.20,
        guitar_min_midi=40,
        guitar_max_midi=88,
        apply_guitar_range_filter=False,
        enforce_monophonic=False,
        min_note_amplitude=0.0,
        min_note_velocity=0,
        min_note_duration_sec=0.0,
    )


def test_fold_harmonic_ghosts_drops_octave_double(synthetic_settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.5, velocity=90, amplitude=0.9),
        NoteEvent(pitch="E5", start=0.05, end=0.45, velocity=70, amplitude=0.6),
    ]

    folded = fold_harmonic_ghosts(notes, synthetic_settings)

    assert len(folded) == 1
    assert folded[0].pitch == "E4"


def test_collapse_semitone_shimmer_merges_alternating_pitches(synthetic_settings):
    notes = [
        NoteEvent(pitch="D4", start=0.0, end=0.12, velocity=80, amplitude=0.7),
        NoteEvent(pitch="D#4", start=0.13, end=0.25, velocity=75, amplitude=0.5),
        NoteEvent(pitch="D4", start=0.26, end=0.38, velocity=70, amplitude=0.6),
    ]

    collapsed = collapse_semitone_shimmer(notes, synthetic_settings)

    assert len(collapsed) == 1
    assert collapsed[0].pitch == "D4"
    assert collapsed[0].end == 0.38


def test_fold_unpaired_octave_errors(synthetic_settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.4, velocity=80, amplitude=0.8),
        NoteEvent(pitch="E5", start=0.5, end=0.9, velocity=80, amplitude=0.8),
    ]
    settings = synthetic_settings.model_copy(update={"harmonic_fold_unpaired_octaves": True})

    folded = fold_unpaired_octave_errors(notes, settings)

    assert folded[1].pitch == "E4"


def test_apply_harmonic_corrections_runs_full_chain(synthetic_settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.5, velocity=90, amplitude=0.9),
        NoteEvent(pitch="E5", start=0.05, end=0.45, velocity=70, amplitude=0.6),
        NoteEvent(pitch="D4", start=0.55, end=0.65, velocity=60, amplitude=0.5),
        NoteEvent(pitch="D#4", start=0.66, end=0.76, velocity=60, amplitude=0.4),
    ]

    corrected = apply_harmonic_corrections(notes, synthetic_settings)

    assert all(note.pitch != "E5" for note in corrected)
    assert len(corrected) <= 3
