import pytest

from app.models.notes import NoteEvent
from app.services.fretboard import (
    FretboardMappingError,
    find_all_positions,
    select_position,
)
from app.services.note_mapping import map_notes_to_fretboard


def test_find_all_positions_for_e4():
    positions = find_all_positions("E4")

    assert (1, 0) in positions
    assert (2, 5) in positions
    assert all(fret <= 24 for _, fret in positions)


def test_find_all_positions_for_high_d_sharp_6():
    positions = find_all_positions("D#6")

    assert (1, 23) in positions


def test_select_position_prefers_open_string():
    string_number, fret = select_position("E4")

    assert string_number == 1
    assert fret == 0


def test_select_position_prefers_mid_neck_over_high_e_for_riffs():
    # D5 can be played high on string 1; prefer lower positions for riff-like lines
    string_number, fret = select_position("D5", preferred_max_fret_string1=12)

    assert string_number != 1 or fret <= 12


def test_select_position_is_deterministic():
    first = select_position("G3")
    second = select_position("G3")

    assert first == second == (3, 0)


def test_select_position_minimizes_hand_movement():
    # After E4 on string 1 fret 0, C4 should land nearby (B string fret 1)
    string_number, fret = select_position("C4", previous=(1, 0))

    assert string_number == 2
    assert fret == 1


def test_map_notes_to_fretboard_preserves_timing():
    notes = [
        NoteEvent(pitch="E4", start=0.52, end=0.88),
        NoteEvent(pitch="C4", start=1.0, end=1.5),
    ]

    mapped = map_notes_to_fretboard(notes)[0]

    assert mapped[0].model_dump() == {
        "note": "E4",
        "start": 0.52,
        "end": 0.88,
        "position": {"string": 1, "fret": 0},
    }
    assert mapped[1].note == "C4"
    assert mapped[1].start == 1.0
    assert mapped[1].end == 1.5
    assert mapped[1].position.string == 2
    assert mapped[1].position.fret == 1


def test_map_notes_to_fretboard_is_reproducible():
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.5),
        NoteEvent(pitch="G4", start=0.5, end=1.0),
        NoteEvent(pitch="A4", start=1.0, end=1.5),
    ]

    assert map_notes_to_fretboard(notes)[0] == map_notes_to_fretboard(notes)[0]


def test_map_notes_to_fretboard_skips_unplayable_notes():
    notes = [
        NoteEvent(pitch="E4", start=0.0, end=0.5),
        NoteEvent(pitch="C1", start=0.5, end=1.0),
        NoteEvent(pitch="G4", start=1.0, end=1.5),
    ]

    mapped, skipped = map_notes_to_fretboard(notes)

    assert len(mapped) == 2
    assert mapped[0].note == "E4"
    assert mapped[1].note == "G4"
    assert skipped == ["C1"]


def test_find_all_positions_raises_for_unplayable_note():
    with pytest.raises(FretboardMappingError, match="No playable position"):
        find_all_positions("C1")
