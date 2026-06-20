from pathlib import Path

ALLOWED_EXTENSIONS = {".mp3"}
ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mpeg",
    "application/octet-stream",
}


def is_valid_mp3_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def is_valid_mp3_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return True
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in ALLOWED_CONTENT_TYPES


def has_mp3_signature(data: bytes) -> bool:
    if len(data) < 3:
        return False

    if data[:3] == b"ID3":
        return True

    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True

    return False
