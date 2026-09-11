"""HTTP API.

Stateless by design. An uploaded image is processed in memory and never written
to disk; the note travels back to the browser and lives there. That is the
privacy position from the README, and it also means there is no database, no
session store and nothing to deploy beyond the process itself.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from lectura import ingest
from lectura.extract import OllamaVLM, Pix2TextOCR, Tesseract
from lectura.preprocess import preprocess
from lectura.render import available_themes, render
from lectura.schema import Note
from lectura.structure import build_note

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
STATIC_DIR = Path(__file__).parent / "static"

BACKENDS = {
    "vlm": lambda: OllamaVLM(model=os.getenv("LECTURA_MODEL", "qwen2.5vl:7b")),
    "pix2text": Pix2TextOCR,
    "tesseract": Tesseract,
}

app = FastAPI(title="Lectura", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractResponse(BaseModel):
    note: Note
    seconds: float
    backend: str
    preprocess: str


class RenderRequest(BaseModel):
    note: Note
    theme: str = "academic"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "themes": available_themes(),
            "backends": list(BACKENDS)}


@app.post("/api/extract", response_model=ExtractResponse)
async def extract(
    file: UploadFile = File(...),
    backend: str = "vlm",
    max_edge: int = 2200,
    use_preprocess: bool = True,
) -> ExtractResponse:
    if backend not in BACKENDS:
        raise HTTPException(400, f"unknown backend {backend!r}")

    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "image larger than 20MB")

    try:
        image = _open(payload, file.filename or "upload")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(415, f"cannot read image: {exc}") from exc

    steps = "skipped"
    if use_preprocess:
        result = preprocess(image)
        image, steps = result.image, result.summary()
    image = ingest.fit_within(image, max_edge)

    try:
        raw = BACKENDS[backend]().extract(image)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    note = build_note(raw, source_image=file.filename)
    return ExtractResponse(
        note=note, seconds=raw.seconds, backend=raw.backend, preprocess=steps
    )


@app.post("/api/render", response_class=HTMLResponse)
def render_note(request: RenderRequest) -> HTMLResponse:
    """Re-render an edited note. No model runs here - themes are presentation."""
    if request.theme not in available_themes():
        raise HTTPException(400, f"unknown theme {request.theme!r}")
    return HTMLResponse(render(request.note, request.theme))


def _open(payload: bytes, filename: str) -> Image.Image:
    """Decode an upload, routing HEIC through the ingest path."""
    if Path(filename).suffix.lower() in {".heic", ".heif"}:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix) as handle:
            handle.write(payload)
            handle.flush()
            return ingest.load(handle.name)
    from PIL import ImageOps

    image = Image.open(io.BytesIO(payload))
    return ImageOps.exif_transpose(image).convert("RGB")


# Built frontend, when present. Mounted last so /api routes win.
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
