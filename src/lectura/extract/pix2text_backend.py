"""Pix2Text backend: layout analysis, text OCR and formula recognition.

A staged document pipeline rather than a single multimodal model, which makes it
the natural comparison point for the end-to-end VLM. Its text OCR is trained on
printed material, so on handwriting it behaves much like Tesseract while its
formula recogniser keeps working - the same split this project was founded on.

Initialised on CPU deliberately. The bundled formula detector runs through ONNX
Runtime, whose CoreML provider fails to build an execution plan on Apple silicon
("Error in building plan"), taking the whole pipeline down with it.
"""

from __future__ import annotations

import re
import time

from PIL import Image

from lectura.extract.base import Extractor, RawExtraction, RawItem

_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)


class Pix2TextOCR(Extractor):
    name = "pix2text"

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._engine = None

    def _load(self):
        if self._engine is None:
            from pix2text import Pix2Text

            self._engine = Pix2Text.from_config(device=self.device)
        return self._engine

    def extract(self, image: Image.Image) -> RawExtraction:
        engine = self._load()
        started = time.perf_counter()
        output = engine.recognize(image, return_text=True)
        elapsed = time.perf_counter() - started

        return RawExtraction(
            items=list(_parse(str(output))),
            backend=self.name,
            seconds=round(elapsed, 1),
        )


def _parse(text: str):
    """Split Pix2Text's markdown into maths and prose, preserving order."""
    position = 0
    for match in _DISPLAY_MATH.finditer(text):
        yield from _prose(text[position : match.start()])
        expression = match.group(1).strip()
        if expression:
            yield RawItem(text=f"${expression}$", hint="math")
        position = match.end()
    yield from _prose(text[position:])


def _prose(chunk: str):
    for line in chunk.splitlines():
        line = line.strip()
        if line:
            yield RawItem(text=line, hint="body")
