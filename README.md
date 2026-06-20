# Audio2Tab

Convert MP3 audio into guitar tablature using AI.

**Status:** MVP complete with web frontend for MP3 upload and tab preview.

## Pipeline (roadmap)

```
MP3 → Basic Pitch → MIDI → Notes → Fretboard → TAB
```

| Phase | Feature |
|-------|---------|
| 1 | Project foundation |
| 2 | `POST /transcribe` — MP3 upload |
| 3 | Audio → MIDI via Basic Pitch |
| 4 | MIDI note extraction |
| 5 | Note-to-fretboard mapping |
| 6 | Tablature generation |
| 7 | Web frontend (this release) |

## Prerequisites

- Python 3.12 (required for Basic Pitch + ONNX runtime on Linux)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker & Docker Compose (optional)
- `libsndfile1` system library for audio I/O (included in Docker image)

On Ubuntu/Debian locally:

```bash
sudo apt-get install libsndfile1
```

## Local development

```bash
# Install dependencies
uv sync --all-groups

# Run the API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
uv run pytest
```

Copy environment defaults:

```bash
cp .env.example .env
```

Regenerate `requirements.txt` after dependency changes:

```bash
uv export --no-hashes --no-editable --no-dev -o requirements.txt
```

### Verify

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Web UI

Open [http://localhost:8000](http://localhost:8000) after starting the server. The UI supports drag-and-drop MP3 upload, **Play/Stop tab playback** (Web Audio synthesis from mapped positions), live tab preview, and download links for all generated artifacts.

### Transcribe (MP3 upload)

```bash
curl -X POST http://localhost:8000/transcribe \
  -F "audio_file=@path/to/song.mp3"
# {"status":"received","midi_file":"outputs/song.mid","notes_file":"outputs/song.notes.json","note_count":42,"positions_file":"outputs/song.positions.json","tab_file":"outputs/song.tab"}
```

Uploaded files are saved to `samples/`. MIDI output is written to `outputs/<stem>.mid` using [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) with the ONNX runtime (no TensorFlow required on Linux). Extracted notes are saved to `outputs/<stem>.notes.json`:

```json
[
  {"pitch": "E4", "start": 0.52, "end": 0.88}
]
```

Fretboard positions (standard tuning E A D G B E) are saved to `outputs/<stem>.positions.json`:

```json
[
  {
    "note": "E4",
    "start": 0.52,
    "end": 0.88,
    "position": {"string": 1, "fret": 0}
  }
]
```

Guitar tablature is saved to `outputs/<stem>.tab`:

```text
e|----0----3----5
B|-----------------
G|-----------------
D|-----------------
A|-----------------
E|-----------------
```

## Docker

```bash
docker compose up --build
curl http://localhost:8000/health
```

The container uses Python 3.12 for compatibility with upcoming ML dependencies (librosa, Basic Pitch).

## Project structure

```text
audio2tab/
├── app/
│   ├── api/          # HTTP routes
│   ├── services/     # Business logic (transcription, tab gen)
│   ├── models/       # Pydantic schemas
│   ├── core/         # Config and shared settings
│   └── utils/        # Helpers
├── frontend/         # Web UI (HTML/CSS/JS)
├── tests/
├── samples/          # Input audio files
├── outputs/          # Generated MIDI and TAB files
└── notebooks/        # Experimentation
```

## License

TBD
