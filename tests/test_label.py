"""The labelling tool writes ground truth, so it must write the right thing to
the right place and nowhere else."""

import json

from fastapi.testclient import TestClient
from PIL import Image

from lectura.evaluate.label import create_app


def _setup(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for name in ("a", "b"):
        Image.new("RGB", (60, 40), "white").save(photos / f"{name}.jpg")
    (photos / "notes.txt").write_text("not an image")
    root = tmp_path / "eval"
    return TestClient(create_app(photos, root, "board", "Public domain")), root


def test_queue_lists_only_unlabelled_images(tmp_path):
    client, _ = _setup(tmp_path)
    assert client.get("/api/queue").json() == {"pending": ["a", "b"], "labelled": 0}


def test_saving_writes_a_reference_and_advances_the_queue(tmp_path):
    client, root = _setup(tmp_path)
    response = client.post("/api/save", json={
        "page_id": "a", "surface": "board", "text": "  Newton's   second law ",
        "formulas": ["F = ma", "", "  a = F/m "], "licence": "Public domain",
    })
    assert response.status_code == 200
    saved = json.loads((root / "pages" / "a.json").read_text())
    assert saved["text"] == "Newton's second law"
    assert saved["formulas"] == ["F = ma", "a = F/m"]
    assert saved["surface"] == "board"
    assert client.get("/api/queue").json()["pending"] == ["b"]


def test_images_are_served_by_id_never_by_path(tmp_path):
    client, _ = _setup(tmp_path)
    assert client.get("/image/a").headers["content-type"] == "image/jpeg"
    assert client.get("/image/..%2F..%2Fpyproject").status_code == 404
    assert client.get("/image/notes").status_code == 404


def test_unknown_surface_is_rejected(tmp_path):
    client, _ = _setup(tmp_path)
    response = client.post("/api/save", json={
        "page_id": "a", "surface": "napkin", "text": "", "formulas": [], "licence": "",
    })
    assert response.status_code == 400
