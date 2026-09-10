"""Tesseract baseline.

Not a production path. It exists so every claim of improvement is measured
against something, and because its failure mode is itself informative: on our
samples it degraded with mathematical density rather than handwriting quality.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image

from lectura.extract.base import Extractor, RawExtraction, RawItem


class Tesseract(Extractor):
    name = "tesseract"

    def __init__(self, lang: str = "eng") -> None:
        self.lang = lang

    @staticmethod
    def available() -> bool:
        return shutil.which("tesseract") is not None

    def extract(self, image: Image.Image) -> RawExtraction:
        if not self.available():
            raise RuntimeError("tesseract not installed (brew install tesseract)")

        started = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "page.png"
            image.save(src)
            proc = subprocess.run(
                ["tesseract", str(src), "stdout", "-l", self.lang],
                capture_output=True,
                text=True,
            )
        elapsed = time.perf_counter() - started

        items = [
            RawItem(text=line.strip(), confidence=None)
            for line in proc.stdout.splitlines()
            if line.strip()
        ]
        return RawExtraction(
            items=items, backend=self.name, seconds=round(elapsed, 1)
        )
