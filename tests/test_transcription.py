from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.services.transcription import TranscriptionError, transcribe_audio, transcribe_audio_to_midi


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        samples_dir=tmp_path / "samples",
        outputs_dir=tmp_path / "outputs",
    )


def test_transcribe_audio_converts_note_events(test_settings, tmp_path):
    audio_path = test_settings.samples_dir / "song.mp3"
    test_settings.samples_dir.mkdir(parents=True)
    audio_path.write_bytes(b"ID3" + b"\x00" * 128)

    mock_midi = MagicMock()

    def write_midi(path: str) -> None:
        Path(path).write_bytes(b"MThd" + b"\x00" * 12)

    mock_midi.write.side_effect = write_midi
    note_events = [(0.52, 0.88, 64, 0.75, None)]

    with patch("basic_pitch.inference.predict", return_value=(None, mock_midi, note_events)):
        midi_path, notes = transcribe_audio(audio_path, test_settings)

    assert midi_path == test_settings.outputs_dir / "song.mid"
    assert len(notes) == 1
    assert notes[0].pitch == "E4"
    assert notes[0].amplitude == 0.75
    assert notes[0].velocity == 95


def test_transcribe_audio_to_midi_writes_file(test_settings, tmp_path):
    audio_path = test_settings.samples_dir / "song.mp3"
    test_settings.samples_dir.mkdir(parents=True)
    audio_path.write_bytes(b"ID3" + b"\x00" * 128)

    mock_midi = MagicMock()

    def write_midi(path: str) -> None:
        Path(path).write_bytes(b"MThd" + b"\x00" * 12)

    mock_midi.write.side_effect = write_midi

    with patch("basic_pitch.inference.predict", return_value=(None, mock_midi, [])):
        result = transcribe_audio_to_midi(audio_path, test_settings)

    assert result == test_settings.outputs_dir / "song.mid"
    mock_midi.write.assert_called_once_with(str(result))


def test_transcribe_audio_to_midi_raises_on_failure(test_settings):
    audio_path = test_settings.samples_dir / "song.mp3"
    test_settings.samples_dir.mkdir(parents=True)
    audio_path.write_bytes(b"ID3" + b"\x00" * 128)

    with (
        patch("basic_pitch.inference.predict", side_effect=RuntimeError("model failed")),
        pytest.raises(TranscriptionError, match="Failed to transcribe audio"),
    ):
        transcribe_audio_to_midi(audio_path, test_settings)
