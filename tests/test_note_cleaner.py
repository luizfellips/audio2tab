import numpy as np
import pytest

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.services.note_cleaner import clean_notes


@pytest.fixture
def settings():
    return Settings(
        guitar_min_midi=40,
        guitar_max_midi=88,
        apply_guitar_range_filter=True,
        melody_extraction_mode="overlap",
        merge_same_pitch_max_gap_sec=0.05,
        enforce_monophonic=True,
        min_note_velocity=45,
        min_note_amplitude=0.42,
        min_note_duration_sec=0.10,
        max_melodic_jump_semitones=10,
        short_note_max_duration_sec=0.20,
        tight_gap_sec=0.25,
        isolated_note_max_duration_sec=0.14,
        isolated_note_min_gap_sec=0.70,
        audio_rms_threshold=0.010,
    )


def test_clean_notes_removes_short_low_velocity_and_out_of_range(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.50, velocity=80, amplitude=0.8),
        NoteEvent(pitch="E4", start=0.55, end=0.58, velocity=80, amplitude=0.8),  # too short
        NoteEvent(pitch="C1", start=1.0, end=1.5, velocity=80, amplitude=0.8),    # out of range
        NoteEvent(pitch="G4", start=1.0, end=1.5, velocity=20, amplitude=0.1),  # too quiet
    ]

    cleaned, filtered_count = clean_notes(notes, settings)

    assert len(cleaned) == 1
    assert cleaned[0].pitch == "E4"
    assert filtered_count == 3


def test_clean_notes_removes_low_amplitude(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.50, velocity=80, amplitude=0.8),
        NoteEvent(pitch="G4", start=1.0, end=1.5, velocity=80, amplitude=0.20),
    ]

    cleaned, filtered_count = clean_notes(notes, settings)

    assert len(cleaned) == 1
    assert cleaned[0].pitch == "E4"
    assert filtered_count == 1


def test_clean_notes_merges_same_pitch_runs(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.40, velocity=70, amplitude=0.7),
        NoteEvent(pitch="E4", start=0.42, end=0.90, velocity=90, amplitude=0.9),
    ]

    cleaned, _ = clean_notes(notes, settings)

    assert len(cleaned) == 1
    assert cleaned[0].start == 0.0
    assert cleaned[0].end == 0.9
    assert cleaned[0].velocity == 90
    assert cleaned[0].amplitude == 0.9


def test_clean_notes_enforces_monophonic_overlaps(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.8, velocity=60, amplitude=0.6),
        NoteEvent(pitch="G4", start=0.2, end=0.8, velocity=90, amplitude=0.9),
    ]

    cleaned, _ = clean_notes(notes, settings)

    assert len(cleaned) == 1
    assert cleaned[0].pitch == "G4"


def test_drop_weak_overlapped_removes_quiet_octave():
    notes = [
        NoteEvent(pitch="D#4", start=0.5, end=1.0, velocity=90, amplitude=0.75),
        NoteEvent(pitch="D5", start=0.52, end=0.65, velocity=30, amplitude=0.24),
        NoteEvent(pitch="G4", start=2.0, end=2.5, velocity=80, amplitude=0.25),
    ]
    settings = Settings(weak_note_amplitude_cap=0.32, enforce_monophonic=False)

    cleaned, _ = clean_notes(notes, settings)

    assert [note.pitch for note in cleaned] == ["D#4", "G4"]


def test_melody_mode_drops_weaker_overlapping_notes():
    settings = Settings(
        melody_extraction_mode="overlap",
        enforce_monophonic=True,
        monophonic_mode="melody",
        min_note_amplitude=0.0,
        min_note_velocity=0,
        min_note_duration_sec=0.0,
        apply_guitar_range_filter=False,
    )
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=1.0, velocity=90, amplitude=0.9),
        NoteEvent(pitch="G4", start=0.1, end=0.9, velocity=50, amplitude=0.4),
        NoteEvent(pitch="B4", start=0.2, end=0.8, velocity=40, amplitude=0.3),
    ]

    cleaned, _ = clean_notes(notes, settings)

    assert len(cleaned) == 1
    assert cleaned[0].pitch == "E4"


def test_clean_notes_keeps_non_overlapping_sequence(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.4, velocity=80, amplitude=0.8),
        NoteEvent(pitch="G4", start=0.5, end=0.9, velocity=80, amplitude=0.8),
        NoteEvent(pitch="A4", start=1.0, end=1.4, velocity=80, amplitude=0.8),
    ]

    cleaned, filtered_count = clean_notes(notes, settings)

    assert filtered_count == 0
    assert [note.pitch for note in cleaned] == ["E4", "G4", "A4"]


