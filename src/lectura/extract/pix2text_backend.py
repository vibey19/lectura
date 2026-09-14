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

import time

from PIL import Image

from lectura.extract.base import Extractor, RawExtraction
from lectura.extract.markdown import markdown_items


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
            items=list(markdown_items(str(output))),
            backend=self.name,
            seconds=round(elapsed, 1),
        )
