import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes.outputs import _resolve_output_file
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

    frontend_static = test_settings.frontend_dir / "static" / "css"
    frontend_static.mkdir(parents=True)
    (test_settings.frontend_dir / "index.html").write_text("<html>Audio2Tab</html>")
    (frontend_static / "app.css").write_text("body { color: red; }")

    monkeypatch.setattr("app.core.config.settings", test_settings)
    monkeypatch.setattr("app.main.settings", test_settings)
    monkeypatch.setattr("app.api.routes.outputs.settings", test_settings)

    with TestClient(create_app()) as client:
        yield client, test_settings


def test_index_serves_frontend(app_client):
    client, _ = app_client
    response = client.get("/")

    assert response.status_code == 200
    assert "Audio2Tab" in response.text


def test_static_assets_are_served(app_client):
    client, _ = app_client
    response = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert response.text == "body { color: red; }"


def test_outputs_serves_generated_file(app_client):
    client, settings = app_client
    tab_path = settings.outputs_dir / "song.tab"
    tab_path.write_text("e|----0\n", encoding="utf-8")

    response = client.get("/api/outputs/song.tab")

    assert response.status_code == 200
    assert response.text == "e|----0\n"


def test_outputs_rejects_path_traversal(app_client):
    _, settings = app_client
    (settings.outputs_dir / "safe.tab").write_text("e|0\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        _resolve_output_file("../safe.tab")

    assert exc_info.value.status_code == 400


def test_outputs_returns_404_for_missing_file(app_client):
    client, _ = app_client
    response = client.get("/api/outputs/missing.tab")

    assert response.status_code == 404
