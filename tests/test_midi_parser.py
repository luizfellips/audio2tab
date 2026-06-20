import json
from pathlib import Path

import pretty_midi
import pytest

from app.models.notes import NoteEvent
from app.services.midi_parser import (
    MidiParseError,
    parse_midi,
    parse_midi_to_json,
    save_notes_json,
)


def create_test_midi(path: Path) -> None:
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)

    # E4 (MIDI 64): 0.52s - 0.88s
    instrument.notes.append(
        pretty_midi.Note(velocity=80, pitch=64, start=0.52, end=0.88)
    )
    # C4 (MIDI 60): 1.00s - 1.50s
    instrument.notes.append(
        pretty_midi.Note(velocity=80, pitch=60, start=1.0, end=1.5)
    )

    midi.instruments.append(instrument)
    midi.write(str(path))


def test_parse_midi_extracts_notes_with_timing(tmp_path):
    midi_path = tmp_path / "test.mid"
    create_test_midi(midi_path)

    notes = parse_midi(midi_path)

    assert notes == [
        NoteEvent(pitch="E4", start=0.52, end=0.88, velocity=80, amplitude=0.0),
        NoteEvent(pitch="C4", start=1.0, end=1.5, velocity=80, amplitude=0.0),
    ]


def test_parse_midi_to_json_matches_target_format(tmp_path):
    midi_path = tmp_path / "test.mid"
    create_test_midi(midi_path)

    payload = parse_midi_to_json(midi_path)

    assert payload == [
        {"pitch": "E4", "start": 0.52, "end": 0.88, "velocity": 80, "amplitude": 0.0},
        {"pitch": "C4", "start": 1.0, "end": 1.5, "velocity": 80, "amplitude": 0.0},
    ]


def test_save_notes_json_writes_file(tmp_path):
    notes = [NoteEvent(pitch="E4", start=0.52, end=0.88, velocity=80)]
    output_path = tmp_path / "song.notes.json"

    save_notes_json(notes, output_path)

    assert json.loads(output_path.read_text()) == [
        {"pitch": "E4", "start": 0.52, "end": 0.88, "velocity": 80, "amplitude": 0.0},
    ]


def test_parse_midi_raises_for_missing_file(tmp_path):
    with pytest.raises(MidiParseError, match="MIDI file not found"):
        parse_midi(tmp_path / "missing.mid")


def test_parse_midi_raises_for_invalid_file(tmp_path):
    bad_midi = tmp_path / "bad.mid"
    bad_midi.write_text("not midi")

    with pytest.raises(MidiParseError, match="Failed to read MIDI file"):
        parse_midi(bad_midi)


def test_parse_midi_skips_drum_tracks(tmp_path):
    midi = pretty_midi.PrettyMIDI()
    drums = pretty_midi.Instrument(program=0, is_drum=True)
    drums.notes.append(pretty_midi.Note(velocity=80, pitch=36, start=0.0, end=0.5))
    midi.instruments.append(drums)

    midi_path = tmp_path / "drums.mid"
    midi.write(str(midi_path))

    assert parse_midi(midi_path) == []
