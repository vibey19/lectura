"""The labelled evaluation set.

Ground truth lives beside the images as small JSON files, one per page. Images
themselves are never committed - they are personal coursework or third-party
lecture material - so the manifest records where each page came from and under
what licence, and the fetch path stays reproducible.

A reference records what a careful human reads on the page, in reading order.
It is not what any model produced.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOT = Path("data/eval")


@dataclass
class Reference:
    """Hand-checked ground truth for one page."""

    page_id: str
    source: str                      # path to the image, relative to repo root
    surface: str                     # notebook | board | slide
    text: str = ""                   # prose in reading order, excluding formulas
    formulas: list[str] = field(default_factory=list)   # LaTeX, in reading order
    licence: str = "personal"
    note: str = ""                   # anything unusual about the page

    @classmethod
    def load(cls, path: Path) -> Reference:
        return cls(**json.loads(Path(path).read_text()))

    def save(self, root: Path = DEFAULT_ROOT) -> Path:
        directory = Path(root) / "pages"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.page_id}.json"
        payload = {
            "page_id": self.page_id,
            "source": self.source,
            "surface": self.surface,
            "text": self.text,
            "formulas": self.formulas,
            "licence": self.licence,
            "note": self.note,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        return path


def load_all(root: Path = DEFAULT_ROOT) -> list[Reference]:
    directory = Path(root) / "pages"
    if not directory.exists():
        return []
    return [Reference.load(p) for p in sorted(directory.glob("*.json"))]


def missing_images(references: list[Reference]) -> list[Reference]:
    """References whose source image is not present locally."""
    return [r for r in references if not Path(r.source).exists()]
