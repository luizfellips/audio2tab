import pytest

from app.utils.audio import (
    has_mp3_signature,
    is_valid_mp3_content_type,
    is_valid_mp3_extension,
)


def test_is_valid_mp3_extension():
    assert is_valid_mp3_extension("song.mp3") is True
    assert is_valid_mp3_extension("song.MP3") is True
    assert is_valid_mp3_extension("song.wav") is False


def test_is_valid_mp3_content_type():
    assert is_valid_mp3_content_type("audio/mpeg") is True
    assert is_valid_mp3_content_type("audio/mpeg; charset=binary") is True
    assert is_valid_mp3_content_type("audio/wav") is False
    assert is_valid_mp3_content_type(None) is True


def test_has_mp3_signature():
    assert has_mp3_signature(b"ID3\x03") is True
    assert has_mp3_signature(b"\xff\xfb\x90") is True
    assert has_mp3_signature(b"RIFF") is False
