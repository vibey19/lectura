"""Image in, note out: the one path every entry point shares.

The local API and the hosted GPU demo both call `read_image`, so the demo runs
exactly the preprocessing, structuring and post-processing that was measured.
"""

from __future__ import annotations

import base64
import io

from PIL import Image
from pydantic import BaseModel

from lectura import ingest
from lectura.extract.base import Extractor
from lectura.preprocess import preprocess
from lectura.schema import Note
from lectura.structure import build_note


class ExtractResult(BaseModel):
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


def read_image(
    image: Image.Image,
    extractor: Extractor,
    *,
    use_preprocess: bool = True,
    max_edge: int = 2200,
    source_name: str | None = None,
) -> ExtractResult:
    """Run the full pipeline. Raises whatever the extractor raises."""
    steps = "skipped"
    if use_preprocess:
        result = preprocess(image)
        image, steps = result.image, result.summary()
    image = ingest.fit_within(image, max_edge)

    raw = extractor.extract(image)
    return ExtractResult(
        note=build_note(raw, source_image=source_name),
        seconds=raw.seconds,
        backend=raw.backend,
        preprocess=steps,
        truncated=raw.truncated,
        preview=preview_data_url(image),
    )


def preview_data_url(image: Image.Image, longest_edge: int = 1100) -> str:
    thumbnail = ingest.fit_within(image, longest_edge)
    buffer = io.BytesIO()
    thumbnail.save(buffer, format="JPEG", quality=78, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
