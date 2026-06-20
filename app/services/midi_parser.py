import json
from pathlib import Path

import pretty_midi

from app.models.notes import NoteEvent
from app.utils.pitch import midi_number_to_pitch


class MidiParseError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def parse_midi(midi_path: Path) -> list[NoteEvent]:
    if not midi_path.exists():
        raise MidiParseError(f"MIDI file not found: {midi_path}")

    try:
        midi_data = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception as exc:
        raise MidiParseError(f"Failed to read MIDI file: {exc}") from exc

    notes: list[NoteEvent] = []
    for instrument in midi_data.instruments:
        if instrument.is_drum:
            continue

        for note in instrument.notes:
            notes.append(
                NoteEvent(
                    pitch=midi_number_to_pitch(note.pitch),
                    start=round(note.start, 2),
                    end=round(note.end, 2),
                    velocity=note.velocity,
                )
            )

    notes.sort(key=lambda event: (event.start, event.pitch))
    return notes


def parse_midi_to_json(midi_path: Path) -> list[dict]:
    return [note.model_dump() for note in parse_midi(midi_path)]


def save_notes_json(notes: list[NoteEvent], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [note.model_dump() for note in notes]
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path
