"""API contract tests. These use the tesseract backend so they need no model
server; the point is the HTTP surface, not extraction quality."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from lectura.api import app
from lectura.api.server import STATIC_DIR
from lectura.extract import Tesseract
from lectura.schema import Block, BlockType, Note

client = TestClient(app)


def _png(size=(300, 400), colour=245) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (colour, colour, colour)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_lists_themes_and_backends():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert len(body["themes"]) == 4
    assert "vlm" in body["backends"]


def test_unknown_backend_is_rejected():
    response = client.post(
        "/api/extract?backend=nonsense",
        files={"file": ("a.png", _png(), "image/png")},
    )
    assert response.status_code == 400


def test_unreadable_upload_is_rejected():
    response = client.post(
        "/api/extract",
        files={"file": ("a.png", b"this is not an image", "image/png")},
    )
    assert response.status_code == 415


@pytest.mark.skipif(not Tesseract.available(), reason="tesseract not installed")
def test_extract_returns_a_note():
    response = client.post(
        "/api/extract?backend=tesseract",
        files={"file": ("a.png", _png(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["note"]["schema_version"]
    assert "backend" in body


def test_render_accepts_an_edited_note():
    note = Note(title="Edited", blocks=[Block(type=BlockType.TEXT, content="hi")])
    response = client.post(
        "/api/render", json={"note": note.model_dump(mode="json"), "theme": "dark"}
    )
    assert response.status_code == 200
    assert "Edited" in response.text


def test_render_rejects_unknown_theme():
    note = Note(blocks=[])
    response = client.post(
        "/api/render", json={"note": note.model_dump(mode="json"), "theme": "nope"}
    )
    assert response.status_code == 400


@pytest.mark.skipif(
    not STATIC_DIR.exists(),
    reason="frontend not built; run `npm run build` in frontend/",
)
def test_client_side_routes_serve_the_app_shell():
    # A refresh on /app must not 404: the router lives in the browser.
    response = client.get("/app")
    assert response.status_code == 200


def test_unknown_api_routes_still_404():
    assert client.get("/api/nope").status_code == 404


@pytest.mark.skipif(not Tesseract.available(), reason="tesseract not installed")
def test_extract_returns_a_displayable_preview():
    # Browsers cannot render HEIC, so the server returns what it actually read.
    response = client.post(
        "/api/extract?backend=tesseract",
        files={"file": ("a.png", _png(), "image/png")},
    )
    preview = response.json()["preview"]
    assert preview.startswith("data:image/jpeg;base64,")
    assert len(preview) > 100


def test_rate_limit_rejects_once_the_hourly_ceiling_is_reached(monkeypatch):
    # One extraction occupies a CPU for minutes; a public demo needs a ceiling.
    import lectura.api.server as app_module

    monkeypatch.setattr(app_module, "RATE_LIMIT_PER_HOUR", 2)
    app_module._requests.clear()

    statuses = [
        client.post(
            "/api/extract?backend=tesseract",
            files={"file": ("a.png", _png(), "image/png")},
        ).status_code
        for _ in range(3)
    ]
    assert statuses[-1] == 429
    app_module._requests.clear()


def test_rate_limit_can_be_disabled():
    import lectura.api.server as app_module

    assert app_module.RATE_LIMIT_PER_HOUR > 0   # sane default for a public demo


@pytest.mark.skipif(not STATIC_DIR.exists(), reason="frontend not built")
def test_static_files_are_served_rather_than_the_shell():
    # The demo notes, favicon and robots.txt live under the static root and were
    # being answered with HTML until the fallback checked for real files first.
    response = client.get("/demo/index.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.skipif(not STATIC_DIR.exists(), reason="frontend not built")
def test_path_traversal_cannot_escape_the_static_root():
    for attempt in ("../pyproject.toml", "../../README.md", "..%2fpyproject.toml"):
        body = client.get(f"/{attempt}").text
        assert "[project]" not in body
