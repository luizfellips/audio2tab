from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.utils.audio import (
    has_mp3_signature,
    is_valid_mp3_content_type,
    is_valid_mp3_extension,
)


class AudioUploadError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def save_audio_upload(file: UploadFile, settings: Settings) -> Path:
    if not file.filename:
        raise AudioUploadError("Missing filename")

    if not is_valid_mp3_extension(file.filename):
        raise AudioUploadError("Only MP3 files are supported")

    if not is_valid_mp3_content_type(file.content_type):
        raise AudioUploadError("Invalid content type for MP3 upload")

    data = await file.read()
    if not data:
        raise AudioUploadError("Uploaded file is empty")

    if len(data) > settings.max_upload_bytes:
        raise AudioUploadError(
            f"File exceeds maximum size of {settings.max_upload_mb} MB",
            status_code=413,
        )

    if not has_mp3_signature(data):
        raise AudioUploadError("File does not appear to be a valid MP3")

    settings.ensure_directories()
    destination = settings.samples_dir / Path(file.filename).name
    destination.write_bytes(data)

    return destination
