from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter(prefix="/api/outputs", tags=["outputs"])

ALLOWED_SUFFIXES = {".mid", ".tab", ".json"}


def _resolve_output_file(filename: str) -> Path:
    if not filename or filename != Path(filename).name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if Path(filename).suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    outputs_dir = settings.outputs_dir.resolve()
    file_path = (settings.outputs_dir / filename).resolve()

    try:
        file_path.relative_to(outputs_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid file path") from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return file_path


@router.get("/{filename}")
def get_output_file(filename: str) -> FileResponse:
    file_path = _resolve_output_file(filename)
    media_type = "application/octet-stream"

    if file_path.suffix == ".tab":
        media_type = "text/plain; charset=utf-8"
    elif file_path.suffix == ".json":
        media_type = "application/json"
    elif file_path.suffix == ".mid":
        media_type = "audio/midi"

    return FileResponse(file_path, media_type=media_type, filename=file_path.name)
