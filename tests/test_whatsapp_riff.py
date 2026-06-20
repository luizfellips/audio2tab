"""Regression test: WhatsApp phone riff pitch sequence."""

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.services.note_cleaner import clean_notes
from app.utils.pitch import pitch_class

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "whatsapp_riff_raw_notes.json"

# Ground truth from user (pitch classes, octaves ignored)
WHATSAPP_RIFF_TRANSCRIPT = [
    "G",
    "G#",
    "A#",
    "B",
    "D",
    "D#",
    "E",
    "B",
    "A#",
    "E",
    "D#",
    "C#",
    "B",
    "F",
    "G",
    "G#",
    "D",
    "G",
    "G#",
    "A#",
    "B",
    "D",
    "D#",
    "E",
    "B",
    "A#",
    "B",
    "A#",
    "G",
    "G#",
]

MIN_SUBSEQUENCE_MATCH = 25
MAX_CLEANED_NOTES = 70


@pytest.fixture
def whatsapp_raw_notes() -> list[NoteEvent]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [NoteEvent(**item) for item in payload]


@pytest.fixture
def phone_settings() -> Settings:
    return Settings(
        melody_extraction_mode="onset",
        onset_cluster_sec=0.10,
        onset_cluster_split_min_amplitude=0.28,
        harmonic_fold_enabled=True,
        weak_note_amplitude_cap=0.0,
        semitone_flat_bias=True,
        enforce_monophonic=False,
        min_note_amplitude=0.25,
        same_pitch_repeat_gap_sec=0.15,
        merge_consecutive_same_pitch_max_gap_sec=0.45,
        trim_leading_silence=True,
        simultaneous_onset_window_sec=0.0,
        note_duration_mode="off",
        note_onset_spacing_sec=0.0,
        note_min_inter_onset_sec=0.0,
        merge_same_pitch_max_gap_sec=0.0,
        apply_guitar_range_filter=True,
        guitar_min_midi=40,
        guitar_max_midi=88,
    )


def _subsequence_match(expected: list[str], got: list[str]) -> int:
    index = 0
    for pitch in got:
        if index < len(expected) and pitch == expected[index]:
            index += 1
    return index


def test_whatsapp_riff_matches_expected_subsequence(whatsapp_raw_notes, phone_settings):
    cleaned, _ = clean_notes(whatsapp_raw_notes, phone_settings)
    pitch_sequence = [pitch_class(note.pitch) for note in cleaned]
    matched = _subsequence_match(WHATSAPP_RIFF_TRANSCRIPT, pitch_sequence)

    assert matched >= MIN_SUBSEQUENCE_MATCH, _format_pitch_diff(
        WHATSAPP_RIFF_TRANSCRIPT,
        pitch_sequence,
        matched,
    )
    assert len(cleaned) <= MAX_CLEANED_NOTES, (
        f"Too many notes after cleanup: {len(cleaned)} (max {MAX_CLEANED_NOTES}). "
        f"Sequence: {' '.join(pitch_sequence)}"
    )


def test_whatsapp_riff_opening_phrase(whatsapp_raw_notes, phone_settings):
    cleaned, _ = clean_notes(whatsapp_raw_notes, phone_settings)
    pitch_sequence = [pitch_class(note.pitch) for note in cleaned]
    opening = WHATSAPP_RIFF_TRANSCRIPT[:6]

    assert _subsequence_match(opening, pitch_sequence) == len(opening)


def _format_pitch_diff(expected: list[str], got: list[str], matched: int) -> str:
    lines = [
        f"Subsequence match {matched}/{len(expected)} (need {MIN_SUBSEQUENCE_MATCH})",
        f"Expected: {' '.join(expected)}",
        f"Got:      {' '.join(got)}",
    ]
    return "\n".join(lines)
