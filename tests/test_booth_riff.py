"""Regression test: Booth by the Window full pitch transcript."""

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.services.note_cleaner import clean_notes

FULL_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "booth_full_raw_notes.json"
RIFF_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "booth_riff_raw_notes.json"

# User ground truth — full Booth transcription (~62 notes)
BOOTH_FULL_TRANSCRIPT = [
    "G3",
    "D#4",
    "D4",
    "D#4",
    "A#4",
    "D4",
    "D#4",
    "A#4",
    "G4",
    "C3",
    "D#4",
    "A#4",
    "C3",
    "D4",
    "A#4",
    "F4",
    "G#3",
    "D#4",
    "D5",
    "D#4",
    "A#4",
    "D#4",
    "G4",
    "D#5",
    "F5",
    "G5",
    "D5",
    "A#4",
    "F4",
    "D#4",
    "D4",
    "A#3",
    "C4",
    "G4",
    "D5",
    "D#4",
    "A#4",
    "D4",
    "D#4",
    "A#4",
    "G4",
    "C3",
    "D#4",
    "A#4",
    "C3",
    "D4",
    "A#4",
    "F4",
    "C3",
    "G4",
    "D5",
    "D#4",
    "A#4",
    "D4",
    "D#4",
    "A#4",
    "G4",
    "C3",
    "D#4",
    "A#4",
    "C3",
    "D4",
]


@pytest.fixture
def booth_full_raw_notes() -> list[NoteEvent]:
    payload = json.loads(FULL_FIXTURE.read_text(encoding="utf-8"))
    return [NoteEvent(**item) for item in payload]


@pytest.fixture
def booth_riff_raw_notes() -> list[NoteEvent]:
    payload = json.loads(RIFF_FIXTURE.read_text(encoding="utf-8"))
    return [NoteEvent(**item) for item in payload]


@pytest.fixture
def riff_settings() -> Settings:
    return Settings(
        melody_extraction_mode="onset",
        onset_cluster_sec=0.10,
        harmonic_fold_enabled=True,
        weak_note_amplitude_cap=0.36,
        guitar_min_midi=40,
        guitar_max_midi=88,
        apply_guitar_range_filter=True,
        merge_same_pitch_max_gap_sec=0.0,
        enforce_monophonic=False,
        semitone_shimmer_collapse=False,
        min_note_amplitude=0.0,
        min_note_velocity=1,
        min_note_duration_sec=0.0,
        same_pitch_repeat_gap_sec=0.22,
    )


def test_booth_full_transcript(booth_full_raw_notes, riff_settings):
    cleaned, _ = clean_notes(booth_full_raw_notes, riff_settings)
    pitch_sequence = [note.pitch for note in cleaned[: len(BOOTH_FULL_TRANSCRIPT)]]

    assert pitch_sequence == BOOTH_FULL_TRANSCRIPT, _format_pitch_diff(
        BOOTH_FULL_TRANSCRIPT,
        pitch_sequence,
    )


def test_booth_riff_fixture_still_matches_opening(booth_riff_raw_notes, riff_settings):
    cleaned, _ = clean_notes(booth_riff_raw_notes, riff_settings)
    pitch_sequence = [note.pitch for note in cleaned[:16]]

    assert pitch_sequence == BOOTH_FULL_TRANSCRIPT[:16]


def _format_pitch_diff(expected: list[str], got: list[str]) -> str:
    lines = ["Pitch sequence mismatch:"]
    for index, (exp, actual) in enumerate(zip(expected, got)):
        if exp != actual:
            lines.append(f"  [{index}] expected {exp}, got {actual}")
    if len(got) < len(expected):
        lines.append(f"  missing {len(expected) - len(got)} note(s) at tail")
    elif len(got) > len(expected):
        lines.append(f"  extra tail: {' '.join(got[len(expected):])}")
    return "\n".join(lines)
