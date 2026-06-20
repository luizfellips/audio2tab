from app.models.fretboard import FretPosition, MappedNote
from app.models.notes import NoteEvent
from app.services.fretboard import select_position
from app.services.note_mapping import map_notes_to_fretboard
from app.services.tab_generator import generate_tab, save_tab


def _mapped_note(pitch: str, start: float, end: float) -> MappedNote:
    string_number, fret = select_position(pitch)
    return MappedNote(
        note=pitch,
        start=start,
        end=end,
        position=FretPosition(string=string_number, fret=fret),
    )


def test_generate_tab_single_open_string():
    notes = [_mapped_note("E4", 0.0, 0.5)]

    tab = generate_tab(notes)

    assert tab == (
        "e|----0\n"
        "B|-----\n"
        "G|-----\n"
        "D|-----\n"
        "A|-----\n"
        "E|-----\n"
    )


def test_generate_tab_matches_expected_sequence_on_e_string():
    notes = map_notes_to_fretboard([
        NoteEvent(pitch="E4", start=0.0, end=0.5),
        NoteEvent(pitch="G4", start=0.5, end=1.0),
        NoteEvent(pitch="A4", start=1.0, end=1.5),
    ])[0]

    tab = generate_tab(notes)

    assert tab.splitlines()[0] == "e|----0----3----5"
    assert tab.splitlines()[1] == "B|---------------"


def test_generate_tab_supports_multi_digit_frets():
    notes = [
        MappedNote(
            note="C6",
            start=0.0,
            end=0.5,
            position=FretPosition(string=1, fret=10),
        )
    ]

    tab = generate_tab(notes)

    assert tab.splitlines()[0] == "e|----10"
    assert tab.splitlines()[1] == "B|------"


def test_generate_tab_empty_notes():
    tab = generate_tab([])

    assert tab.splitlines() == ["e|", "B|", "G|", "D|", "A|", "E|"]


def test_save_tab_writes_file(tmp_path):
    notes = [_mapped_note("E4", 0.0, 0.5)]
    output_path = tmp_path / "song.tab"

    save_tab(notes, output_path)

    assert output_path.read_text() == generate_tab(notes)
