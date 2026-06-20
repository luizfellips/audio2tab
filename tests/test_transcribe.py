import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.models.notes import NoteEvent
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_settings = Settings(
        samples_dir=tmp_path / "samples",
        outputs_dir=tmp_path / "outputs",
        enable_audio_preprocessing=False,
    )
    monkeypatch.setattr(
        "app.api.routes.transcribe.reload_settings",
        lambda: test_settings,
    )

    def fake_transcribe(audio_path, settings):
        settings.ensure_directories()
        midi_path = settings.outputs_dir / f"{audio_path.stem}.mid"
        create_minimal_midi(midi_path)
        notes = [
            NoteEvent(pitch="E4", start=0.52, end=0.88, velocity=80, amplitude=0.8),
        ]
        return midi_path, notes

    monkeypatch.setattr(
        "app.api.routes.transcribe.transcribe_audio",
        fake_transcribe,
    )

    with TestClient(create_app()) as test_client:
        yield test_client, test_settings


def create_minimal_midi(path):
    import pretty_midi

    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes.append(
        pretty_midi.Note(velocity=80, pitch=64, start=0.52, end=0.88)
    )
    midi.instruments.append(instrument)
    midi.write(str(path))


def minimal_mp3_bytes() -> bytes:
    return b"ID3" + b"\x00" * 128


def test_transcribe_accepts_valid_mp3(client):
    test_client, test_settings = client
    response = test_client.post(
        "/transcribe",
        files={"audio_file": ("song.mp3", minimal_mp3_bytes(), "audio/mpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "status": "received",
        "midi_file": str(test_settings.outputs_dir / "song.mid"),
        "notes_file": str(test_settings.outputs_dir / "song.notes.json"),
        "raw_notes_file": str(test_settings.outputs_dir / "song.raw.notes.json"),
        "raw_note_count": 1,
        "note_count": 1,
        "filtered_note_count": 0,
        "mapped_note_count": 1,
        "skipped_notes": [],
        "positions_file": str(test_settings.outputs_dir / "song.positions.json"),
        "tab_file": str(test_settings.outputs_dir / "song.tab"),
        "preprocessed_file": str(test_settings.samples_dir / "song.mp3"),
        "stem_separation": "none",
        "stereo_mode": "mono",
        "transcription_profile": "clean",
    }
    assert (test_settings.samples_dir / "song.mp3").exists()
    assert (test_settings.outputs_dir / "song.mid").exists()
    assert (test_settings.outputs_dir / "song.notes.json").exists()
    assert (test_settings.outputs_dir / "song.positions.json").exists()
    assert (test_settings.outputs_dir / "song.tab").exists()


def test_transcribe_rejects_non_mp3_extension(client):
    test_client, _ = client
    response = test_client.post(
        "/transcribe",
        files={"audio_file": ("song.wav", b"RIFF", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only MP3 files are supported"


def test_transcribe_rejects_invalid_content_type(client):
    test_client, _ = client
    response = test_client.post(
        "/transcribe",
        files={"audio_file": ("song.mp3", minimal_mp3_bytes(), "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid content type for MP3 upload"


def test_transcribe_rejects_empty_file(client):
    test_client, _ = client
    response = test_client.post(
        "/transcribe",
        files={"audio_file": ("song.mp3", b"", "audio/mpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty"


def test_transcribe_rejects_invalid_mp3_signature(client):
    test_client, _ = client
    response = test_client.post(
        "/transcribe",
        files={"audio_file": ("song.mp3", b"not-an-mp3-file", "audio/mpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File does not appear to be a valid MP3"


def test_transcribe_rejects_missing_file(client):
    test_client, _ = client
    response = test_client.post("/transcribe")

    assert response.status_code == 422
