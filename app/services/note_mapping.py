import json
from pathlib import Path

from app.core.config import Settings
from app.models.fretboard import FretPosition, MappedNote
from app.models.notes import NoteEvent
from app.services.fretboard import FretboardMappingError, select_position


def map_notes_to_fretboard(
    notes: list[NoteEvent],
    settings: Settings | None = None,
) -> tuple[list[MappedNote], list[str]]:
    max_fret = settings.max_fret if settings else 24
    mapped: list[MappedNote] = []
    skipped: list[str] = []
    previous_position: tuple[int, int] | None = None

    for note in notes:
        try:
            string_number, fret = select_position(
                note.pitch,
                previous=previous_position,
                max_fret=max_fret,
                preferred_max_fret_string1=(
                    settings.preferred_max_fret_string1 if settings else 12
                ),
            )
        except FretboardMappingError:
            skipped.append(note.pitch)
            continue

        previous_position = (string_number, fret)
        mapped.append(
            MappedNote(
                note=note.pitch,
                start=note.start,
                end=note.end,
                position=FretPosition(string=string_number, fret=fret),
            )
        )

    return mapped, skipped


def save_mapped_notes_json(notes: list[MappedNote], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [note.model_dump() for note in notes]
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path
