import pytest

from app.core.config import Settings, get_settings, reload_settings


def test_settings_reads_basic_pitch_from_environment(monkeypatch):
    reload_settings()
    monkeypatch.setenv("BASIC_PITCH_ONSET_THRESHOLD", "0.88")
    monkeypatch.setenv("BASIC_PITCH_FRAME_THRESHOLD", "0.77")
    reload_settings()

    settings = get_settings()

    assert settings.basic_pitch_onset_threshold == 0.88
    assert settings.basic_pitch_frame_threshold == 0.77


def test_reload_settings_picks_up_new_environment(monkeypatch):
    reload_settings()
    monkeypatch.setenv("BASIC_PITCH_ONSET_THRESHOLD", "0.55")
    reload_settings()
    assert get_settings().basic_pitch_onset_threshold == 0.55

    monkeypatch.setenv("BASIC_PITCH_ONSET_THRESHOLD", "0.91")
    reload_settings()
    assert get_settings().basic_pitch_onset_threshold == 0.91


def test_settings_reads_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "BASIC_PITCH_ONSET_THRESHOLD=0.81\nBASIC_PITCH_FRAME_THRESHOLD=0.72\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BASIC_PITCH_ONSET_THRESHOLD", "")
    monkeypatch.setenv("BASIC_PITCH_FRAME_THRESHOLD", "")
    monkeypatch.delenv("BASIC_PITCH_ONSET_THRESHOLD", raising=False)
    monkeypatch.delenv("BASIC_PITCH_FRAME_THRESHOLD", raising=False)
    monkeypatch.setattr("app.core.config.ENV_FILE", env_path)
    reload_settings()

    settings = get_settings()

    assert settings.basic_pitch_onset_threshold == 0.81
    assert settings.basic_pitch_frame_threshold == 0.72
