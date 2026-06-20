from pathlib import Path

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.utils.pitch import midi_number_to_pitch, pitch_to_midi


class TranscriptionError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _convert_note_events(
    note_events: list[tuple[float, float, int, float, object | None]],
) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for event in note_events:
        start, end, pitch_midi, amplitude = event[:4]
        velocity = max(1, min(127, int(round(float(amplitude) * 127))))
        notes.append(
            NoteEvent(
                pitch=midi_number_to_pitch(int(pitch_midi)),
                start=round(float(start), 2),
                end=round(float(end), 2),
                velocity=velocity,
                amplitude=round(float(amplitude), 4),
            )
        )
    notes.sort(key=lambda note: (note.start, note.pitch))
    return notes


def transcribe_audio(
    audio_path: Path,
    settings: Settings,
) -> tuple[Path, list[NoteEvent]]:
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    settings.ensure_directories()
    midi_path = settings.outputs_dir / f"{audio_path.stem}.mid"

    try:
        _, midi_data, note_events = predict(
            str(audio_path),
            model_or_model_path=settings.basic_pitch_model_path or ICASSP_2022_MODEL_PATH,
            minimum_frequency=settings.guitar_min_frequency_hz,
            maximum_frequency=settings.guitar_max_frequency_hz,
            onset_threshold=settings.basic_pitch_onset_threshold,
            frame_threshold=settings.basic_pitch_frame_threshold,
            minimum_note_length=settings.basic_pitch_min_note_length_ms,
            melodia_trick=settings.basic_pitch_melodia_trick,
            multiple_pitch_bends=settings.basic_pitch_multiple_pitch_bends,
        )
        midi_data.write(str(midi_path))
        raw_notes = _convert_note_events(note_events)
    except Exception as exc:
        raise TranscriptionError(f"Failed to transcribe audio: {exc}") from exc

    if not midi_path.exists():
        raise TranscriptionError("MIDI file was not created")

    return midi_path, raw_notes


def transcribe_audio_to_midi(audio_path: Path, settings: Settings) -> Path:
    """Backward-compatible helper that only returns the MIDI path."""
    midi_path, _ = transcribe_audio(audio_path, settings)
    return midi_path
