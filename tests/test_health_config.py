import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    test_settings = Settings(
        samples_dir=tmp_path / "samples",
        outputs_dir=tmp_path / "outputs",
        frontend_dir=tmp_path / "frontend",
    )
    test_settings.ensure_directories()

    monkeypatch.setattr("app.core.config.settings", test_settings)
    monkeypatch.setattr("app.main.settings", test_settings)

    with TestClient(create_app()) as client:
        yield client, test_settings


def test_config_endpoint_reflects_env(app_client, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("BASIC_PITCH_ONSET_THRESHOLD", "0.88")
    monkeypatch.setenv("BASIC_PITCH_FRAME_THRESHOLD", "0.77")

    from app.core.config import reload_settings

    reload_settings()

    response = client.get("/health/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["basic_pitch_onset_threshold"] == 0.88
    assert payload["basic_pitch_frame_threshold"] == 0.77
    assert "env_file" in payload
