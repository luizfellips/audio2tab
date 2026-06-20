from pathlib import Path

from pydantic import BaseModel


class TranscribeResponse(BaseModel):
    status: str
    midi_file: str
    notes_file: str
    raw_notes_file: str | None = None
    raw_note_count: int
    note_count: int
    filtered_note_count: int
    mapped_note_count: int
    skipped_notes: list[str]
    positions_file: str
    tab_file: str
    preprocessed_file: str | None = None
    stem_separation: str | None = None
    stereo_mode: str | None = None
    transcription_profile: str | None = None
