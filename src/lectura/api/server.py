"""HTTP API.

Stateless by design. An uploaded image is processed in memory and never written
to disk; the note travels back to the browser and lives there. That is the
privacy position from the README, and it also means there is no database, no
session store and nothing to deploy beyond the process itself.
"""

from __future__ import annotations

import base64
import io
import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from lectura import ingest
from lectura.extract import ExtractionError, OllamaVLM, Pix2TextOCR, Tesseract
from lectura.preprocess import preprocess
from lectura.render import available_themes, render
from lectura.schema import Note
from lectura.structure import build_note

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
STATIC_DIR = Path(__file__).parent / "static"

# Origins allowed to call the API. A split deployment puts the frontend on a
# static host and the backend wherever a 6GB model can actually run, so the
# permitted origin has to be configurable rather than hardcoded.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "LECTURA_ALLOWED_ORIGINS", "http://localhost:5173"
    ).split(",")
    if origin.strip()
]

# One extraction occupies a CPU for minutes. Without a ceiling a public demo is
# trivially turned into someone else's compute.
RATE_LIMIT_PER_HOUR = int(os.getenv("LECTURA_RATE_LIMIT", "12"))
_requests: dict[str, list[float]] = defaultdict(list)

BACKENDS = {
    "vlm": lambda: OllamaVLM(model=os.getenv("LECTURA_MODEL", "qwen2.5vl:7b")),
    "pix2text": Pix2TextOCR,
    "tesseract": Tesseract,
}

app = FastAPI(title="Lectura", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _rate_limit(request: Request) -> None:
    """Allow a fixed number of extractions per client per hour."""
    if RATE_LIMIT_PER_HOUR <= 0:
        return
    client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now = time.time()
    recent = [t for t in _requests[client] if now - t < 3600]
    if len(recent) >= RATE_LIMIT_PER_HOUR:
        recent_at = min(recent)
        wait = int((3600 - (now - recent_at)) / 60) + 1
        raise HTTPException(
            429, f"rate limit reached; try again in about {wait} minutes"
        )
    recent.append(now)
    _requests[client] = recent


class ExtractResponse(BaseModel):
    note: Note
    seconds: float
    backend: str
    preprocess: str
    truncated: bool = False
    """The model was cut off mid-answer and this note is partial."""

    preview: str = ""
    """Data URL of the image the model actually read.

    Returned rather than letting the browser display the upload directly:
    browsers cannot decode HEIC, which is what most phone photos arrive as, and
    a preview of the corrected image is the more useful comparison anyway - it
    shows what the model saw, not what the camera produced.
    """


class RenderRequest(BaseModel):
    note: Note
    theme: str = "academic"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "themes": available_themes(),
            "backends": list(BACKENDS)}


@app.post("/api/extract", response_model=ExtractResponse)
async def extract(
    request: Request,
    file: UploadFile = File(...),
    backend: str = "vlm",
    max_edge: int = 2200,
    use_preprocess: bool = True,
) -> ExtractResponse:
    if backend not in BACKENDS:
        raise HTTPException(400, f"unknown backend {backend!r}")
    _rate_limit(request)

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
    except ExtractionError as exc:
        # A readable reason, not a blank page: the user waited minutes for this.
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    note = build_note(raw, source_image=file.filename)
    return ExtractResponse(
        note=note,
        seconds=raw.seconds,
        backend=raw.backend,
        preprocess=steps,
        truncated=raw.truncated,
        preview=_preview_data_url(image),
    )


def _preview_data_url(image: Image.Image, longest_edge: int = 1100) -> str:
    thumbnail = ingest.fit_within(image, longest_edge)
    buffer = io.BytesIO()
    thumbnail.save(buffer, format="JPEG", quality=78, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"


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


# Built frontend, when present. Registered last so /api routes take priority.
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        """Serve the app shell for client-side routes such as /app.

        Without this a refresh on any route but / returns 404, because the
        router lives in the browser and the server knows only one document.
        """
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        return FileResponse(STATIC_DIR / "index.html")
