import asyncio

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.config import reload_settings
from app.models.transcribe import TranscribeResponse
from app.services.audio_preprocess import AudioPreprocessError, prepare_audio_for_transcription
from app.services.audio_upload import AudioUploadError, save_audio_upload
from app.services.midi_parser import MidiParseError, save_notes_json
from app.services.note_cleaner import clean_notes
from app.services.note_mapping import map_notes_to_fretboard, save_mapped_notes_json
from app.services.tab_generator import save_tab
from app.services.transcription import TranscriptionError, transcribe_audio
from app.services.transcription_profile import resolve_transcription_settings

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.post("", response_model=TranscribeResponse)
async def transcribe(
    audio_file: UploadFile = File(...),
    profile: str | None = Query(default=None, description="Optional: synthetic"),
) -> TranscribeResponse:
    settings = reload_settings()
    if profile:
        settings = settings.model_copy(update={"transcription_profile": profile})
    effective_settings = resolve_transcription_settings(settings)

    try:
        saved_path = await save_audio_upload(audio_file, settings)
    except AudioUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    try:
        preprocess_result = await asyncio.to_thread(
            prepare_audio_for_transcription, saved_path, effective_settings
        )
        transcription_path = preprocess_result.output_path
    except AudioPreprocessError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc

    try:
        midi_path, raw_notes = await asyncio.to_thread(
            transcribe_audio, transcription_path, effective_settings
        )
    except TranscriptionError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc

    try:
        notes, filtered_count = await asyncio.to_thread(
            clean_notes, raw_notes, effective_settings, transcription_path
        )
        raw_notes_path = await asyncio.to_thread(
            save_notes_json,
            raw_notes,
            settings.outputs_dir / f"{saved_path.stem}.raw.notes.json",
        )
        notes_path = await asyncio.to_thread(
            save_notes_json,
            notes,
            settings.outputs_dir / f"{saved_path.stem}.notes.json",
        )
        mapped_notes, skipped_notes = await asyncio.to_thread(
            map_notes_to_fretboard, notes, effective_settings
        )
        positions_path = await asyncio.to_thread(
            save_mapped_notes_json,
            mapped_notes,
            settings.outputs_dir / f"{saved_path.stem}.positions.json",
        )
        tab_path = await asyncio.to_thread(
            save_tab,
            mapped_notes,
            settings.outputs_dir / f"{saved_path.stem}.tab",
            effective_settings,
        )
    except MidiParseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc

    return TranscribeResponse(
        status="received",
        midi_file=str(midi_path),
        notes_file=str(notes_path),
        raw_notes_file=str(raw_notes_path),
        raw_note_count=len(raw_notes),
        note_count=len(notes),
        filtered_note_count=filtered_count,
        mapped_note_count=len(mapped_notes),
        skipped_notes=skipped_notes,
        positions_file=str(positions_path),
        tab_file=str(tab_path),
        preprocessed_file=str(preprocess_result.output_path),
        stem_separation=preprocess_result.stem_separation,
        stereo_mode=preprocess_result.stereo_mode,
        transcription_profile=effective_settings.transcription_profile,
    )