def test_clean_notes_removes_melodic_outliers(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.50, velocity=80, amplitude=0.8),
        NoteEvent(pitch="C6", start=0.52, end=0.65, velocity=80, amplitude=0.8),
        NoteEvent(pitch="G4", start=1.0, end=1.5, velocity=80, amplitude=0.8),
    ]

    cleaned, _ = clean_notes(notes, settings)

    assert [note.pitch for note in cleaned] == ["E4", "G4"]


def test_clean_notes_removes_isolated_spikes(settings):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.50, velocity=80, amplitude=0.8),
        NoteEvent(pitch="A4", start=2.0, end=2.10, velocity=80, amplitude=0.8),
        NoteEvent(pitch="G4", start=3.5, end=4.0, velocity=80, amplitude=0.8),
    ]

    cleaned, _ = clean_notes(notes, settings)

    assert [note.pitch for note in cleaned] == ["E4", "G4"]


def test_legato_extends_note_to_next_onset():
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.12, velocity=80, amplitude=0.8),
        NoteEvent(pitch="G4", start=0.50, end=0.62, velocity=80, amplitude=0.8),
    ]
    settings = Settings(
        melody_extraction_mode="none",
        enforce_monophonic=False,
        note_duration_mode="legato",
        note_legato_gap_sec=0.02,
        note_max_duration_sec=0.55,
        apply_guitar_range_filter=False,
        min_note_amplitude=0.0,
        min_note_velocity=0,
        min_note_duration_sec=0.0,
    )

    cleaned, _ = clean_notes(notes, settings)

    assert cleaned[0].pitch == "E4"
    assert cleaned[0].end == pytest.approx(0.48, abs=0.01)
    assert cleaned[1].end == pytest.approx(0.62, abs=0.01)


def test_normalize_timing_trims_overlap_before_shifting():
    notes = [
        NoteEvent(pitch="G3", start=0.26, end=0.46, velocity=80, amplitude=0.8),
        NoteEvent(pitch="D#4", start=0.38, end=0.58, velocity=80, amplitude=0.8),
    ]
    settings = Settings(
        melody_extraction_mode="none",
        enforce_monophonic=False,
        note_duration_mode="off",
        note_onset_spacing_sec=0.03,
        note_min_inter_onset_sec=0.0,
        apply_guitar_range_filter=False,
        min_note_amplitude=0.0,
        min_note_velocity=0,
    )

    cleaned, _ = clean_notes(notes, settings)

    assert cleaned[0].start == pytest.approx(0.26, abs=0.01)
    assert cleaned[0].end == pytest.approx(0.35, abs=0.01)
    assert cleaned[1].start == pytest.approx(0.38, abs=0.01)
    assert cleaned[1].start >= cleaned[0].end + 0.03


def test_min_inter_onset_separates_attack_times():
    notes = [
        NoteEvent(pitch="G3", start=0.26, end=0.46, velocity=80, amplitude=0.8),
        NoteEvent(pitch="D#4", start=0.38, end=0.58, velocity=80, amplitude=0.8),
    ]
    settings = Settings(
        melody_extraction_mode="none",
        enforce_monophonic=False,
        note_duration_mode="off",
        note_onset_spacing_sec=0.02,
        note_min_inter_onset_sec=0.18,
        apply_guitar_range_filter=False,
        min_note_amplitude=0.0,
        min_note_velocity=0,
    )

    cleaned, _ = clean_notes(notes, settings)

    assert cleaned[1].start == pytest.approx(0.44, abs=0.01)
    assert cleaned[1].start - cleaned[0].start >= 0.18


def test_clean_notes_gates_by_audio_energy(settings, tmp_path, monkeypatch):
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.50, velocity=80, amplitude=0.8),
        NoteEvent(pitch="G4", start=1.0, end=1.5, velocity=80, amplitude=0.8),
    ]
    audio_path = tmp_path / "song.mp3"
    audio_path.write_bytes(b"ID3" + b"\x00" * 128)

    sample_rate = 22050
    hop_length = 512
    frame_count = 200
    rms = np.zeros(frame_count)
    rms[0:20] = 0.05
    rms[80:120] = 0.001

    frame_times = np.linspace(0, 4.0, frame_count)

    def fake_load(path, sr, mono):
        return np.zeros(sample_rate * 4), sample_rate

    def fake_rms(y, hop_length):
        return rms.reshape(1, -1)

    def fake_frames_to_time(frames, sr, hop_length):
        return frame_times

    monkeypatch.setattr("app.services.note_cleaner.librosa.load", fake_load)
    monkeypatch.setattr("app.services.note_cleaner.librosa.feature.rms", fake_rms)
    monkeypatch.setattr(
        "app.services.note_cleaner.librosa.frames_to_time",
        fake_frames_to_time,
    )

    cleaned, _ = clean_notes(notes, settings, audio_path=audio_path)

    assert [note.pitch for note in cleaned] == ["E4"]
